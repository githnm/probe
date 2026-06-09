"""Tests for the diff pipeline (probes -> severity -> report)."""

import pytest

from probe.db import DuckDBAdapter
from probe.diff import run_diff
from probe.report import render_terminal


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
    yield db
    db.close()


OLD_SQL = "SELECT * FROM orders"


class TestRunDiff:
    def test_no_change_is_info(self, adapter):
        report = run_diff(adapter, OLD_SQL, OLD_SQL)
        assert report.severity == "info"
        assert all(r.status == "ok" for r in report.results)

    def test_row_drop_is_warn(self, adapter):
        new_sql = "SELECT * FROM orders WHERE id <= 2"
        report = run_diff(adapter, OLD_SQL, new_sql)
        assert report.severity == "warn"
        rc = next(r for r in report.results if r.name == "row_count")
        assert rc.status == "changed"
        assert rc.delta == -1

    def test_column_removed_is_block(self, adapter):
        new_sql = "SELECT id, customer FROM orders"
        report = run_diff(adapter, OLD_SQL, new_sql)
        assert report.severity == "block"
        cp = next(r for r in report.results if r.name == "column_presence")
        assert "amount" in cp.delta["removed"]

    def test_column_added_is_info(self, adapter):
        new_sql = "SELECT *, amount * 2 AS doubled FROM orders"
        report = run_diff(adapter, OLD_SQL, new_sql)
        assert report.severity == "info"
        assert "doubled" in report.scope

    def test_all_results_have_receipts(self, adapter):
        report = run_diff(adapter, OLD_SQL, OLD_SQL)
        for r in report.results:
            assert r.receipt is not None
            assert r.receipt.sql
            assert r.receipt.result is not None

    def test_scope_lists_changed_columns(self, adapter):
        new_sql = "SELECT id, customer, amount * 2 AS doubled FROM orders"
        report = run_diff(adapter, OLD_SQL, new_sql)
        assert "doubled" in report.scope
        assert "amount" in report.scope


class TestPipelineRendersWithReceipts:
    def test_terminal_output_has_receipts(self, adapter):
        new_sql = "SELECT * FROM orders WHERE id <= 2"
        report = run_diff(adapter, OLD_SQL, new_sql)
        text = render_terminal(report)
        assert "receipt:" in text
        assert "COUNT(*)" in text
        assert "severity: warn" in text
