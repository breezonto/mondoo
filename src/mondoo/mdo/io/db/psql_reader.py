"""
PostgreSQL Database Reader Interface
========================
Features:
  - Connection pool management
  - Paginated queries
  - Conditional filtering (WHERE)
  - Specified column queries
  - Streaming large tables (prevents OOM)
  - Retrieval of table structure information
"""
from .psql import PostgresConfig

from abc             import ABC, abstractmethod
from contextlib      import asynccontextmanager, contextmanager
from typing          import Any, AsyncGenerator, Generator, Optional, Union
from dataclasses     import dataclass, field
from psycopg2.extras import RealDictCursor as AsyncRealDictCursor

import logging
import asyncio
import psycopg2
import psycopg2.extras
import psycopg2.pool as pool
import aiopg

logger = logging.getLogger(__name__)


# ──────────────────────────── Result Class ──────────────────────────────
@dataclass
class QueryResult:
    """Query Result Wrapper"""

    columns: list[str] = field(default_factory=list)
    rows: list[dict]   = field(default_factory=list)
    total_count: Optional[int] = None
    page: Optional[int] = None
    page_size: Optional[int] = None

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def to_list(self) -> list[dict]:
        return self.rows

    def __repr__(self) -> str:
        return (
            f"QueryResult(columns={len(self.columns)}, "
            f"rows={self.row_count}, total={self.total_count})"
        )
    

class PostgresReader:
    """
    PostgreSQL Unified Reader Interface, 
    specified by is_async to determine if it's in asynchronous mode or not.

    Example (Sync):
        >>> reader = PostgresReader(config, is_async=False)
        >>> result = reader.query("users", page=1, page_size=10)
        >>> reader.close()

    Example (Async):
        >>> reader = PostgresReader(config, is_async=True)
        >>> await reader.connect()
        >>> result = await reader.query("users", page=1, page_size=10)
        >>> await reader.close()
    """

    def __new__(cls, config: 'PostgresConfig', is_async: bool = False):
        if is_async:
            return object.__new__(_AsyncPostgresReaderImpl)
        return object.__new__(_SyncPostgresReaderImpl)


