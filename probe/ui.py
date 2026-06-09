"""Streamlit UI for Probe — thin layer over existing probe modules."""

from __future__ import annotations

import os
import sys

EXAMPLES = [
    {
        "name": "Fan-out — revenue doubles",
        "db": ":memory:",
        "setup_sql": (
            "CREATE TABLE orders (order_id INT, amount DOUBLE);\n"
            "INSERT INTO orders VALUES (1, 100.0), (2, 200.0), (3, 150.0);\n"
            "CREATE TABLE addr (order_id INT, city TEXT);\n"
            "INSERT INTO addr VALUES"
            " (1, 'NYC'), (1, 'Boston'),"
            " (2, 'Chicago'), (2, 'Denver'),"
            " (3, 'Seattle'), (3, 'Portland')"
        ),
        "old_sql": "SELECT order_id, amount FROM orders",
        "new_sql": (
            "SELECT o.order_id, o.amount, a.city\n"
            "FROM orders o JOIN addr a ON o.order_id = a.order_id"
        ),
        "key": "order_id",
        "metrics": "amount",
        "explain": False,
    },
    {
        "name": "Safe refactor — no change",
        "db": ":memory:",
        "setup_sql": (
            "CREATE TABLE orders (order_id INT, amount DOUBLE);\n"
            "INSERT INTO orders VALUES (1, 100.0), (2, 200.0), (3, 150.0)"
        ),
        "old_sql": "SELECT order_id, amount FROM orders WHERE amount > 0",
        "new_sql": (
            "WITH base AS (SELECT order_id, amount FROM orders WHERE amount > 0)\n"
            "SELECT * FROM base"
        ),
        "key": "order_id",
        "metrics": "amount",
        "explain": False,
    },
    {
        "name": "Row drop — LEFT to INNER",
        "db": ":memory:",
        "setup_sql": (
            "CREATE TABLE orders (order_id INT, customer_id INT, amount DOUBLE);\n"
            "INSERT INTO orders VALUES (1, 10, 50.0), (2, 20, 75.0), (3, NULL, 30.0);\n"
            "CREATE TABLE customers (customer_id INT, name TEXT);\n"
            "INSERT INTO customers VALUES (10, 'Alice'), (20, 'Bob')"
        ),
        "old_sql": (
            "SELECT o.order_id, o.amount, c.name\n"
            "FROM orders o LEFT JOIN customers c ON o.customer_id = c.customer_id"
        ),
        "new_sql": (
            "SELECT o.order_id, o.amount, c.name\n"
            "FROM orders o INNER JOIN customers c ON o.customer_id = c.customer_id"
        ),
        "key": "order_id",
        "metrics": "amount",
        "explain": False,
    },
    {
        "name": "Honest unknown — no key",
        "db": ":memory:",
        "setup_sql": (
            "CREATE TABLE orders (order_id INT, amount DOUBLE);\n"
            "INSERT INTO orders VALUES (1, 100.0), (2, 200.0), (3, 150.0);\n"
            "CREATE TABLE addr (order_id INT, city TEXT);\n"
            "INSERT INTO addr VALUES"
            " (1, 'NYC'), (1, 'Boston'),"
            " (2, 'Chicago'), (2, 'Denver'),"
            " (3, 'Seattle'), (3, 'Portland')"
        ),
        "old_sql": "SELECT order_id, amount FROM orders",
        "new_sql": (
            "SELECT o.order_id, o.amount, a.city\n"
            "FROM orders o JOIN addr a ON o.order_id = a.order_id"
        ),
        "key": "",
        "metrics": "amount",
        "explain": False,
    },
]


def main() -> None:
    """Launch the Streamlit app."""
    app_path = os.path.abspath(__file__)
    os.execvp("streamlit", ["streamlit", "run", app_path, "--server.headless=false"])


