import click

from probe import __version__


@click.group()
@click.version_option(version=__version__, prog_name="probe")
def main():
    """Probe — a SQL reviewer that reports what changed, with proof."""


@main.command()
@click.option("--old", required=True, help="SQL for the old version (query text or @file).")
@click.option("--new", required=True, help="SQL for the new version (query text or @file).")
@click.option("--db", "db_url", default=":memory:", help="DuckDB database path.")
@click.option("--format", "fmt", type=click.Choice(["terminal", "markdown"]), default="terminal")
@click.option("--setup", "setup_sql", default=None, help="SQL to run before probes.")
def diff(old, new, db_url, fmt, setup_sql):
    """Compare before/after SQL and report findings."""
    from probe.db import DuckDBAdapter
    from probe.diff import run_diff
    from probe.report import render_markdown, render_terminal

    old_sql = _read_sql(old)
    new_sql = _read_sql(new)

    adapter = DuckDBAdapter.connect(db_url)
    try:
        if setup_sql:
            for stmt in _read_sql(setup_sql).split(";"):
                stmt = stmt.strip()
                if stmt:
                    adapter.run(stmt)
        report = run_diff(adapter, old_sql, new_sql)
    finally:
        adapter.close()

    if fmt == "markdown":
        click.echo(render_markdown(report))
    else:
        click.echo(render_terminal(report))

    if report.severity == "block":
        raise SystemExit(1)


def _read_sql(value: str) -> str:
    if value.startswith("@"):
        path = value[1:]
        with open(path) as f:
            return f.read()
    return value