class _SyncPostgresReaderImpl(PostgresReader):
    """
        Synchronization Implementation of PostgresReader
    """
    
    def __init__(self, config: 'PostgresConfig', *, is_async: bool = False) -> None:
        self.config = config
        self._pool: pool.ThreadedConnectionPool | None = None

    def connect(self) -> None:
        if self._pool:
            logger.warning("Connection pool already exists, skipping initialization")
            return
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=self.config.min_connections,
                maxconn=self.config.max_connections,
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.database,
                user=self.config.user,
                password=self.config.password,
            )
            logger.info("✅ Connection pool established [%s:%d/%s]", self.config.host, self.config.port, self.config.database)
        except psycopg2.Error as e:
            logger.error("❌ Connection failed: %s", e)
            raise

    def close(self) -> None:
        if self._pool:
            self._pool.closeall()
            self._pool = None
            logger.info("🔒 Connection pool closed")

    @contextmanager
    def _get_connection(self):
        if not self._pool: self.connect()
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            self._pool.putconn(conn)

    @contextmanager
    def _get_cursor(self, cursor_factory=None):
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=cursor_factory)
            try:
                yield conn, cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()

    def execute_sql(
        self, 
        sql: str, 
        params: tuple = ()
    ) -> 'QueryResult':
        with self._get_cursor(psycopg2.extras.RealDictCursor) as (_, cursor):
            logger.debug("Executing SQL: %s | Params: %s", sql, params)
            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall() if cursor.description else []
            row_dicts = [dict(row) for row in rows] if (rows and isinstance(rows[0], dict)) else [dict(zip(columns, row)) for row in rows]
            return QueryResult(columns=columns, rows=row_dicts)

    def query(
        self, 
        table: str, 
        *, 
        columns      : Optional[list[str]] = None, 
        where        : Optional[str] = None, 
        where_params : tuple = (), 
        order_by     : Optional[str] = None, 
        page         : Optional[int] = None, 
        page_size    : int = 100
    ) -> 'QueryResult':
        
        col_str = ", ".join(columns) if columns else "*"
        where_clause = f"WHERE {where}" if where else ""
        order_clause = f"ORDER BY {order_by}" if order_by else ""
        
        total_count = None
        pagination_clause = ""
        if page is not None:
            offset = (page - 1) * page_size
            pagination_clause = f"LIMIT {page_size} OFFSET {offset}"
            count_sql = f"SELECT COUNT(*) FROM {table} {where_clause}"
            count_result = self.execute_sql(count_sql, where_params)
            total_count = count_result.rows[0]["count"]

        sql = f"SELECT {col_str} FROM {table} {where_clause} {order_clause} {pagination_clause}".strip()
        result = self.execute_sql(sql, where_params)
        result.total_count = total_count
        result.page = page
        result.page_size = page_size
        return result

    def query_by_id(
        self, 
        table     : str, 
        record_id : Any, 
        id_column : str = "id", 
        columns   : Optional[list[str]] = None
    ) -> Optional[dict]:
        col_str = ", ".join(columns) if columns else "*"
        sql = f"SELECT {col_str} FROM {table} WHERE {id_column} = %s LIMIT 1"
        result = self.execute_sql(sql, (record_id,))
        return result.rows[0] if result.rows else None

    def get_table_info(self, table: str) -> 'QueryResult':
        sql = """SELECT c.column_name, c.data_type, c.is_nullable, c.column_default, 
                        c.character_maximum_length, pgd.description AS column_comment
                 FROM information_schema.columns c
                 LEFT JOIN pg_catalog.pg_description pgd 
                     ON pgd.objoid = (c.table_schema || '.' || c.table_name)::regclass::oid 
                     AND pgd.objsubid = c.ordinal_position
                 WHERE c.table_name = %s AND c.table_schema = 'public'
                 ORDER BY c.ordinal_position"""
        return self.execute_sql(sql, (table,))

    def get_table_names(self, schema: str = "public") -> list[str]:
        sql = """SELECT table_name FROM information_schema.tables 
                 WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name"""
        result = self.execute_sql(sql, (schema,))
        return [row["table_name"] for row in result.rows]

    def count(
        self, 
        table        : str, 
        where        : Optional[str] = None, 
        where_params : tuple = ()
    ) -> int:
        where_clause = f"WHERE {where}" if where else ""
        result = self.execute_sql(f"SELECT COUNT(*) as cnt FROM {table} {where_clause}", where_params)
        return result.rows[0]["cnt"]

    def stream_query(
        self, 
        table        : str, 
        *, 
        columns      : Optional[list[str]] = None, 
        where        : Optional[str] = None, 
        where_params : tuple = (), 
        batch_size   : int = 1000
    ) -> Generator[list[dict], None, None]:
        col_str = ", ".join(columns) if columns else "*"
        where_clause = f"WHERE {where}" if where else ""
        sql = f"DECLARE stream_cursor SCROLL CURSOR FOR SELECT {col_str} FROM {table} {where_clause}"
        
        with self._get_connection() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                conn.autocommit = False
                cursor.execute(sql, where_params)
                while True:
                    cursor.execute(f"FETCH {batch_size} FROM stream_cursor")
                    batch = cursor.fetchall()
                    if not batch: break
                    yield [dict(row) for row in batch]
                cursor.execute("CLOSE stream_cursor")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cursor.close()


