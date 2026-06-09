"""Streamlit UI for Probe — thin layer over existing probe modules."""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Launch the Streamlit app."""
    app_path = os.path.abspath(__file__)
    os.execvp("streamlit", ["streamlit", "run", app_path, "--server.headless=false"])


def _app() -> None:
    import streamlit as st

    st.set_page_config(page_title="Probe", page_icon="🔍", layout="wide")
    st.title("🔍 Probe — SQL Reviewer")

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Settings")
        db_path = st.text_input("DuckDB path", value=":memory:")
        manifest_path = st.text_input("dbt manifest.json path", value="")
        setup_sql = st.text_area("Setup SQL (optional)", height=80, placeholder="CREATE TABLE ...")
        key_col = st.text_input("Key column (for grain probe)", value="")
        metric_cols = st.text_input("Metric columns (comma-separated)", value="")

    # ── Load manifest ────────────────────────────────────────────────────
    graph = None
    if manifest_path and os.path.exists(manifest_path):
        from probe.lineage import load_manifest

        graph = load_manifest(manifest_path)

    # ── Tabs ─────────────────────────────────────────────────────────────
    tab_lineage, tab_diff = st.tabs(["Lineage", "Diff"])

    # ── Lineage tab ──────────────────────────────────────────────────────
    with tab_lineage:
        if graph is None:
            st.info("Load a dbt manifest.json in the sidebar to view the lineage graph.")
        else:
            model_names = ["(none)"] + sorted(graph.nodes())
            selected = st.selectbox("Select a model to highlight impact", model_names)

            highlight: set[str] = set()
            selected_id = None
            if selected != "(none)":
                selected_id = graph.resolve(selected)
                if selected_id:
                    highlight = {selected}
                    for uid in graph.downstream(selected_id):
                        m = graph.models.get(uid)
                        if m:
                            highlight.add(m.name)

            dot = _build_dot(graph, highlight, selected or "")
            st.graphviz_chart(dot)

            if selected_id:
                cols = graph.impacted_columns(selected_id)
                if cols:
                    st.subheader("Impacted columns")
                    st.write(", ".join(f"`{c}`" for c in cols))
                else:
                    st.caption("No column-level impact detected.")

    # ── Diff tab ─────────────────────────────────────────────────────────
    with tab_diff:
        col1, col2 = st.columns(2)
        with col1:
            old_sql = st.text_area("Old SQL", height=200, placeholder="SELECT * FROM orders")
        with col2:
            new_sql = st.text_area("New SQL", height=200, placeholder="SELECT * FROM orders ...")

        explain_check = st.checkbox(
            "Explain (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)",
            value=False,
        )

        if st.button("Run Probe Diff", type="primary"):
            if not old_sql.strip() or not new_sql.strip():
                st.warning("Enter both old and new SQL.")
            else:
                _run_diff(
                    db_path, setup_sql, old_sql, new_sql,
                    key_col or None,
                    [m.strip() for m in metric_cols.split(",") if m.strip()] or None,
                    graph, selected_id if graph else None,
                    explain_check,
                )


def _build_dot(graph: object, highlight: set[str], selected: str) -> str:
    lines = [
        "digraph {",
        '  rankdir=LR;',
        '  node [shape=box, style=filled, fillcolor="#f0f0f0", fontname="Helvetica"];',
        '  edge [color="#888888"];',
    ]
    for name in graph.nodes():
        if name == selected:
            lines.append(f'  "{name}" [fillcolor="#ff6b6b", fontcolor="white"];')
        elif name in highlight:
            lines.append(f'  "{name}" [fillcolor="#ffa94d"];')
    for parent, child in graph.edges():
        lines.append(f'  "{parent}" -> "{child}";')
    lines.append("}")
    return "\n".join(lines)


def _run_diff(
    db_path: str,
    setup_sql: str,
    old_sql: str,
    new_sql: str,
    key: str | None,
    metrics: list[str] | None,
    graph: object | None,
    selected_model_id: str | None,
    explain: bool,
) -> None:
    import streamlit as st

    from probe.db import DuckDBAdapter
    from probe.diff import run_diff

    scope_columns = None
    if graph and selected_model_id:
        scope_columns = graph.impacted_columns(selected_model_id)

    adapter = DuckDBAdapter.connect(db_path)
    try:
        if setup_sql and setup_sql.strip():
            for stmt in setup_sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    adapter.run(stmt)
        report = run_diff(
            adapter, old_sql, new_sql,
            key=key, scope_columns=scope_columns, metrics=metrics,
        )
    except Exception as e:
        st.error(f"Error running probes: {e}")
        return
    finally:
        adapter.close()

    if explain:
        from probe.orchestrate import explain_report, get_llm_client

        client = get_llm_client()
        if client:
            try:
                report.explanation = explain_report(report, client)
            except ImportError as e:
                st.warning(str(e))
        else:
            st.warning("No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")

    # ── Severity badge ───────────────────────────────────────────────
    sev_colors = {"info": "green", "warn": "orange", "block": "red"}
    sev_labels = {"info": "ℹ️ INFO", "warn": "⚠️ WARN", "block": "❌ BLOCK"}
    color = sev_colors.get(report.severity, "gray")
    label = sev_labels.get(report.severity, report.severity)
    st.markdown(
        f'<h2 style="color:{color}">{label}</h2>',
        unsafe_allow_html=True,
    )
    if report.scope:
        st.caption(f"Scope: {', '.join(report.scope)}")

    # ── Explanation ──────────────────────────────────────────────────
    if report.explanation:
        st.subheader("Explanation")
        st.write(report.explanation.summary)
        for f in report.explanation.findings:
            tag = "✅ confirmed" if f.confirmed else "❓ unconfirmed"
            backed = f" — backed by `{f.backed_by}`" if f.backed_by else ""
            st.markdown(f"- **[{tag}]** {f.claim}{backed}")

    # ── Probe results ────────────────────────────────────────────────
    st.subheader("Probe Results")
    for r in report.results:
        status_icon = {"ok": "✅", "changed": "🔶", "unverified": "❓"}.get(r.status, "")
        with st.container(border=True):
            st.markdown(f"**{status_icon} {r.name}** — {r.question}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Old", str(r.old_value))
            c2.metric("New", str(r.new_value))
            c3.metric("Delta", str(r.delta))
            st.caption(f"Status: {r.status}")
            with st.expander("Receipt"):
                if r.receipt.sql:
                    st.code(r.receipt.sql, language="sql")
                st.json(r.receipt.result) if isinstance(
                    r.receipt.result, (dict, list)
                ) else st.text(str(r.receipt.result))


# Streamlit runs this file as a script — detect that and call _app()
if __name__ == "__main__" or "streamlit" in sys.modules:
    # Only run the app when Streamlit is executing this file, not on import
    import inspect

    if any("streamlit" in str(f.filename) for f in inspect.stack()):
        _app()
    elif __name__ == "__main__":
        main()