def _init_state(st) -> None:
    defaults = {
        "s_db_path": ":memory:",
        "s_manifest_path": "",
        "s_setup_sql": "",
        "s_key_col": "",
        "s_metric_cols": "",
        "s_old_sql": "",
        "s_new_sql": "",
        "s_explain": False,
        "s_example": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _load_example(st) -> None:
    name = st.session_state.get("s_example", "")
    if not name:
        return
    ex = next((e for e in EXAMPLES if e["name"] == name), None)
    if ex is None:
        return
    st.session_state["s_db_path"] = ex["db"]
    st.session_state["s_setup_sql"] = ex["setup_sql"]
    st.session_state["s_old_sql"] = ex["old_sql"]
    st.session_state["s_new_sql"] = ex["new_sql"]
    st.session_state["s_key_col"] = ex["key"]
    st.session_state["s_metric_cols"] = ex["metrics"]
    st.session_state["s_explain"] = ex["explain"]


def _app() -> None:
    import pandas as pd
    import streamlit as st

    from probe.db import DuckDBAdapter

    st.set_page_config(page_title="Probe", page_icon="🔍", layout="wide")
    _init_state(st)
    st.title("🔍 Probe — SQL Reviewer")

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("Settings")
        db_path = st.text_input("DuckDB path", key="s_db_path")
        manifest_path = st.text_input("dbt manifest.json path", key="s_manifest_path")
        setup_sql = st.text_area(
            "Setup SQL (optional)", height=80,
            placeholder="CREATE TABLE ...", key="s_setup_sql",
        )
        key_col = st.text_input("Key column (for grain probe)", key="s_key_col")
        metric_cols = st.text_input(
            "Metric columns (comma-separated)", key="s_metric_cols",
        )

    # ── Load manifest ────────────────────────────────────────────────────
    graph = None
    if manifest_path and os.path.exists(manifest_path):
        from probe.lineage import load_manifest

        graph = load_manifest(manifest_path)

    # ── Tabs ─────────────────────────────────────────────────────────────
    tab_tables, tab_lineage, tab_diff, tab_verify = st.tabs(
        ["Tables", "Lineage", "Diff", "Verify"]
    )

    # ── Tables tab ───────────────────────────────────────────────────────
    with tab_tables:
        _render_tables_tab(st, pd, db_path, setup_sql, DuckDBAdapter)

    # ── Lineage tab ──────────────────────────────────────────────────────
    selected_id = None
    with tab_lineage:
        if graph is None:
            st.info(
                "Load a dbt manifest.json in the sidebar to view the lineage graph."
            )
        else:
            model_names = ["(none)"] + sorted(graph.nodes())
            selected = st.selectbox(
                "Select a model to highlight impact", model_names
            )

            highlight: set[str] = set()
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
        example_names = [""] + [e["name"] for e in EXAMPLES]
        st.selectbox(
            "Load example",
            example_names,
            key="s_example",
            on_change=_load_example,
            args=(st,),
        )

        col1, col2 = st.columns(2)
        with col1:
            old_sql = st.text_area(
                "Old SQL", height=200,
                placeholder="SELECT * FROM orders",
                key="s_old_sql",
            )
        with col2:
            new_sql = st.text_area(
                "New SQL", height=200,
                placeholder="SELECT * FROM orders ...",
                key="s_new_sql",
            )

        explain_check = st.checkbox(
            "Explain (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)",
            key="s_explain",
        )

        if st.button("Run Probe Diff", type="primary"):
            if not old_sql.strip() or not new_sql.strip():
                st.warning("Enter both old and new SQL.")
            else:
                _run_diff(
                    st, pd, db_path, setup_sql, old_sql, new_sql,
                    key_col or None,
                    [m.strip() for m in metric_cols.split(",") if m.strip()]
                    or None,
                    graph, selected_id if graph else None,
                    explain_check, DuckDBAdapter,
                )

    # ── Verify tab ────────────────────────────────────────────────────────
    with tab_verify:
        model_names_v = sorted(graph.nodes()) if graph else []

        if model_names_v:
            vc1, vc2 = st.columns(2)
            with vc1:
                up_model = st.selectbox(
                    "Upstream model (optional)", ["(custom)"] + model_names_v,
                    key="verify_up_model",
                )
            with vc2:
                down_model = st.selectbox(
                    "Downstream model (optional)", ["(custom)"] + model_names_v,
                    key="verify_down_model",
                )
            up_default = (
                f"SELECT * FROM {up_model}" if up_model != "(custom)" else ""
            )
            down_default = (
                f"SELECT * FROM {down_model}" if down_model != "(custom)" else ""
            )
        else:
            up_default = ""
            down_default = ""

        vq1, vq2 = st.columns(2)
        with vq1:
            v_up_sql = st.text_area(
                "Upstream query", height=150, value=up_default,
                key="verify_up_sql",
            )
        with vq2:
            v_down_sql = st.text_area(
                "Downstream query", height=150, value=down_default,
                key="verify_down_sql",
            )

        v_mappings_str = st.text_input(
            "Column mappings (optional, down=up, comma-separated)",
            value="", key="verify_mappings",
        )

        if st.button("Run Verify", type="primary", key="verify_run"):
            if not v_up_sql.strip() or not v_down_sql.strip():
                st.warning("Enter both upstream and downstream queries.")
            elif not key_col:
                st.warning("Enter a key column in the sidebar.")
            else:
                v_mappings = None
                if v_mappings_str.strip():
                    v_mappings = {}
                    for pair in v_mappings_str.split(","):
                        pair = pair.strip()
                        if "=" in pair:
                            d, u = pair.split("=", 1)
                            v_mappings[d.strip()] = u.strip()
                _run_verify(
                    st, db_path, setup_sql,
                    v_up_sql, v_down_sql, key_col, v_mappings,
                    DuckDBAdapter,
                )


# ── Tables tab renderer ─────────────────────────────────────────────────


def _render_tables_tab(st, pd, db_path, setup_sql, adapter_cls):
    adapter = adapter_cls.connect(db_path)
    try:
        if setup_sql and setup_sql.strip():
            for stmt in setup_sql.split(";"):
                s = stmt.strip()
                if s:
                    adapter.run(s)
        tables = adapter.run(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        )
    except Exception as e:
        st.error(f"Error connecting to database: {e}")
        return
    finally:
        adapter.close()

    if not tables:
        st.info(
            "No tables found. If using `:memory:`, add Setup SQL in the sidebar "
            "to create tables, or point the DuckDB path at a `.duckdb` file."
        )
        return

    # Reopen for previews (adapter was closed to release the lock)
    adapter = adapter_cls.connect(db_path)
    try:
        if setup_sql and setup_sql.strip():
            for stmt in setup_sql.split(";"):
                s = stmt.strip()
                if s:
                    adapter.run(s)

        st.subheader(f"{len(tables)} table(s)")
        for row in tables:
            tname = row["table_name"]
            cnt = adapter.run(f'SELECT COUNT(*) AS n FROM "{tname}"')[0]["n"]
            with st.expander(f"**{tname}** — {cnt} rows"):
                preview = adapter.run(f'SELECT * FROM "{tname}" LIMIT 50')
                if preview:
                    st.dataframe(pd.DataFrame(preview), use_container_width=True)
                else:
                    st.caption("Table is empty.")
    finally:
        adapter.close()


# ── Lineage DOT builder ─────────────────────────────────────────────────


def _build_dot(graph, highlight: set[str], selected: str) -> str:
    lines = [
        "digraph {",
        '  rankdir=LR;',
        '  node [shape=box, style=filled, fillcolor="#f0f0f0",'
        ' fontname="Helvetica"];',
        '  edge [color="#888888"];',
    ]
    for name in graph.nodes():
        if name == selected:
            lines.append(
                f'  "{name}" [fillcolor="#ff6b6b", fontcolor="white"];'
            )
        elif name in highlight:
            lines.append(f'  "{name}" [fillcolor="#ffa94d"];')
    for parent, child in graph.edges():
        lines.append(f'  "{parent}" -> "{child}";')
    lines.append("}")
    return "\n".join(lines)


# ── Diff runner ──────────────────────────────────────────────────────────


def _run_diff(
    st, pd, db_path, setup_sql, old_sql, new_sql,
    key, metrics, graph, selected_model_id, explain, adapter_cls,
) -> None:
    from probe.diff import run_diff

    scope_columns = None
    if graph and selected_model_id:
        scope_columns = graph.impacted_columns(selected_model_id)

    adapter = adapter_cls.connect(db_path)
    try:
        if setup_sql and setup_sql.strip():
            for stmt in setup_sql.split(";"):
                s = stmt.strip()
                if s:
                    adapter.run(s)

        # ── Result previews ──────────────────────────────────────────
        st.subheader("Preview")
        pc1, pc2 = st.columns(2)
        with pc1:
            st.caption("Old result (first 50 rows)")
            try:
                old_rows = adapter.run(
                    f"SELECT * FROM ({old_sql}) _t LIMIT 50"
                )
                st.dataframe(
                    pd.DataFrame(old_rows), use_container_width=True,
                )
            except Exception as e:
                st.error(f"Old query error: {e}")
        with pc2:
            st.caption("New result (first 50 rows)")
            try:
                new_rows = adapter.run(
                    f"SELECT * FROM ({new_sql}) _t LIMIT 50"
                )
                st.dataframe(
                    pd.DataFrame(new_rows), use_container_width=True,
                )
            except Exception as e:
                st.error(f"New query error: {e}")

        # ── Run probes ───────────────────────────────────────────────
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
            st.warning(
                "No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
            )

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
        status_icon = {
            "ok": "✅", "changed": "🔶", "unverified": "❓"
        }.get(r.status, "")
        with st.container(border=True):
            st.markdown(f"**{status_icon} {r.name}** — {r.question}")
            old_str = _summarize(r.old_value)
            new_str = _summarize(r.new_value)
            delta_str = _summarize(r.delta)
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"**Old:** {old_str}")
            c2.markdown(f"**New:** {new_str}")
            c3.markdown(f"**Delta:** {delta_str}")
            st.caption(f"Status: {r.status}")
            with st.expander("Receipt"):
                if r.receipt.sql:
                    st.code(r.receipt.sql, language="sql")
                if isinstance(r.receipt.result, (dict, list)):
                    st.json(r.receipt.result)
                else:
                    st.text(str(r.receipt.result))


