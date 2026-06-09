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
@click.option("--metric", "metrics", multiple=True, help="Numeric column(s) to sum (repeatable).")
@click.option("--explain", "explain", is_flag=True, help="Add LLM explanation of findings.")
def diff(old, new, db_url, fmt, setup_sql, key, manifest_path, model, metrics, explain):
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
        metric_list = _parse_metrics(metrics) or None
        report = run_diff(
            adapter, old_sql, new_sql, key=key,
            scope_columns=scope_columns, metrics=metric_list,
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


@main.command()
@click.option("--upstream", required=True, help="Upstream SQL (query text or @file).")
@click.option("--downstream", required=True, help="Downstream SQL (query text or @file).")
@click.option("--db", "db_url", default=":memory:", help="DuckDB database path.")
@click.option("--key", required=True, help="Join key column.")
@click.option("--setup", "setup_sql", default=None, help="SQL to run before verify.")
@click.option("--map", "mappings_str", default=None, help="Column mappings: down=up,down2=up2.")
def verify(upstream, downstream, db_url, key, setup_sql, mappings_str):
    """Verify claimed lineage edges against real data."""
    from probe.db import DuckDBAdapter
    from probe.verify import verify as run_verify

    up_sql = _read_sql(upstream)
    down_sql = _read_sql(downstream)

    mappings = None
    if mappings_str:
        mappings = {}
        for pair in mappings_str.split(","):
            pair = pair.strip()
            if "=" in pair:
                d, u = pair.split("=", 1)
                mappings[d.strip()] = u.strip()

    adapter = DuckDBAdapter.connect(db_url)
    try:
        if setup_sql:
            for stmt in _read_sql(setup_sql).split(";"):
                stmt = stmt.strip()
                if stmt:
                    adapter.run(stmt)
        results = run_verify(adapter, up_sql, down_sql, key, mappings=mappings)
    finally:
        adapter.close()

    has_killed = False
    for r in results:
        icon = {"verified": ".", "killed": "X", "unverified": "?"}.get(r.verdict, "?")
        click.echo(f"  [{icon}] {r.downstream_col} <- {r.claimed_parent}: {r.verdict}")
        if r.match_rate is not None:
            click.echo(f"      match_rate: {r.match_rate}%")
        if r.real_parent:
            click.echo(f"      real_parent: {r.real_parent}")
        click.echo("      receipt:")
        if r.receipt.sql:
            click.echo(f"        sql: {r.receipt.sql}")
        click.echo(f"        result: {r.receipt.result}")
        if r.verdict == "killed":
            has_killed = True

    if has_killed:
        raise SystemExit(1)


def _parse_metrics(raw: tuple[str, ...]) -> list[str]:
    result = []
    for item in raw:
        for part in item.split(","):
            part = part.strip()
            if part:
                result.append(part)
    return result


def _read_sql(value: str) -> str:
    if value.startswith("@"):
        path = value[1:]
        with open(path) as f:
            return f.read()
    return value
