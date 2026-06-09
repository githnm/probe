# Probe

A SQL reviewer that runs an AI-written SQL change against real data and reports what changed, with proof.

```
[X] Probe Report  (severity: block)
    scope: address_type, city

  [~] row_count: Did the row count change?
      old: 5
      new: 11
      delta: 6  (status: changed)
      receipt:
        sql: SELECT COUNT(*) AS cnt FROM (...new query...) _t
        result: {'old': 5, 'new': 11}

  [~] grain: Is the grain (uniqueness on key) preserved?
      old: {'total': 5, 'distinct': 5, 'duplicates': 0}
      new: {'total': 11, 'distinct': 5, 'duplicates': 6}
      delta: 6  (status: changed)
      receipt:
        sql: SELECT COUNT(*) AS total, COUNT(DISTINCT order_id) AS uniq FROM (...) _t
        result: {'old': {'total': 5, 'uniq': 5}, 'new': {'total': 11, 'uniq': 5}}
```

Every finding carries a **receipt** — the exact SQL that ran and the number it got.
Nothing is asserted without measurement. Probe exits non-zero on `block`, so you can
gate merges on it.

## Quickstart (2 minutes, DuckDB, no server)

Requires pip 21.3+ (the venv upgrade step below handles this).

```bash
git clone https://github.com/githnm/probe.git && cd probe
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e . && pip install duckdb

# Seed a small database: 5 orders + 6 customer addresses (one-to-many)
python examples/seed.py

# The new query joins addresses, fanning out rows and doubling revenue
probe diff \
  --db examples/shop.duckdb \
  --old @examples/old.sql \
  --new @examples/new.sql \
  --key order_id
```

Probe detects the fan-out (5 rows became 11), flags the grain break
(6 duplicate `order_id` values), reports the new columns (`address_type`, `city`),
and exits with code 1. Every finding includes the SQL and numbers that back it.

## How It Works

Probe compares two SQL queries — the old version and the new — by running
deterministic **probes** against real data. No LLM is involved in measurement.

```
old.sql ──┐                  ┌── row_count ──┐
          ├── adapter.run() ─┤── grain ──────┤── severity ── Report
new.sql ──┘                  ├── null_rate ──┤     (with receipts)
                             └── col_presence┘
```

### Probes

| Probe | What it checks | Severity when changed |
|-------|---------------|----------------------|
| `row_count` | `COUNT(*)` old vs new | increase: `block`, decrease: `warn` |
| `grain` | `COUNT(*)` vs `COUNT(DISTINCT key)` | `block` (no key: `unverified`) |
| `null_rate` | `% NULL` per column, old vs new | increase: `warn` |
| `column_presence` | column names added/removed | removed: `block`, added: `info` |
| `metric_sum` | `SUM(col)` per numeric column, old vs new | `warn` (no numerics: `unverified`) |

### Receipt contract

Every `ProbeResult` carries a `Receipt` with the SQL that produced it and the raw
value returned. A finding may never be marked `ok` without a measured number —
anything unmeasured is `unverified`.

### Severity gating

Each probe result maps to `info`, `warn`, or `block`. The overall report severity
is the max. `probe diff` exits non-zero on `block`, so CI can gate merges.

### Optional LLM explanation

Pass `--explain` with an `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to get a
plain-English summary on top of the receipts. Each LLM claim is tagged
`[confirmed]` only if backed by a probe that actually fired — unbacked claims
are tagged `[unconfirmed]`. Without an API key, the tool runs normally and
prints receipts only.

## Usage

```bash
# Inline SQL
probe diff \
  --setup "CREATE TABLE t (x INT); INSERT INTO t VALUES (1),(2),(3)" \
  --old "SELECT * FROM t" \
  --new "SELECT * FROM t WHERE x <= 2"

# Against a Postgres warehouse (read-only role)
pip install 'probe[postgres]'
probe diff \
  --old @models/orders_v1.sql \
  --new @models/orders_v2.sql \
  --db "postgresql://readonly:pass@host:5432/warehouse" \
  --key order_id

# Markdown output (for CI comments)
probe diff --db examples/shop.duckdb \
  --old @examples/old.sql --new @examples/new.sql \
  --format markdown

# dbt lineage scoping
probe diff --db warehouse.duckdb \
  --old @old.sql --new @new.sql \
  --manifest target/manifest.json --model stg_orders

# LLM explanation (optional, needs API key + explain extra)
pip install "probe[explain]"
ANTHROPIC_API_KEY=sk-... probe diff --db examples/shop.duckdb \
  --old @examples/old.sql --new @examples/new.sql --explain
```

## GitHub Action

```yaml
- uses: githnm/probe@v0.1.0
  with:
    old-sql: "@models/orders_old.sql"
    new-sql: "@models/orders_new.sql"
    db-url: ${{ secrets.WAREHOUSE_READ_URL }}
    adapter: postgres
    key: order_id
```

The action posts a markdown comment on the PR with receipts, and fails the
check on `block` severity. Warehouse credentials come from repo secrets and
must use a **read-only role**.

## Benchmarks

```bash
# Run the seed benchmark (5 known-answer cases)
python -m tests.bench
```

Current results: **5/5 catch rate, 0 false positives** across fan-out,
row-drop-via-inner-join, grain change, new nulls, and metric shift scenarios.

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

pytest           # 123 tests (Postgres tests need PROBE_PG_URL)
ruff check .     # linter
python -m tests.bench      # seed benchmarks
```

## Roadmap

- [x] M0 — Project scaffold
- [x] M1 — DuckDB adapter
- [x] M2 — Row count probe
- [x] M3 — Grain probe
- [x] M4 — Null rate probe
- [x] M5 — Column presence probe
- [x] M6 — Severity gating
- [ ] M7 — Policy config (YAML-based thresholds and rules)
- [x] M8 — Report assembly (terminal + markdown)
- [x] M9 — `probe diff` CLI end-to-end
- [x] M10 — Postgres adapter
- [x] M11 — dbt lineage scoping
- [x] M12 — LLM explanation (optional)
- [x] M13 — GitHub Action + PR commenter
- [ ] Snowflake adapter
- [ ] BigQuery adapter
- [ ] Value distribution probe (histogram diff)
- [ ] Schema-change probe (type changes)
- [ ] `probe watch` (continuous monitoring)

## License

Apache-2.0
