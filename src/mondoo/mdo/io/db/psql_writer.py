import logging
import asyncio
import psycopg2
import psycopg2.extras
import psycopg2.pool as pool
import aiopg

from abc                      import ABC, abstractmethod
from contextlib               import asynccontextmanager, contextmanager
from typing                   import Any, AsyncGenerator, Generator, Optional, Union
from dataclasses              import dataclass, field
from psycopg2.extras          import RealDictCursor as AsyncRealDictCursor, Json
from .psql import (
    PostgresConfig,
    PSQL_HOST, PSQL_PORT, PSQL_DB, PSQL_USER, PSQL_PSSWD
)

from .psql_reader  import PostgresReader

# ──────────────────────────── Logging Config ────────────────────────────
logger = logging.getLogger(__name__)


class PostgresWriter:
    def __new__(cls, config: 'PostgresConfig', is_async: bool = False):
        if is_async:
            return object.__new__(_AsyncPostgresWriterImpl)
        return object.__new__(_SyncPostgresWriterImpl)
    

class _SyncPostgresWriterImpl(PostgresWriter):
    def __init__(self, config: 'PostgresConfig', *, is_async: bool = False):
        self.config = config
        self._pool: pool.ThreadedConnectionPool | None = None

    def connect(self) -> None:
        if self._pool:
            return
        self._pool = pool.ThreadedConnectionPool(
            self.config.min_connections,
            self.config.max_connections,
            host     = self.config.host,
            port     = self.config.port,
            dbname   = self.config.database,
            user     = self.config.user,
            password = self.config.password,
        )

    def close(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None

    @contextmanager
    def _get_cursor(self):
        if not self._pool:
            self.connect()
        conn = self._pool.getconn()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            yield conn, cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            self._pool.putconn(conn)

    # ───────────── INSERT ─────────────
    def _insert_(
        self, 
        table     : str, 
        data      : dict, 
        returning : bool = False
    ) -> Optional[dict]:
        keys   = data.keys()
        values = tuple(data.values())

        cols = ', '.join(keys)
        placeholders = ", ".join(["%s"] * len(keys))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        if returning:
            sql += " RETURNING *"

        with self._get_cursor() as (_, cur):
            cur.execute(sql, values)
            if returning:
                return dict(cur.fetchone())
        return None
    
    def insert(
        self, 
        table     : str, 
        data      : dict,
        json_col  : Optional[str]  = None,
        json_data : Optional[dict] = None, 
        returning : bool           = False
    ) -> Optional[dict]:
        
        if json_col is not None and json_data is not None:
            data[json_col] = Json(json_data)
    
        result = self._insert_(
            table     = table,
            data      = data,
            returning = returning
        )

        return result

    # async def insert_json(
    #     self,
    #     table       : str,
    #     json_column : str,
    #     json_data   : dict,
    #     extra_data  : dict = None,
    #     returning   : bool = False,
    # ):
    #     data = dict(extra_data or {})
    #     data[json_column] = Json(json_data)

    #     return self._insert_(table, data, returning=returning)


    # ───────────── BATCH INSERT ─────────────
    def insert_many(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return

        keys = rows[0].keys()
        cols = ", ".join(keys)
        placeholders = ", ".join(["%s"] * len(keys))

        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"

        values = [tuple(row[k] for k in keys) for row in rows]

        with self._get_cursor() as (_, cur):
            psycopg2.extras.execute_batch(cur, sql, values)

    # ───────────── UPDATE ─────────────
    def update(
        self,
        table        : str,
        data         : dict,
        where        : str,
        where_params : tuple = (),
        returning    : bool = False,
    ) -> list[dict]:
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        params = tuple(data.values()) + where_params

        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        if returning:
            sql += " RETURNING *"

        with self._get_cursor() as (_, cur):
            cur.execute(sql, params)
            if returning:
                return [dict(r) for r in cur.fetchall()]
        return []

    def update_json(
        self,
        table        : str,
        json_column  : str,
        json_data    : dict,
        where        : str,
        where_params : tuple = (),
        returning    : bool = False,
    ):
        data = { json_column: Json(json_data) }
        return self.update(table, data, where, where_params, returning)
    
    # ───────────── DELETE ─────────────
    def delete(self, table: str, where: str, where_params: tuple = ()) -> int:
        sql = f"DELETE FROM {table} WHERE {where}"

        with self._get_cursor() as (_, cur):
            cur.execute(sql, where_params)
            return cur.rowcount

    # ───────────── UPSERT ─────────────
    def upsert(
        self,
        table            : str,
        data             : dict,
        conflict_columns : list[str],
        returning        : bool = False,
    ) -> Optional[dict]:
        keys = data.keys()
        values = tuple(data.values())

        cols = ", ".join(keys)
        placeholders = ", ".join(["%s"] * len(keys))

        update_clause = ", ".join(
            [f"{k} = EXCLUDED.{k}" for k in keys if k not in conflict_columns]
        )

        conflict = ", ".join(conflict_columns)

        sql = f"""
        INSERT INTO {table} ({cols})
        VALUES ({placeholders})
        ON CONFLICT ({conflict})
        DO UPDATE SET {update_clause}
        """

        if returning:
            sql += " RETURNING *"

        with self._get_cursor() as (_, cur):
            cur.execute(sql, values)
            if returning:
                return dict(cur.fetchone())
        return None
    

class _AsyncPostgresWriterImpl(PostgresWriter):
    def __init__(self, config: 'PostgresConfig', *, is_async: bool = False):
        self.config = config
        self._pool: aiopg.Pool | None = None

    async def connect(self) -> None:
        if self._pool:
            return
        self._pool = await aiopg.create_pool(
            minsize  = self.config.min_connections,
            maxsize  = self.config.max_connections,
            host     = self.config.host,
            port     = self.config.port,
            dbname   = self.config.database,
            user     = self.config.user,
            password = self.config.password,
        )

    async def close(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    @asynccontextmanager
    async def _get_cursor(self):
        if not self._pool:
            await self.connect()
        async with self._pool.acquire() as conn:
            cursor = await conn.cursor(cursor_factory=AsyncRealDictCursor)
            try:
                yield conn, cursor
            finally:
                cursor.close()

    @asynccontextmanager
    async def transaction(self):
        async with self._get_cursor() as (_, cur):
            try:
                await cur.execute("BEGIN")
                yield cur
                await cur.execute("COMMIT")
            except:
                await cur.execute("ROLLBACK")
                raise

    # ───────── INSERT ─────────
    async def _insert_(
        self, 
        table     : str, 
        data      : dict, 
        returning : bool = False
    ):
        keys   = data.keys()
        values = tuple(data.values())

        cols = ", ".join(keys)
        placeholders = ", ".join(['%s'] * len(keys))

        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        if returning:
            sql += " RETURNING *"

        # async with self._get_cursor() as (_, cur):
        async with self.transaction() as cur:
            await cur.execute(sql, values)
            if returning:
                return dict(await cur.fetchone())
        return None
    
    async def insert(
        self, 
        table     : str, 
        data      : dict,
        json_col  : Optional[str]  = None,
        json_data : Optional[dict] = None, 
        returning : bool           = False
    ):
        if json_col is not None and json_data is not None:
            data[json_col] = Json(json_data)
        
        result = await self._insert_(table, data, returning)
        return result

    # async def insert_json(
    #     self,
    #     table       : str,
    #     json_column : str,
    #     json_data   : dict,
    #     extra_data  : dict = None,
    #     returning   : bool = False,
    # ):
    #     data = dict(extra_data or {})
    #     data[json_column] = Json(json_data)
    # 
    #     return await self._insert_(table, data, returning=returning)
    
    # ───────── UPDATE ─────────
    async def update(self, table, data, where, where_params=(), returning=False):
        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        params = tuple(data.values()) + where_params

        sql = f"UPDATE {table} SET {set_clause} WHERE {where}"
        if returning:
            sql += " RETURNING *"

        # async with self._get_cursor() as (_, cur):
        async with self.transaction() as cur:
            await cur.execute(sql, params)
            if returning:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]
        return []

    async def update_json(
        self,
        table        : str,
        json_column  : str,
        json_data    : dict,
        where        : str,
        where_params : tuple = (),
        returning    : bool  = False,
    ):
        data = { json_column: Json(json_data) }
        return await self.update(table, data, where, where_params, returning)

    # ───────── DELETE ─────────
    async def delete(self, table, where, where_params=()):
        sql = f"DELETE FROM {table} WHERE {where}"
        # async with self._get_cursor() as (_, cur):
        async with self.transaction() as cur:
            await cur.execute(sql, where_params)
            return cur.rowcount

    # ───────── UPSERT ─────────
    async def upsert(self, table, data, conflict_columns, returning=False):
        keys = data.keys()
        values = tuple(data.values())

        cols = ", ".join(keys)
        placeholders = ", ".join(["%s"] * len(keys))
        conflict = ", ".join(conflict_columns)

        update_clause = ", ".join(
            [f"{k} = EXCLUDED.{k}" for k in keys if k not in conflict_columns]
        )

        sql = f"""
        INSERT INTO {table} ({cols})
        VALUES ({placeholders})
        ON CONFLICT ({conflict})
        DO UPDATE SET {update_clause}
        """

        if returning:
            sql += " RETURNING *"

        # async with self._get_cursor() as (_, cur):
        async with self.transaction() as cur:
            await cur.execute(sql, values)
            if returning:
                return dict(await cur.fetchone())
        return None


