"""Tests for lineage verifier."""

import pytest

from probe.db import DuckDBAdapter
from probe.verify import verify


@pytest.fixture()
def adapter():
    db = DuckDBAdapter.connect(":memory:")
    db.run(
        "CREATE TABLE upstream ("
        " id INT, name TEXT, amount DOUBLE, code TEXT)"
    )
    db.run(
        "INSERT INTO upstream VALUES"
        " (1, 'alice', 10.0, 'A'),"
        " (2, 'bob', 20.0, 'B'),"
        " (3, 'carol', 30.0, 'C')"
    )
    db.run(
        "CREATE TABLE downstream ("
        " id INT, name TEXT, total DOUBLE, label TEXT)"
    )
    # name is a passthrough, total = amount (passthrough/rename),
    # label = code (rename)
    db.run(
        "INSERT INTO downstream VALUES"
        " (1, 'alice', 10.0, 'A'),"
        " (2, 'bob', 20.0, 'B'),"
        " (3, 'carol', 30.0, 'C')"
    )
    yield db
    db.close()


UP = "SELECT * FROM upstream"
DOWN = "SELECT * FROM downstream"


class TestPassthrough:
    def test_auto_map_verifies_shared_name(self, adapter):
        results = verify(adapter, UP, DOWN, key="id")
        by_col = {r.downstream_col: r for r in results}
        assert "name" in by_col
        assert by_col["name"].verdict == "verified"
        assert by_col["name"].match_rate >= 99.0

    def test_receipt_has_sql_and_rate(self, adapter):
        results = verify(adapter, UP, DOWN, key="id")
        name_r = next(r for r in results if r.downstream_col == "name")
        assert "IS NOT DISTINCT FROM" in name_r.receipt.sql
        assert "match_rate" in name_r.receipt.result


class TestKilledAndHunt:
    def test_wrong_mapping_is_killed(self, adapter):
        mappings = {"total": "name"}  # total actually comes from amount
        results = verify(adapter, UP, DOWN, key="id", mappings=mappings)
        assert len(results) == 1
        r = results[0]
        assert r.verdict == "killed"
        assert r.match_rate < 99.0

    def test_hunt_finds_real_parent(self, adapter):
        mappings = {"total": "name"}
        results = verify(adapter, UP, DOWN, key="id", mappings=mappings)
        r = results[0]
        assert r.real_parent == "amount"

    def test_label_mapped_to_wrong_column_killed(self, adapter):
        mappings = {"label": "name"}
        results = verify(adapter, UP, DOWN, key="id", mappings=mappings)
        r = results[0]
        assert r.verdict == "killed"
        assert r.real_parent == "code"

    def test_hunt_result_in_receipt(self, adapter):
        mappings = {"total": "name"}
        results = verify(adapter, UP, DOWN, key="id", mappings=mappings)
        r = results[0]
        assert "hunt" in r.receipt.result
        assert r.receipt.result["hunt"]["real_parent"] == "amount"


class TestUnverified:
    def test_missing_key_is_unverified(self, adapter):
        results = verify(
            adapter, UP, DOWN, key="nonexistent",
            mappings={"name": "name"},
        )
        assert len(results) == 1
        assert results[0].verdict == "unverified"
        assert "missing" in str(results[0].receipt.result)

    def test_missing_downstream_col_is_unverified(self, adapter):
        results = verify(
            adapter, UP, DOWN, key="id",
            mappings={"nope": "name"},
        )
        assert results[0].verdict == "unverified"

    def test_missing_upstream_col_is_unverified(self, adapter):
        results = verify(
            adapter, UP, DOWN, key="id",
            mappings={"name": "nope"},
        )
        assert results[0].verdict == "unverified"


class TestRenameMapping:
    def test_explicit_rename_verifies(self, adapter):
        mappings = {"total": "amount"}
        results = verify(adapter, UP, DOWN, key="id", mappings=mappings)
        assert results[0].verdict == "verified"
        assert results[0].match_rate >= 99.0

    def test_label_to_code_verifies(self, adapter):
        mappings = {"label": "code"}
        results = verify(adapter, UP, DOWN, key="id", mappings=mappings)
        assert results[0].verdict == "verified"


class TestMultipleEdges:
    def test_mixed_results(self, adapter):
        mappings = {"name": "name", "total": "name", "label": "code"}
        results = verify(adapter, UP, DOWN, key="id", mappings=mappings)
        by_col = {r.downstream_col: r for r in results}
        assert by_col["name"].verdict == "verified"
        assert by_col["total"].verdict == "killed"
        assert by_col["label"].verdict == "verified"


class TestCLI:
    def test_verify_passthrough(self):
        from click.testing import CliRunner

        from probe.cli import main

        setup = (
            "CREATE TABLE u (id INT, val TEXT);"
            " INSERT INTO u VALUES (1,'a'),(2,'b');"
            "CREATE TABLE d (id INT, val TEXT);"
            " INSERT INTO d VALUES (1,'a'),(2,'b')"
        )
        runner = CliRunner()
        result = runner.invoke(main, [
            "verify",
            "--setup", setup,
            "--upstream", "SELECT * FROM u",
            "--downstream", "SELECT * FROM d",
            "--key", "id",
        ])
        assert result.exit_code == 0
        assert "verified" in result.output

    def test_verify_killed_exits_nonzero(self):
        from click.testing import CliRunner

        from probe.cli import main

        setup = (
            "CREATE TABLE u (id INT, a TEXT, b TEXT);"
            " INSERT INTO u VALUES (1,'x','y'),(2,'m','n');"
            "CREATE TABLE d (id INT, a TEXT);"
            " INSERT INTO d VALUES (1,'y'),(2,'n')"
        )
        runner = CliRunner()
        result = runner.invoke(main, [
            "verify",
            "--setup", setup,
            "--upstream", "SELECT * FROM u",
            "--downstream", "SELECT * FROM d",
            "--key", "id",
            "--map", "a=a",
        ])
        assert result.exit_code == 1
        assert "killed" in result.output
        assert "real_parent: b" in result.output
