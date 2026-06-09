"""Tests for severity gating."""

from probe import ProbeResult, Receipt
from probe.severity import classify, overall


def _result(name, status="changed", delta=None):
    return ProbeResult(
        name=name,
        question="?",
        old_value=0,
        new_value=0,
        delta=delta,
        status=status,
        receipt=Receipt(sql="SELECT 1", result=None),
    )


class TestClassify:
    def test_ok_is_always_info(self):
        assert classify(_result("row_count", status="ok")) == "info"
        assert classify(_result("grain", status="ok")) == "info"

    def test_row_count_drop_is_warn(self):
        assert classify(_result("row_count", delta=-5)) == "warn"

    def test_row_count_increase_is_block(self):
        assert classify(_result("row_count", delta=10)) == "block"

    def test_grain_change_is_block(self):
        assert classify(_result("grain", delta=100)) == "block"

    def test_null_rate_increase_is_warn(self):
        assert classify(_result("null_rate", delta={"col_a": 0.1})) == "warn"

    def test_null_rate_decrease_is_info(self):
        assert classify(_result("null_rate", delta={"col_a": -0.05})) == "info"

    def test_column_removed_is_block(self):
        r = _result("column_presence", delta={"added": [], "removed": ["x"]})
        assert classify(r) == "block"

    def test_column_added_is_info(self):
        assert classify(_result("column_presence", delta={"added": ["x"], "removed": []})) == "info"

    def test_unknown_probe_is_info(self):
        assert classify(_result("some_future_probe")) == "info"


class TestOverall:
    def test_empty_is_info(self):
        assert overall([]) == "info"

    def test_takes_max_severity(self):
        results = [
            _result("row_count", delta=-1),    # warn
            _result("grain"),                   # block
            _result("column_presence", delta={"added": ["x"], "removed": []}),  # info
        ]
        assert overall(results) == "block"

    def test_all_ok_is_info(self):
        results = [
            _result("row_count", status="ok"),
            _result("column_presence", status="ok"),
        ]
        assert overall(results) == "info"
