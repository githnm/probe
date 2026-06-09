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
@click.option("--key", default=None, help="Column name for grain probe.")
@click.option("--manifest", "manifest_path", default=None, help="Path to dbt manifest.json.")
@click.option("--model", default=None, help="Changed model name (used with --manifest).")
@click.option("--explain", "explain", is_flag=True, help="Add LLM explanation of findings.")
def diff(old, new, db_url, fmt, setup_sql, key, manifest_path, model, explain):
    """Compare before/after SQL and report findings."""
    from probe.db import DuckDBAdapter
    from probe.diff import run_diff
    from probe.report import render_markdown, render_terminal

    old_sql = _read_sql(old)
    new_sql = _read_sql(new)

    scope_columns = None
    if manifest_path:
        from probe.lineage import load_manifest

        graph = load_manifest(manifest_path)
        if model:
            model_id = graph.resolve(model)
            if model_id:
                scope_columns = graph.impacted_columns(model_id)

    adapter = DuckDBAdapter.connect(db_url)
    try:
        if setup_sql:
            for stmt in _read_sql(setup_sql).split(";"):
                stmt = stmt.strip()
                if stmt:
                    adapter.run(stmt)
        report = run_diff(
            adapter, old_sql, new_sql, key=key, scope_columns=scope_columns
        )
    finally:
        adapter.close()

    if explain:
        from probe.orchestrate import explain_report, get_llm_client

        client = get_llm_client()
        if client:
            try:
                report.explanation = explain_report(report, client)
            except ImportError as e:
                click.echo(f"Error: {e}", err=True)
                raise SystemExit(1)
        else:
            click.echo("Warning: --explain requires ANTHROPIC_API_KEY or OPENAI_API_KEY", err=True)

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