class _AsyncPostgresReaderImpl(PostgresReader):
    """
        Asynchronization Implementation of PostgresReader
    """

    def __init__(self, config: 'PostgresConfig', *, is_async: bool = False) -> None:
        self.config = config
        self._pool: aiopg.Pool | None = None

    async def connect(self) -> None:
        if self._pool:
            logger.warning("Connection pool already exists, skipping initialization")
            return
        try:
            self._pool = await aiopg.create_pool(
                minsize=self.config.min_connections, maxsize=self.config.max_connections,
                host=self.config.host, port=self.config.port, dbname=self.config.database,
                user=self.config.user, password=self.config.password,
            )
            logger.info("✅ Connection pool established [%s:%d/%s]", self.config.host, self.config.port, self.config.database)
        except Exception as e:
            logger.error("❌ Connection failed: %s", e)
            raise

    async def close(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None
            logger.info("🔒 Connection pool closed")

    @asynccontextmanager
    async def _get_connection(self):
        if not self._pool: await self.connect()
        async with self._pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def _get_cursor(self, cursor_factory=None):
        async with self._get_connection() as conn:
            cursor = await conn.cursor(cursor_factory=cursor_factory)
            try:
                yield conn, cursor
            finally:
                cursor.close()

    async def execute_sql(self, sql: str, params: tuple = ()) -> 'QueryResult':
        async with self._get_cursor(AsyncRealDictCursor) as (_, cursor):
            logger.debug("Executing SQL: %s | Params: %s", sql, params)
            await cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = await cursor.fetchall() if cursor.description else []
            row_dicts = [dict(row) for row in rows] if (rows and isinstance(rows[0], dict)) else [dict(zip(columns, row)) for row in rows]
            return QueryResult(columns=columns, rows=row_dicts)

    async def query(
        self, 
        table        : str, 
        *, 
        columns      : Optional[list[str]] = None, 
        where        : Optional[str] = None, 
        where_params : tuple = (), 
        order_by     : Optional[str] = None, 
        page         : Optional[int] = None, 
        page_size    : int = 100
    ) -> 'QueryResult':
        
        col_str = ", ".join(columns) if columns else "*"
        where_clause = f"WHERE {where}" if where else ""
        order_clause = f"ORDER BY {order_by}" if order_by else ""
        
        total_count = None
        pagination_clause = ""
        if page is not None:
            offset            = (page - 1) * page_size
            pagination_clause = f"LIMIT {page_size} OFFSET {offset}"
            count_result      = await self.execute_sql(f"SELECT COUNT(*) FROM {table} {where_clause}", where_params)
            total_count       = count_result.rows[0]["count"]

        sql = f"SELECT {col_str} FROM {table} {where_clause} {order_clause} {pagination_clause}".strip()
        result             = await self.execute_sql(sql, where_params)
        result.total_count = total_count
        result.page        = page
        result.page_size   = page_size
        return result

    async def query_by_id(
        self, 
        table     : str, 
        record_id : Any, 
        id_column : str = 'id', 
        columns   : Optional[list[str]] = None
    ) -> Optional[dict]:
        col_str = ", ".join(columns) if columns else "*"
        result = await self.execute_sql(f"SELECT {col_str} FROM {table} WHERE {id_column} = %s LIMIT 1", (record_id,))
        return result.rows[0] if result.rows else None

    async def get_table_info(self, table: str) -> 'QueryResult':
        sql = """SELECT c.column_name, c.data_type, c.is_nullable, c.column_default, 
                        c.character_maximum_length, pgd.description AS column_comment
                 FROM information_schema.columns c
                 LEFT JOIN pg_catalog.pg_description pgd 
                     ON pgd.objoid = (c.table_schema || '.' || c.table_name)::regclass::oid 
                     AND pgd.objsubid = c.ordinal_position
                 WHERE c.table_name = %s AND c.table_schema = 'public'
                 ORDER BY c.ordinal_position"""
        return await self.execute_sql(sql, (table,))

    async def get_table_names(self, schema: str = "public") -> list[str]:
        result = await self.execute_sql("""SELECT table_name FROM information_schema.tables 
                                           WHERE table_schema = %s AND table_type = 'BASE TABLE' ORDER BY table_name""", (schema,))
        return [row["table_name"] for row in result.rows]

    async def count(
        self, 
        table        : str, 
        where        : Optional[str] = None, 
        where_params : tuple = ()
    ) -> int:
        where_clause = f"WHERE {where}" if where else ""
        result = await self.execute_sql(f"SELECT COUNT(*) as cnt FROM {table} {where_clause}", where_params)
        return result.rows[0]["cnt"]

    async def stream_query(
        self, 
        table        : str, 
        *, 
        columns      : Optional[list[str]] = None, 
        where        : Optional[str] = None, 
        where_params : tuple = (), 
        batch_size   : int = 1000
    ) -> AsyncGenerator[list[dict], None]:
        col_str = ", ".join(columns) if columns else "*"
        where_clause = f"WHERE {where}" if where else ""
        sql = f"DECLARE stream_cursor SCROLL CURSOR FOR SELECT {col_str} FROM {table} {where_clause}"
        
        # 避免异步生成器与上下文管理器死锁，采用手动连接管理
        if not self._pool: await self.connect()
        conn = await self._pool.acquire()
        cursor = await conn.cursor(cursor_factory=AsyncRealDictCursor)
        _committed = False

        try:
            await cursor.execute("BEGIN")
            await cursor.execute(sql, where_params)
            while True:
                await cursor.execute(f"FETCH {batch_size} FROM stream_cursor")
                batch = await cursor.fetchall()
                if not batch: break
                yield [dict(row) for row in batch]
            await cursor.execute("CLOSE stream_cursor")
            await cursor.execute("COMMIT")
            _committed = True
        except Exception:
            try: await cursor.execute("ROLLBACK")
            except Exception: pass
            raise
        finally:
            if not _committed:
                try: await cursor.execute("ROLLBACK")
                except Exception: pass
            cursor.close()
            await self._pool.release(conn)
