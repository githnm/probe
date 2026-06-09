"""Probes: row_count, grain, null_rate, column_presence."""

from __future__ import annotations

from typing import Any

from probe import ProbeResult, Receipt
from probe.db import Adapter


def row_count(adapter: Adapter, old_sql: str, new_sql: str, key: Any = None) -> ProbeResult:
    old_query = f"SELECT COUNT(*) AS cnt FROM ({old_sql}) _t"
    new_query = f"SELECT COUNT(*) AS cnt FROM ({new_sql}) _t"
    old_cnt = adapter.run(old_query)[0]["cnt"]
    new_cnt = adapter.run(new_query)[0]["cnt"]
    delta = new_cnt - old_cnt
    return ProbeResult(
        name="row_count",
        question="Did the row count change?",
        old_value=old_cnt,
        new_value=new_cnt,
        delta=delta,
        status="ok" if delta == 0 else "changed",
        receipt=Receipt(sql=new_query, result={"old": old_cnt, "new": new_cnt}),
    )


def grain(adapter: Adapter, old_sql: str, new_sql: str, key: Any = None) -> ProbeResult:
    if key is None:
        return ProbeResult(
            name="grain",
            question="Is the grain (uniqueness on key) preserved?",
            old_value=None,
            new_value=None,
            delta=None,
            status="unverified",
            receipt=Receipt(sql="", result="no key provided"),
        )
    query = (
        f"SELECT COUNT(*) AS total, COUNT(DISTINCT {key}) AS uniq"
        f" FROM ({{sql}}) _t"
    )
    old_query = query.format(sql=old_sql)
    new_query = query.format(sql=new_sql)
    old_row = adapter.run(old_query)[0]
    new_row = adapter.run(new_query)[0]
    old_dup = old_row["total"] - old_row["uniq"]
    new_dup = new_row["total"] - new_row["uniq"]
    delta = new_dup - old_dup
    return ProbeResult(
        name="grain",
        question="Is the grain (uniqueness on key) preserved?",
        old_value={"total": old_row["total"], "distinct": old_row["uniq"], "duplicates": old_dup},
        new_value={"total": new_row["total"], "distinct": new_row["uniq"], "duplicates": new_dup},
        delta=delta,
        status="ok" if delta == 0 else "changed",
        receipt=Receipt(sql=new_query, result={"old": dict(old_row), "new": dict(new_row)}),
    )


def null_rate(adapter: Adapter, old_sql: str, new_sql: str, key: Any = None) -> ProbeResult:
    old_col_names = [name for name, _ in adapter.columns(old_sql)]
    new_col_names = [name for name, _ in adapter.columns(new_sql)]
    shared = [c for c in old_col_names if c in new_col_names]

    def _null_pcts(sql: str, cols: list[str]) -> tuple[str, dict[str, float]]:
        exprs = ", ".join(
            f"ROUND(SUM(CASE WHEN {c} IS NULL THEN 1 ELSE 0 END) * 100.0"
            f" / NULLIF(COUNT(*), 0), 2) AS {c}"
            for c in cols
        )
        q = f"SELECT {exprs} FROM ({sql}) _t"
        row = adapter.run(q)[0]
        return q, {c: float(row[c]) if row[c] is not None else 0.0 for c in cols}

    old_query, old_pcts = _null_pcts(old_sql, shared)
    new_query, new_pcts = _null_pcts(new_sql, shared)
    delta = {c: round(new_pcts.get(c, 0.0) - old_pcts.get(c, 0.0), 2) for c in shared}
    changed = any(d != 0 for d in delta.values())
    return ProbeResult(
        name="null_rate",
        question="Did null rates change?",
        old_value=old_pcts,
        new_value=new_pcts,
        delta=delta,
        status="ok" if not changed else "changed",
        receipt=Receipt(sql=new_query, result={"old": old_pcts, "new": new_pcts}),
    )


def column_presence(
    adapter: Adapter, old_sql: str, new_sql: str, key: Any = None
) -> ProbeResult:
    old_cols = adapter.columns(old_sql)
    new_cols = adapter.columns(new_sql)
    old_names = [name for name, _ in old_cols]
    new_names = [name for name, _ in new_cols]
    added = [n for n in new_names if n not in old_names]
    removed = [n for n in old_names if n not in new_names]
    delta = {"added": added, "removed": removed}
    changed = bool(added or removed)
    return ProbeResult(
        name="column_presence",
        question="Were columns added or removed?",
        old_value=old_names,
        new_value=new_names,
        delta=delta,
        status="ok" if not changed else "changed",
        receipt=Receipt(
            sql=f"SELECT * FROM ({new_sql}) _t LIMIT 0",
            result={"old_columns": old_names, "new_columns": new_names},
        ),
    )
