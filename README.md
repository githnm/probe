# Probe

A SQL reviewer that runs an AI-written SQL change against real data and reports what changed, with proof.

## Quickstart

```bash
git clone <repo-url> && cd Probe
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install duckdb

# Seed the example database (orders + customer_addresses)
python examples/seed.py

# Run probe diff: the new query joins a one-to-many table, fanning out rows
probe diff --db examples/shop.duckdb --old @examples/old.sql --new @examples/new.sql
```

Probe detects the fan-out (5 → 11 rows), flags the new columns (`address_type`, `city`),
and exits with code 1 (`block` severity). Every finding includes a receipt — the exact SQL
and the numbers it measured.

## Usage

```bash
probe --help
probe diff --help

# Inline SQL
probe diff --setup "CREATE TABLE t (x INT); INSERT INTO t VALUES (1),(2)" \
           --old "SELECT * FROM t" \
           --new "SELECT * FROM t WHERE x = 1"

# Markdown output
probe diff --db examples/shop.duckdb --old @examples/old.sql --new @examples/new.sql --format markdown
```

## Running tests

```bash
pip install pytest ruff
pytest
ruff check .
```

## License

Apache-2.0
