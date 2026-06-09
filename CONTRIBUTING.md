# Contributing to Probe

Thanks for your interest in Probe! This guide will help you get started.

## Getting started

```bash
git clone https://github.com/githnm/probe.git && cd probe
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest && ruff check .
```

All tests should pass before you start.

## Development workflow

1. **Pick an issue** or open one describing what you want to change.
2. **Create a branch** from `main`.
3. **Write the test first.** A task is done only when its test passes. See Hard Rule 3 in `CLAUDE.md`.
4. **Implement the change.**
5. **Run the checks:**
   ```bash
   pytest
   ruff check .
   probe-bench
   ```
6. **Open a PR.** Describe what changed and why. Include the probe output or test output if relevant.

## Architecture

Probe has a deterministic core and an optional LLM layer on top. See `CLAUDE.md` for the full spec.

- **Probes** (`probe/probes.py`) are pure functions: `(adapter, old_sql, new_sql, key) -> ProbeResult`. Each wraps the user SQL as a subquery — probes never write to the database.
- **Adapters** (`probe/db.py`) implement the `Adapter` protocol: `run(sql)`, `columns(sql)`, `close()`.
- **Severity** (`probe/severity.py`) maps probe results to `info`/`warn`/`block`.
- **Receipts** are non-negotiable. Every finding must carry the SQL that produced it and the number it got. Never mark something `ok` without measurement — use `unverified` instead.

## Adding a new probe

1. Add a function to `probe/probes.py` with the signature `(adapter, old_sql, new_sql, key=None) -> ProbeResult`.
2. Register it in `ALL_PROBES` in `probe/diff.py`.
3. Add a severity rule in `probe/severity.py`.
4. Write tests in `tests/test_probes.py`.
5. Add a seed case in `tests/seeds/` and verify `probe-bench` still passes.

## Adding a new adapter

1. Add a class to `probe/db.py` that satisfies the `Adapter` protocol.
2. Write tests (see `tests/test_postgres.py` for the skip pattern for external databases).
3. Wire it into `probe/cli.py` and `entrypoint.py`.

## Hard rules

These are enforced in code review:

1. **Deterministic core, LLM on top.** Probes, diff, severity, and lineage never call the network.
2. **Receipt contract.** Never assert a data fact without a measured number.
3. **Test-first.** Write the test with the code.
4. **Bounded agent loop.** The agent loop has a hard round cap and always falls back.

## Code style

- Python 3.11+
- Ruff for linting (config in `pyproject.toml`)
- No comments unless the *why* is non-obvious
- No unnecessary abstractions

## Postgres tests

Postgres tests are skipped by default. To run them locally:

```bash
docker run -d --name probe-pg -e POSTGRES_USER=probe -e POSTGRES_PASSWORD=probe \
  -e POSTGRES_DB=probe_test -p 5432:5432 postgres:16
export PROBE_PG_URL="postgresql://probe:probe@localhost:5432/probe_test"
pytest
```

## License

By contributing, you agree that your contributions will be licensed under the Apache-2.0 License.