# ── Verify runner ────────────────────────────────────────────────────────


def _run_verify(st, db_path, setup_sql, up_sql, down_sql, key, mappings, adapter_cls):
    from probe.verify import verify

    adapter = adapter_cls.connect(db_path)
    try:
        if setup_sql and setup_sql.strip():
            for stmt in setup_sql.split(";"):
                s = stmt.strip()
                if s:
                    adapter.run(s)
        results = verify(adapter, up_sql, down_sql, key, mappings=mappings)
    except Exception as e:
        st.error(f"Error running verify: {e}")
        return
    finally:
        adapter.close()

    if not results:
        st.info("No column edges to verify (no shared columns found).")
        return

    # ── Summary ──────────────────────────────────────────────────────
    n_verified = sum(1 for r in results if r.verdict == "verified")
    n_killed = sum(1 for r in results if r.verdict == "killed")
    n_unverified = sum(1 for r in results if r.verdict == "unverified")
    st.markdown(
        f"**{n_verified} verified** · "
        f"**{n_killed} killed** · "
        f"**{n_unverified} unverified**"
    )

    # ── Edge cards ───────────────────────────────────────────────────
    verdict_color = {"verified": "green", "killed": "red", "unverified": "orange"}
    verdict_icon = {"verified": "✅", "killed": "❌", "unverified": "❓"}
    for r in results:
        icon = verdict_icon.get(r.verdict, "")
        color = verdict_color.get(r.verdict, "gray")
        with st.container(border=True):
            st.markdown(
                f"**{icon} `{r.downstream_col}` ← `{r.claimed_parent}`** — "
                f'<span style="color:{color};font-weight:bold">'
                f"{r.verdict}</span>",
                unsafe_allow_html=True,
            )
            if r.match_rate is not None:
                st.markdown(f"Match rate: **{r.match_rate}%**")
            if r.real_parent:
                st.markdown(
                    f"Suggested real parent: **`{r.real_parent}`**"
                )
            with st.expander("Receipt"):
                if r.receipt.sql:
                    st.code(r.receipt.sql, language="sql")
                if isinstance(r.receipt.result, (dict, list)):
                    st.json(r.receipt.result)
                else:
                    st.text(str(r.receipt.result))


def _summarize(value: object) -> str:
    if value is None:
        return "—"
    if isinstance(value, dict):
        parts = [f"{k}: {v}" for k, v in value.items()]
        if len(parts) <= 3:
            return ", ".join(parts)
        return ", ".join(parts[:3]) + f" (+{len(parts) - 3} more)"
    if isinstance(value, list):
        if len(value) <= 4:
            return ", ".join(str(v) for v in value)
        return ", ".join(str(v) for v in value[:3]) + f" (+{len(value) - 3} more)"
    return str(value)


# Streamlit runs this file as a script — detect that and call _app()
if __name__ == "__main__" or "streamlit" in sys.modules:
    import inspect

    if any("streamlit" in str(f.filename) for f in inspect.stack()):
        _app()
    elif __name__ == "__main__":
        main()
