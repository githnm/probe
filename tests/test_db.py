"""Tests for database adapters."""

import pytest

from probe.db import DuckDBAdapter, QueryBudgetExceeded, wrap_as_subquery


@pytest.fixture()
def adapter():
    db = DuckDBAdapter.connect(":memory:")
    db.run("CREATE TABLE orders (id INT, customer TEXT, amount DOUBLE, note TEXT)")
    db.run(
        "INSERT INTO orders VALUES"
        " (1, 'alice', 10.0, 'first'),"
        " (2, 'bob', 20.0, NULL),"
        " (3, 'alice', 30.0, 'third')"
    )
    db._query_count = 0
    yield db
    db.close()


class TestRun:
    def test_returns_list_of_dicts(self, adapter):
        rows = adapter.run("SELECT * FROM orders ORDER BY id")
        assert len(rows) == 3
        assert rows[0] == {"id": 1, "customer": "alice", "amount": 10.0, "note": "first"}

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
        assert type_map["customer"] == "VARCHAR"
        assert type_map["amount"] == "DOUBLE"

    def test_columns_on_subquery(self, adapter):
        cols = adapter.columns("SELECT id, amount FROM orders WHERE id > 1")
        names = [name for name, _ in cols]
        assert names == ["id", "amount"]

    def test_columns_does_not_fetch_rows(self, adapter):
        adapter.columns("SELECT * FROM orders")
        assert adapter.query_count == 1


class TestQueryBudget:
    def test_allows_queries_within_budget(self):
        db = DuckDBAdapter.connect(":memory:", max_queries=3)
        db.run("SELECT 1")
        db.run("SELECT 2")
        db.run("SELECT 3")
        db.close()

    def test_raises_when_budget_exceeded(self):
        db = DuckDBAdapter.connect(":memory:", max_queries=2)
        db.run("SELECT 1")
        db.run("SELECT 2")
        with pytest.raises(QueryBudgetExceeded) as exc_info:
            db.run("SELECT 3")
        assert exc_info.value.limit == 2
        db.close()

    def test_no_budget_means_unlimited(self, adapter):
        for i in range(50):
            adapter.run(f"SELECT {i}")
        assert adapter.query_count == 50


class TestWrapAsSubquery:
    def test_wraps_user_sql(self):
        result = wrap_as_subquery(
            "SELECT * FROM orders",
            "SELECT COUNT(*) FROM {subquery} _t",
        )
        assert result == "SELECT COUNT(*) FROM (SELECT * FROM orders) _t"


class TestProtocol:
    def test_adapter_satisfies_protocol(self):
        from probe.db import Adapter

        db = DuckDBAdapter.connect(":memory:")
        assert isinstance(db, Adapter)
        db.close()
