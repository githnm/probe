---
name: "Good first issue: Add an adapter"
about: Add a new database adapter to Probe (e.g., Snowflake, BigQuery, SQLite).
title: "Add [DATABASE] adapter"
labels: ["good first issue", "enhancement", "new adapter"]
---

## Add a new adapter: `[DATABASE]`

### What it should do

Implement the `Adapter` protocol for [DATABASE]:

```python
class Adapter(Protocol):
    def run(self, sql: str) -> list[dict[str, Any]]: ...
    def columns(self, sql: str) -> list[tuple[str, str]]: ...
    def close(self) -> None: ...
```

The `columns` method must use `SELECT * FROM (<sql>) _t LIMIT 0` to return
`[(name, type)]` without fetching rows.

### Checklist

- [ ] Add the adapter class to `probe/db.py`
- [ ] Add the driver to `[project.optional-dependencies]` in `pyproject.toml`
- [ ] Write tests (see `tests/test_postgres.py` for the skip pattern)
- [ ] Wire it into `probe/cli.py` (add an `--adapter` option or auto-detect from URL)
- [ ] Wire it into `entrypoint.py` for the GitHub Action
- [ ] Verify `isinstance(adapter, Adapter)` passes
- [ ] Adapter must be read-only: never issue DDL or DML

### Resources

- See `CONTRIBUTING.md` for the development workflow
- See `probe/db.py` for `DuckDBAdapter` and `PostgresAdapter` as examples
- See `tests/test_postgres.py` for the skip-when-unavailable test pattern
