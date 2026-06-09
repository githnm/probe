"""Database adapter protocol and implementations (DuckDB, Postgres)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class QueryBudgetExceeded(Exception):
    def __init__(self, limit: int):
        super().__init__(f"Query budget exceeded: {limit} queries allowed")
        self.limit = limit


@runtime_checkable
class Adapter(Protocol):
    def run(self, sql: str) -> list[dict[str, Any]]: ...
    def columns(self, sql: str) -> list[tuple[str, str]]: ...
    def close(self) -> None: ...


class DuckDBAdapter:
    def __init__(self, conn: Any, max_queries: int | None = None):
        self._conn = conn
        self._max_queries = max_queries
        self._query_count = 0

    @classmethod
    def connect(cls, url: str = ":memory:", *, max_queries: int | None = None) -> DuckDBAdapter:
        import duckdb

        conn = duckdb.connect(url)
        return cls(conn, max_queries=max_queries)

    @property
    def query_count(self) -> int:
        return self._query_count

    def _tick(self) -> None:
        self._query_count += 1
        if self._max_queries is not None and self._query_count > self._max_queries:
            raise QueryBudgetExceeded(self._max_queries)

    def run(self, sql: str) -> list[dict[str, Any]]:
        self._tick()
        result = self._conn.execute(sql)
        cols = [desc[0] for desc in result.description]
        return [dict(zip(cols, row)) for row in result.fetchall()]

    def columns(self, sql: str) -> list[tuple[str, str]]:
        self._tick()
        wrapped = f"SELECT * FROM ({sql}) _t LIMIT 0"
        result = self._conn.execute(wrapped)
        return [(desc[0], desc[1]) for desc in result.description]

    def close(self) -> None:
        self._conn.close()


_PG_TYPE_MAP = {
    16: "BOOLEAN",
    20: "BIGINT",
    21: "SMALLINT",
    23: "INTEGER",
    25: "TEXT",
    700: "REAL",
    701: "DOUBLE PRECISION",
    790: "MONEY",
    1042: "CHAR",
    1043: "VARCHAR",
    1082: "DATE",
    1083: "TIME",
    1114: "TIMESTAMP",
    1184: "TIMESTAMPTZ",
    1700: "NUMERIC",
}


class PostgresAdapter:
    def __init__(self, conn: Any, max_queries: int | None = None):
        self._conn = conn
        self._max_queries = max_queries
        self._query_count = 0

    @classmethod
    def connect(
        cls, url: str, *, max_queries: int | None = None
    ) -> PostgresAdapter:
        import psycopg

        conn = psycopg.connect(url, autocommit=True)
        return cls(conn, max_queries=max_queries)

    @property
    def query_count(self) -> int:
        return self._query_count

    def _tick(self) -> None:
        self._query_count += 1
        if self._max_queries is not None and self._query_count > self._max_queries:
            raise QueryBudgetExceeded(self._max_queries)

    def run(self, sql: str) -> list[dict[str, Any]]:
        self._tick()
        with self._conn.cursor() as cur:
            cur.execute(sql)
            if cur.description is None:
                return []
            cols = [desc[0] for desc in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

    def columns(self, sql: str) -> list[tuple[str, str]]:
        self._tick()
        wrapped = f"SELECT * FROM ({sql}) _t LIMIT 0"
        with self._conn.cursor() as cur:
            cur.execute(wrapped)
            return [
                (desc[0], _PG_TYPE_MAP.get(desc[1], str(desc[1])))
                for desc in cur.description
            ]

    def close(self) -> None:
        self._conn.close()


def wrap_as_subquery(user_sql: str, probe_sql_template: str) -> str:
    return probe_sql_template.replace("{subquery}", f"({user_sql})")
