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
