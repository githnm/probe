"""Tests for PostgresAdapter — skipped when Postgres is unavailable."""

import os

import pytest

PG_URL = os.environ.get("PROBE_PG_URL", "")

pg_available = bool(PG_URL)
pytestmark = pytest.mark.skipif(not pg_available, reason="PROBE_PG_URL not set")


def _make_adapter(max_queries=None):
    from probe.db import PostgresAdapter

    return PostgresAdapter.connect(PG_URL, max_queries=max_queries)


@pytest.fixture()
def adapter():
    db = _make_adapter()
    db.run("DROP TABLE IF EXISTS orders")
    db.run(
        "CREATE TABLE orders ("
        " id INT, customer TEXT, amount DOUBLE PRECISION, note TEXT)"
    )
    db.run(
        "INSERT INTO orders VALUES"
        " (1, 'alice', 10.0, 'first'),"
        " (2, 'bob', 20.0, NULL),"
        " (3, 'alice', 30.0, 'third')"
    )
    db._query_count = 0
    yield db
    db.run("DROP TABLE IF EXISTS orders")
    db.close()


class TestRun:
    def test_returns_list_of_dicts(self, adapter):
        rows = adapter.run("SELECT * FROM orders ORDER BY id")
        assert len(rows) == 3
        assert rows[0]["id"] == 1
        assert rows[0]["customer"] == "alice"

    def test_aggregate_query(self, adapter):
        rows = adapter.run("SELECT COUNT(*) AS cnt FROM orders")
        assert rows == [{"cnt": 3}]

    def test_empty_result(self, adapter):
        rows = adapter.run("SELECT * FROM orders WHERE id > 100")
        assert rows == []


class TestColumns:
    def test_returns_name_type_pairs(self, adapter):
        cols = adapter.columns("SELECT * FROM orders")
        names = [name for name, _ in cols]
        assert names == ["id", "customer", "amount", "note"]

    def test_column_types(self, adapter):
        cols = adapter.columns("SELECT * FROM orders")
        type_map = dict(cols)
        assert type_map["id"] == "INTEGER"
        assert type_map["customer"] == "TEXT"
        assert type_map["amount"] == "DOUBLE PRECISION"

    def test_columns_on_subquery(self, adapter):
        cols = adapter.columns("SELECT id, amount FROM orders WHERE id > 1")
        names = [name for name, _ in cols]
        assert names == ["id", "amount"]


class TestQueryBudget:
    def test_raises_when_budget_exceeded(self):
        db = _make_adapter(max_queries=2)
        db.run("SELECT 1")
        db.run("SELECT 2")
        from probe.db import QueryBudgetExceeded

        with pytest.raises(QueryBudgetExceeded):
            db.run("SELECT 3")
        db.close()


class TestProtocol:
    def test_adapter_satisfies_protocol(self):
        from probe.db import Adapter

        db = _make_adapter()
        assert isinstance(db, Adapter)
        db.close()


class TestProbesOnPostgres:
    def test_row_count(self, adapter):
        from probe.probes import row_count

        old_sql = "SELECT * FROM orders"
        new_sql = "SELECT * FROM orders WHERE id <= 2"
        result = row_count(adapter, old_sql, new_sql)
        assert result.old_value == 3
        assert result.new_value == 2
        assert result.status == "changed"

    def test_grain_with_key(self, adapter):
        from probe.probes import grain

        old_sql = "SELECT * FROM orders"
        dup_sql = (
            "SELECT * FROM orders"
            " UNION ALL SELECT 1, 'alice', 10.0, 'first'"
        )
        result = grain(adapter, old_sql, dup_sql, key="id")
        assert result.status == "changed"
        assert result.new_value["duplicates"] > 0

    def test_null_rate(self, adapter):
        from probe.probes import null_rate

        old_sql = "SELECT * FROM orders"
        result = null_rate(adapter, old_sql, old_sql)
        assert result.status == "ok" or result.new_value["note"] > 0

    def test_column_presence(self, adapter):
        from probe.probes import column_presence

        old_sql = "SELECT * FROM orders"
        new_sql = "SELECT id, customer FROM orders"
        result = column_presence(adapter, old_sql, new_sql)
        assert result.status == "changed"
        assert "amount" in result.delta["removed"]

    def test_full_diff(self, adapter):
        from probe.diff import run_diff

        old_sql = "SELECT * FROM orders"
        new_sql = "SELECT id, customer FROM orders WHERE id <= 2"
        report = run_diff(adapter, old_sql, new_sql, key="id")
        assert report.severity == "block"
        assert any(r.name == "grain" for r in report.results)
