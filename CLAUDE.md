# Probe

## Purpose

A SQL reviewer that runs an AI-written SQL change against real data and reports what changed, with proof.

## Scope

### In

- `probe diff` CLI that compares before/after SQL and reports findings
- DuckDB and Postgres database adapters
- Four probes: row count, grain (uniqueness), null rate, column presence
- dbt lineage scoping to identify impacted downstream models
- Bounded agent loop that picks and refines probes based on the SQL change
- Severity gating config (info / warn / block)
- GitHub Action that comments probe results on PRs
- Optional LLM explanation of findings

### Out

- Snowflake, BigQuery adapters
- Any write access to databases
- Lineage verifier (trust dbt manifest, don't re-derive)

## Hard Rules

1. **Deterministic core, LLM on top.** Probes, diff, severity, and lineage never call the network. Only the agent loop and the explanation step may call an LLM.
2. **Receipt contract.** Every finding carries the exact query that produced it and the number it got. Never assert a data fact without a measured number. Mark anything unmeasured as `unverified`, never `ok`.
3. **Test-first.** Write the test with the code. A task is done only when its check passes.
4. **Bounded agent loop.** The agent loop has a hard round cap (default 5). If it exhausts rounds or errors, it falls back to running all probes unconditionally.

## Data Shapes

```python
@dataclass
class Receipt:
    sql: str
    result: Any  # the raw value returned by the query

@dataclass
class ProbeResult:
    name: str           # e.g. "row_count", "grain", "null_rate", "column_presence"
    question: str       # human-readable question this probe answers
    old_value: Any
    new_value: Any
    delta: Any          # new_value - old_value, or structural diff
    status: str         # "ok" | "changed" | "unverified"
    receipt: Receipt    # the SQL and raw result that back this finding

@dataclass
class Report:
    results: list[ProbeResult]
    severity: str       # "info" | "warn" | "block"
    scope: list[str]    # impacted column names
```

### Adapter Protocol

Every adapter implements:

- `connect(url: str) -> Connection`
- `run(sql: str) -> list[dict]` — execute SQL, return rows as dicts
- `columns(sql: str) -> list[tuple[str, str]]` — return `[(name, type)]` via `SELECT * FROM (<sql>) _t LIMIT 0`

Every probe wraps the user SQL as a subquery — probes never modify the database.

## Module Map

```
probe/
├── __init__.py       # package root, version
├── cli.py            # click CLI: `probe diff`
├── db.py             # adapter protocol + DuckDB/Postgres implementations
├── probes.py         # row_count, grain, null_rate, column_presence probes
├── lineage.py        # dbt manifest parser, downstream model discovery
├── orchestrate.py    # bounded agent loop: pick probes, refine, fallback
├── severity.py       # severity gating: map probe results -> info/warn/block
├── policy.py         # user config for thresholds and rules
├── report.py         # Report assembly and formatting (markdown, JSON)
├── comment.py        # GitHub PR comment poster
tests/
├── __init__.py
├── test_db.py
├── test_probes.py
├── test_lineage.py
├── test_orchestrate.py
├── test_severity.py
├── test_policy.py
├── test_report.py
├── test_comment.py
├── test_cli.py
```

## Milestones

- **M0**: Project scaffold — pyproject.toml, CI, empty modules, `probe --help` works
- **M1**: Adapter protocol + DuckDB adapter with `connect`, `run`, `columns`
- **M2**: Row count probe — wraps SQL as subquery, returns ProbeResult with receipt
- **M3**: Grain probe — checks uniqueness of key columns
- **M4**: Null rate probe — measures null fraction per column
- **M5**: Column presence probe — detects added/removed columns
- **M6**: Severity gating — map ProbeResult list to info/warn/block
- **M7**: Policy config — YAML-based threshold and rule configuration
- **M8**: Report assembly — markdown and JSON output from ProbeResult list
- **M9**: `probe diff` CLI end-to-end with DuckDB
- **M10**: Postgres adapter
- **M11**: dbt lineage scoping — parse manifest.json, find impacted models
- **M12**: Bounded agent loop — LLM picks probes, refines, hard round cap, fallback
- **M13**: GitHub Action + PR comment poster
