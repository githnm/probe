"""GitHub Action entrypoint for Probe."""

import json
import os
import sys


def main() -> None:
    old_sql = _read_input("INPUT_OLD_SQL")
    new_sql = _read_input("INPUT_NEW_SQL")
    db_url = os.environ["INPUT_DB_URL"]
    adapter_type = os.environ.get("INPUT_ADAPTER", "duckdb")
    key = os.environ.get("INPUT_KEY", "") or None
    manifest_path = os.environ.get("INPUT_MANIFEST", "") or None
    model_name = os.environ.get("INPUT_MODEL", "") or None
    explain = os.environ.get("INPUT_EXPLAIN", "false").lower() == "true"
    token = os.environ.get("GITHUB_TOKEN", "")

    from probe.diff import run_diff

    scope_columns = None
    if manifest_path:
        from probe.lineage import load_manifest

        graph = load_manifest(manifest_path)
        if model_name:
            model_id = graph.resolve(model_name)
            if model_id:
                scope_columns = graph.impacted_columns(model_id)

    if adapter_type == "postgres":
        from probe.db import PostgresAdapter

        adapter = PostgresAdapter.connect(db_url)
    else:
        from probe.db import DuckDBAdapter

        adapter = DuckDBAdapter.connect(db_url)

    try:
        report = run_diff(adapter, old_sql, new_sql, key=key, scope_columns=scope_columns)
    finally:
        adapter.close()

    if explain:
        from probe.orchestrate import explain_report, get_llm_client

        client = get_llm_client()
        if client:
            report.explanation = explain_report(report, client)

    from probe.comment import format_comment, post_comment
    from probe.report import render_terminal

    print(render_terminal(report))

    github_output = os.environ.get("GITHUB_OUTPUT", "")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"severity={report.severity}\n")

    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number = _get_pr_number(event_path)

    if token and repo and pr_number:
        body = format_comment(report)
        result = post_comment(body, repo, pr_number, token)
        comment_id = result.get("id", "")
        print(f"Posted comment {comment_id} on {repo}#{pr_number}")
        if github_output:
            with open(github_output, "a") as f:
                f.write(f"comment-id={comment_id}\n")
    else:
        print("Skipping PR comment (not in a PR context or no token).")

    if report.severity == "block":
        print("::error::Probe found blocking findings (severity: block)")
        sys.exit(1)


def _read_input(env_var: str) -> str:
    value = os.environ.get(env_var, "")
    if value.startswith("@"):
        with open(value[1:]) as f:
            return f.read()
    return value


def _get_pr_number(event_path: str) -> int | None:
    if not event_path or not os.path.exists(event_path):
        return None
    with open(event_path) as f:
        event = json.load(f)
    pr = event.get("pull_request") or event.get("issue", {})
    return pr.get("number")


if __name__ == "__main__":
    main()
