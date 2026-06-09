"""Integration test: probe diff on the examples/ fan-out scenario."""

import os

import pytest
from click.testing import CliRunner

from examples.seed import seed
from probe.cli import main

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "examples")
DB_PATH = os.path.join(EXAMPLES_DIR, "shop.duckdb")
OLD_SQL = os.path.join(EXAMPLES_DIR, "old.sql")
NEW_SQL = os.path.join(EXAMPLES_DIR, "new.sql")


@pytest.fixture(autouse=True)
def seeded_db():
    seed(DB_PATH)
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)


def test_fanout_is_block():
    runner = CliRunner()
    result = runner.invoke(main, [
        "diff",
        "--db", DB_PATH,
        "--old", f"@{OLD_SQL}",
        "--new", f"@{NEW_SQL}",
    ])
    assert result.exit_code == 1, result.output
    assert "block" in result.output


def test_row_count_increases():
    runner = CliRunner()
    result = runner.invoke(main, [
        "diff",
        "--db", DB_PATH,
        "--old", f"@{OLD_SQL}",
        "--new", f"@{NEW_SQL}",
    ])
    lines = result.output
    assert "row_count" in lines
    assert "changed" in lines
    # Old table has 5 orders; join fans out to 11 rows
    assert "old: 5" in lines
    assert "new: 11" in lines


def test_receipt_shows_count_query():
    runner = CliRunner()
    result = runner.invoke(main, [
        "diff",
        "--db", DB_PATH,
        "--old", f"@{OLD_SQL}",
        "--new", f"@{NEW_SQL}",
    ])
    assert "COUNT(*)" in result.output
    assert "receipt:" in result.output


def test_new_columns_detected():
    runner = CliRunner()
    result = runner.invoke(main, [
        "diff",
        "--db", DB_PATH,
        "--old", f"@{OLD_SQL}",
        "--new", f"@{NEW_SQL}",
    ])
    assert "address_type" in result.output
    assert "city" in result.output
