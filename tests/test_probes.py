"""Tests for probes."""

import pytest

from probe.db import DuckDBAdapter
from probe.probes import column_presence, row_count


@pytest.fixture()
def adapter():
    db = DuckDBAdapter.connect(":memory:")
    db.run("CREATE TABLE orders (id INT, customer TEXT, amount DOUBLE)")
    db.run(
        "INSERT INTO orders VALUES"
        " (1, 'alice', 10.0),"
        " (2, 'bob', 20.0),"
        " (3, 'alice', 30.0)"
    )
    db._query_count = 0
    yield db
    db.close()


OLD_SQL = "SELECT * FROM orders"


class TestRowCount:
    def test_no_change(self, adapter):
        result = row_count(adapter, OLD_SQL, OLD_SQL)
        assert result.name == "row_count"
        assert result.old_value == 3
        assert result.new_value == 3
        assert result.delta == 0
        assert result.status == "ok"

    def test_rows_added(self, adapter):
        new_sql = "SELECT * FROM orders UNION ALL SELECT 4, 'carol', 40.0"
        result = row_count(adapter, OLD_SQL, new_sql)
        assert result.old_value == 3
        assert result.new_value == 4
        assert result.delta == 1
        assert result.status == "changed"

    def test_rows_removed(self, adapter):
        new_sql = "SELECT * FROM orders WHERE id <= 2"
        result = row_count(adapter, OLD_SQL, new_sql)
        assert result.old_value == 3
        assert result.new_value == 2
        assert result.delta == -1
        assert result.status == "changed"

    def test_receipt_carries_sql_and_numbers(self, adapter):
        result = row_count(adapter, OLD_SQL, OLD_SQL)
        assert "COUNT(*)" in result.receipt.sql
        assert result.receipt.result == {"old": 3, "new": 3}

    def test_empty_tables(self, adapter):
        empty = "SELECT * FROM orders WHERE 1=0"
        result = row_count(adapter, empty, empty)
        assert result.old_value == 0
        assert result.new_value == 0
        assert result.delta == 0
        assert result.status == "ok"


class TestColumnPresence:
    def test_no_change(self, adapter):
        result = column_presence(adapter, OLD_SQL, OLD_SQL)
        assert result.name == "column_presence"
        assert result.status == "ok"
        assert result.delta == {"added": [], "removed": []}

    def test_column_added(self, adapter):
        new_sql = "SELECT *, amount * 2 AS doubled FROM orders"
        result = column_presence(adapter, OLD_SQL, new_sql)
        assert result.status == "changed"
        assert result.delta["added"] == ["doubled"]
        assert result.delta["removed"] == []
        assert "doubled" in result.new_value
        assert "doubled" not in result.old_value

    def test_column_removed(self, adapter):
        new_sql = "SELECT id, customer FROM orders"
        result = column_presence(adapter, OLD_SQL, new_sql)
        assert result.status == "changed"
        assert result.delta["added"] == []
        assert result.delta["removed"] == ["amount"]

    def test_column_added_and_removed(self, adapter):
        new_sql = "SELECT id, amount * 2 AS doubled FROM orders"
        result = column_presence(adapter, OLD_SQL, new_sql)
        assert result.status == "changed"
        assert result.delta["added"] == ["doubled"]
        assert result.delta["removed"] == ["customer", "amount"]

    def test_receipt_carries_column_lists(self, adapter):
        result = column_presence(adapter, OLD_SQL, OLD_SQL)
        assert result.receipt.result["old_columns"] == ["id", "customer", "amount"]
        assert result.receipt.result["new_columns"] == ["id", "customer", "amount"]
        assert "LIMIT 0" in result.receipt.sql

    def test_preserves_column_order(self, adapter):
        new_sql = "SELECT amount, id, customer FROM orders"
        result = column_presence(adapter, OLD_SQL, new_sql)
        assert result.new_value == ["amount", "id", "customer"]
        assert result.status == "ok"
