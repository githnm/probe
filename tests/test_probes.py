"""Tests for probes."""

import pytest

from probe.db import DuckDBAdapter
from probe.probes import column_presence, grain, null_rate, row_count


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


class TestGrain:
    def test_no_key_is_unverified(self, adapter):
        result = grain(adapter, OLD_SQL, OLD_SQL)
        assert result.name == "grain"
        assert result.status == "unverified"
        assert result.old_value is None
        assert result.new_value is None

    def test_unique_key_is_ok(self, adapter):
        result = grain(adapter, OLD_SQL, OLD_SQL, key="id")
        assert result.status == "ok"
        assert result.old_value["duplicates"] == 0
        assert result.new_value["duplicates"] == 0
        assert result.delta == 0

    def test_fanout_breaks_grain(self, adapter):
        new_sql = (
            "SELECT * FROM orders UNION ALL SELECT 1, 'alice', 10.0"
        )
        result = grain(adapter, OLD_SQL, new_sql, key="id")
        assert result.status == "changed"
        assert result.new_value["duplicates"] > result.old_value["duplicates"]
        assert result.delta > 0

    def test_receipt_carries_query(self, adapter):
        result = grain(adapter, OLD_SQL, OLD_SQL, key="id")
        assert "COUNT(*)" in result.receipt.sql
        assert "COUNT(DISTINCT id)" in result.receipt.sql

    def test_non_unique_column_both_sides(self, adapter):
        result = grain(adapter, OLD_SQL, OLD_SQL, key="customer")
        assert result.status == "ok"
        assert result.old_value["duplicates"] == 1
        assert result.delta == 0


class TestNullRate:
    def test_no_change(self, adapter):
        result = null_rate(adapter, OLD_SQL, OLD_SQL)
        assert result.name == "null_rate"
        assert result.status == "ok"
        assert all(d == 0 for d in result.delta.values())

    def test_nulls_introduced(self, adapter):
        new_sql = (
            "SELECT id, customer, NULL AS amount FROM orders"
        )
        result = null_rate(adapter, OLD_SQL, new_sql)
        assert result.status == "changed"
        assert result.delta["amount"] > 0
        assert result.new_value["amount"] == 100.0

    def test_nulls_removed(self, adapter):
        old_sql = "SELECT id, customer, NULL AS amount FROM orders"
        result = null_rate(adapter, old_sql, OLD_SQL)
        assert result.status == "changed"
        assert result.delta["amount"] < 0

    def test_receipt_has_sql_and_values(self, adapter):
        result = null_rate(adapter, OLD_SQL, OLD_SQL)
        assert "IS NULL" in result.receipt.sql
        assert "old" in result.receipt.result
        assert "new" in result.receipt.result

    def test_partial_nulls(self, adapter):
        new_sql = (
            "SELECT id, customer,"
            " CASE WHEN id = 1 THEN NULL ELSE amount END AS amount"
            " FROM orders"
        )
        result = null_rate(adapter, OLD_SQL, new_sql)
        assert result.status == "changed"
        assert 0 < result.new_value["amount"] < 100.0
        assert result.delta["amount"] > 0


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
