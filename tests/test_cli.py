from click.testing import CliRunner

from probe.cli import main


def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Probe" in result.output


def test_version():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_diff_help():
    runner = CliRunner()
    result = runner.invoke(main, ["diff", "--help"])
    assert result.exit_code == 0
    assert "--old" in result.output
    assert "--new" in result.output


def test_diff_no_change():
    runner = CliRunner()
    setup = "CREATE TABLE t (id INT); INSERT INTO t VALUES (1), (2), (3)"
    result = runner.invoke(main, [
        "diff",
        "--setup", setup,
        "--old", "SELECT * FROM t",
        "--new", "SELECT * FROM t",
    ])
    assert result.exit_code == 0
    assert "severity: info" in result.output
    assert "row_count" in result.output
    assert "receipt:" in result.output


def test_diff_block_exits_nonzero():
    runner = CliRunner()
    setup = "CREATE TABLE t (id INT, name TEXT); INSERT INTO t VALUES (1, 'a')"
    result = runner.invoke(main, [
        "diff",
        "--setup", setup,
        "--old", "SELECT * FROM t",
        "--new", "SELECT id FROM t",
    ])
    assert result.exit_code == 1
    assert "severity: block" in result.output


def test_diff_markdown_format():
    runner = CliRunner()
    setup = "CREATE TABLE t (id INT); INSERT INTO t VALUES (1)"
    result = runner.invoke(main, [
        "diff",
        "--format", "markdown",
        "--setup", setup,
        "--old", "SELECT * FROM t",
        "--new", "SELECT * FROM t",
    ])
    assert result.exit_code == 0
    assert "## Probe Report" in result.output
    assert "Receipt" in result.output
