"""Tests for dbt lineage scoping."""

import os

import pytest

from probe.lineage import LineageGraph, Model, load_manifest

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "manifest.json")


@pytest.fixture()
def graph():
    return load_manifest(FIXTURE)


class TestLoadManifest:
    def test_loads_all_models(self, graph):
        assert len(graph.models) == 4
        assert "model.shop.stg_orders" in graph.models
        assert "model.shop.orders" in graph.models
        assert "model.shop.revenue" in graph.models
        assert "model.shop.customers" in graph.models

    def test_model_columns(self, graph):
        stg = graph.models["model.shop.stg_orders"]
        assert "order_id" in stg.columns
        assert "amount" in stg.columns

    def test_child_map(self, graph):
        children = graph.child_map["model.shop.stg_orders"]
        assert children == ["model.shop.orders"]

    def test_orders_has_two_children(self, graph):
        children = graph.child_map["model.shop.orders"]
        assert set(children) == {"model.shop.revenue", "model.shop.customers"}

    def test_leaf_has_no_children(self, graph):
        assert graph.child_map["model.shop.revenue"] == []


class TestResolve:
    def test_resolve_by_name(self, graph):
        assert graph.resolve("stg_orders") == "model.shop.stg_orders"

    def test_resolve_by_unique_id(self, graph):
        uid = "model.shop.orders"
        assert graph.resolve(uid) == uid

    def test_resolve_unknown_returns_none(self, graph):
        assert graph.resolve("nonexistent") is None


class TestDownstream:
    def test_direct_children(self, graph):
        ds = graph.downstream("model.shop.stg_orders")
        assert "model.shop.orders" in ds

    def test_transitive_children(self, graph):
        ds = graph.downstream("model.shop.stg_orders")
        assert "model.shop.revenue" in ds
        assert "model.shop.customers" in ds

    def test_full_downstream_of_stg(self, graph):
        ds = graph.downstream("model.shop.stg_orders")
        assert set(ds) == {
            "model.shop.orders",
            "model.shop.revenue",
            "model.shop.customers",
        }

    def test_leaf_has_no_downstream(self, graph):
        assert graph.downstream("model.shop.revenue") == []

    def test_orders_downstream(self, graph):
        ds = graph.downstream("model.shop.orders")
        assert set(ds) == {"model.shop.revenue", "model.shop.customers"}


class TestImpactedColumns:
    def test_amount_propagates_to_orders(self, graph):
        cols = graph.impacted_columns("model.shop.stg_orders", ["amount"])
        assert "amount" in cols

    def test_amount_does_not_reach_revenue(self, graph):
        cols = graph.impacted_columns("model.shop.stg_orders", ["amount"])
        assert "total_amount" not in cols

    def test_customer_id_propagates_transitively(self, graph):
        cols = graph.impacted_columns("model.shop.stg_orders", ["customer_id"])
        assert "customer_id" in cols

    def test_all_columns_when_none_specified(self, graph):
        cols = graph.impacted_columns("model.shop.stg_orders")
        assert "order_id" in cols
        assert "customer_id" in cols
        assert "amount" in cols

    def test_unknown_model_returns_empty(self, graph):
        assert graph.impacted_columns("model.shop.nope", ["x"]) == []

    def test_status_only_in_orders_not_upstream(self, graph):
        cols = graph.impacted_columns("model.shop.stg_orders", ["amount"])
        assert "status" not in cols


class TestBuildWithoutChildMap:
    def test_derives_child_map_from_depends_on(self):
        graph = LineageGraph()
        a = Model("model.x.a", "a", ["id"], [])
        b = Model("model.x.b", "b", ["id"], ["model.x.a"])
        c = Model("model.x.c", "c", ["id"], ["model.x.b"])
        graph.models = {"model.x.a": a, "model.x.b": b, "model.x.c": c}
        graph.child_map = {"model.x.a": [], "model.x.b": [], "model.x.c": []}
        for uid, m in graph.models.items():
            for parent in m.depends_on:
                if parent in graph.child_map:
                    graph.child_map[parent].append(uid)

        assert graph.downstream("model.x.a") == ["model.x.b", "model.x.c"]


class TestScopedDiff:
    """Integration: lineage scoping limits which columns null_rate checks."""

    @pytest.fixture()
    def adapter(self):
        from probe.db import DuckDBAdapter

        db = DuckDBAdapter.connect(":memory:")
        db.run(
            "CREATE TABLE stg_orders"
            " (order_id INT, customer_id INT, amount DOUBLE)"
        )
        db.run(
            "INSERT INTO stg_orders VALUES"
            " (1, 100, 10.0), (2, 200, 20.0), (3, 100, 30.0)"
        )
        yield db
        db.close()

    def test_scoped_null_rate_only_checks_impacted(self, graph, adapter):
        from probe.diff import run_diff

        old_sql = "SELECT * FROM stg_orders"
        new_sql = "SELECT * FROM stg_orders"
        scope_columns = graph.impacted_columns(
            "model.shop.stg_orders", ["amount"]
        )
        report = run_diff(adapter, old_sql, new_sql, scope_columns=scope_columns)
        nr = next(r for r in report.results if r.name == "null_rate")
        assert list(nr.old_value.keys()) == ["amount"]
        assert list(nr.new_value.keys()) == ["amount"]

    def test_scoped_report_scope_reflects_lineage(self, graph, adapter):
        from probe.diff import run_diff

        old_sql = "SELECT * FROM stg_orders"
        new_sql = "SELECT * FROM stg_orders"
        scope_columns = graph.impacted_columns(
            "model.shop.stg_orders", ["amount"]
        )
        report = run_diff(adapter, old_sql, new_sql, scope_columns=scope_columns)
        assert report.scope == ["amount"]

    def test_unscoped_null_rate_checks_all_columns(self, adapter):
        from probe.diff import run_diff

        old_sql = "SELECT * FROM stg_orders"
        new_sql = "SELECT * FROM stg_orders"
        report = run_diff(adapter, old_sql, new_sql)
        nr = next(r for r in report.results if r.name == "null_rate")
        assert "order_id" in nr.old_value
        assert "customer_id" in nr.old_value
        assert "amount" in nr.old_value
