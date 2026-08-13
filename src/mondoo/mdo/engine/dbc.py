from ..io.db.psql        import get_default_psql_config
from ..io.db.psql_reader import PostgresReader
from ..io.db.psql_writer import PostgresWriter


class DBC:
    def __init__(
        self,
        enable_psql  : bool = True, 
        enable_redis : bool = False,
        is_async     : bool = True,
        **kwargs
    ):
        self.psql_enabled  = False
        self.redis_enabled = False
        
        if enable_psql:
            psql_host  = kwargs.get('psql_host', None)
            psql_port  = kwargs.get('psql_port', None)
            psql_db    = kwargs.get('psql_db', None)
            psql_user  = kwargs.get('psql_user', None)
            psql_psswd = kwargs.get('psql_psswd', None)

            self.psql_config = get_default_psql_config()

            self.is_async = is_async

            self.psql_reader : PostgresReader = PostgresReader(self.psql_config, is_async=self.is_async)
            self.psql_writer : PostgresWriter = PostgresWriter(self.psql_config, is_async=self.is_async)

            self.psql_enabled = True

        if enable_redis:
             self.redis_enabled = True
    
    
    def is_psql_enabled(self) -> bool:
        return self.psql_enabled
    
    
    def is_redis_enabled(self) -> bool:
        return self.redis_enabled

    def insert(
        self,
        table_name       : str,
        data             : dict,
        *,
        returning        : bool = True,
        upsert           : bool = False,
        conflict_columns : list[str] | None = None
    ):
        if self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface suffixed with async")
        
        if not self.psql_enabled and not self.redis_enabled:
            raise RuntimeError("Both PostgreSQL and Redis not initialized")

        if self.psql_enabled:
            self.psql_writer.connect()
            try:
                if not upsert:
                    result = self.psql_writer.insert(
                        table     = table_name,
                        data      = data,
                        returning = returning
                    )

                else:
                    if not conflict_columns:
                        raise ValueError("conflict_columns must be provided for upsert")

                    result = self.psql_writer.upsert(
                        table            = table_name,
                        data             = data,
                        conflict_columns = conflict_columns,
                        returning        = returning
                    )

            finally:
                self.psql_writer.close()

        if self.redis_enabled:
            pass
        
        return result

    async def insert_async(
        self,
        table_name       : str,
        data             : dict,
        *,
        returning        : bool = True,
        upsert           : bool = False,
        conflict_columns : list[str] | None = None
    ):
        if not self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface in sync")
        
        if not self.psql_enabled and not self.redis_enabled:
            raise RuntimeError("Both PostgreSQL and Redis not initialized")

        if self.psql_enabled:
            await self.psql_writer.connect()
            try:
                if not upsert:
                    result = await self.psql_writer.insert(
                        table     = table_name,
                        data      = data,
                        returning = returning
                    )

                else:
                    if not conflict_columns:
                        raise ValueError("conflict_columns must be provided for upsert")

                    result = await self.psql_writer.upsert(
                        table            = table_name,
                        data             = data,
                        conflict_columns = conflict_columns,
                        returning        = returning
                    )

            finally:
                await self.psql_writer.close()

        if self.redis_enabled:
            pass
        
        return result
    
    # ========================
    # READ
    # ========================
    def read(
        self,
        table_name   : str,
        *,
        columns      : list[str] | None = None,
        num          : int | None       = None,
        where        : str | None       = None,
        where_params : tuple            = (),
        order_by     : str | None       = None
    ):
        if not self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface in sync")
        
        if not self.psql_enabled and not self.redis_enabled:
            raise RuntimeError("Both PostgreSQL and Redis not initialized")
        
        if self.psql_enabled:
            self.psql_reader.connect()
            try:
                if num is None:
                    result = self.psql_reader.query(
                        table_name,
                        columns      = columns,
                        where        = where,
                        where_params = where_params,
                        order_by     = order_by,
                    )
                
                elif num > 0:
                    result = self.psql_reader.query(
                        table_name,
                        columns      = columns,
                        where        = where,
                        where_params = where_params,
                        page         = 1,
                        page_size    = num,
                        order_by     = order_by,
                    )

                else:
                    raise ValueError("num must be None or > 0")

            finally:
                self.psql_reader.close()

        
        if self.redis_enabled:
            pass

        return result.rows
    
    async def read_async(
        self,
        table_name   : str,
        *,
        columns      : list[str] | None = None,
        num          : int | None       = None,
        where        : str | None       = None,
        where_params : tuple            = (),
        order_by     : str | None       = None
    ):
        if not self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface in sync")
        
        if not self.psql_enabled and not self.redis_enabled:
            raise RuntimeError("Both PostgreSQL and Redis not initialized")
        
        if self.psql_enabled:
            await self.psql_reader.connect()
            try:
                if num is None:
                    result = await self.psql_reader.query(
                        table_name,
                        columns      = columns,
                        where        = where,
                        where_params = where_params,
                        order_by     = order_by,
                    )
                
                elif num > 0:
                    result = await self.psql_reader.query(
                        table_name,
                        columns      = columns,
                        where        = where,
                        where_params = where_params,
                        page         = 1,
                        page_size    = num,
                        order_by     = order_by,
                    )

                else:
                    raise ValueError("num must be None or > 0")

            finally:
                await self.psql_reader.close()

        
        if self.redis_enabled:
            pass

        return result.rows
    
    # ========================
    # UPDATE
    # ========================
    def update(
        self,
        table_name   : str,
        data         : dict,
        where        : str,
        where_params : tuple = (),
        *,
        returning: bool = True
    ):
        if self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface suffixed with async")
        
        if not self.psql_enabled and not self.redis_enabled:
            raise RuntimeError("Both PostgreSQL and Redis not initialized")

        if self.psql_enabled:
            self.psql_writer.connect()
            try:
                result = self.psql_writer.update(
                    table        = table_name,
                    data         = data,
                    where        = where,
                    where_params = where_params,
                    returning    = returning
                )
            finally:
                self.psql_writer.close()

        if self.redis_enabled:
            pass

        return result
    
    async def update_async(
        self,
        table_name   : str,
        data         : dict,
        where        : str,
        where_params : tuple = (),
        *,
        returning: bool = True
    ):
        if not self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface in sync")
        
        if not self.psql_enabled and not self.redis_enabled:
            raise RuntimeError("Both PostgreSQL and Redis not initialized")

        if self.psql_enabled:
            await self.psql_writer.connect()
            try:
                result = await self.psql_writer.update(
                    table        = table_name,
                    data         = data,
                    where        = where,
                    where_params = where_params,
                    returning    = returning
                )
            finally:
                await self.psql_writer.close()

        if self.redis_enabled:
            pass

        return result

    # ========================
    # DELETE
    # ========================
    def remove(
        self,
        table_name   : str,
        where        : str,
        where_params : tuple = ()
    ):
        if self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface suffixed with async")
        
        if not self.psql_enabled and not self.redis_enabled:
            raise RuntimeError("Both PostgreSQL and Redis not initialized")

        if self.psql_enabled:
            self.psql_writer.connect()
            try:
                result = self.psql_writer.delete(
                    table=table_name,
                    where=where,
                    where_params=where_params
                )
            finally:
                self.psql_writer.close()

        if self.redis_enabled:
            pass

        return result
    
    async def remove_async(
        self,
        table_name   : str,
        where        : str,
        where_params : tuple = ()
    ):
        if not self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface in sync")
        
        if not self.psql_enabled and not self.redis_enabled:
            raise RuntimeError("Both PostgreSQL and Redis not initialized")

        if self.psql_enabled:
            await self.psql_writer.connect()
            try:
                result = await self.psql_writer.delete(
                    table=table_name,
                    where=where,
                    where_params=where_params
                )
            finally:
                await self.psql_writer.close()

        if self.redis_enabled:
            pass

        return result


    async def write_json_data_async(
        self,
        table_name   : str,
        json_column  : str,
        json_data    : dict,
        where        : str,
        where_params : tuple = (),
        returning    : bool  = False
    ):
        if not self.is_async:
            raise RuntimeError("Current Client is in Async Mode, Call interface in sync")
        
        if not self.psql_enabled:
            raise RuntimeError("PostgreSQL not initialized (Note: Redis doesn't support writing json data)")
        
        await self.psql_writer.update_json(
            table        = table_name,
            json_column  = json_column,
            json_data    = json_data,
            where        = where,
            where_params = where_params,
            returning    = returning
        )

    
    async def run(self):
        pass


ACTIVE_DBC_ASYNC = None
ACTIVE_DBC_SYNC  = None

def init_db_client_from_default_config() -> DBC:
    global ACTIVE_DBC_ASYNC
    global ACTIVE_DBC_SYNC

    if not ACTIVE_DBC_ASYNC:
        ACTIVE_DBC_ASYNC = DBC(
            enable_psql  = True,
            enable_redis = False,
            is_async     = True
        )

    if not ACTIVE_DBC_SYNC:
        ACTIVE_DBC_SYNC = DBC(
            enable_psql  = True,
            enable_redis = False,
            is_async     = False
        )
    
    return ACTIVE_DBC_SYNC, ACTIVE_DBC_SYNC


def get_current_async_dbc():
    global ACTIVE_DBC_ASYNC
    return ACTIVE_DBC_ASYNC


def get_current_sync_dbc():
    global ACTIVE_DBC_SYNC
    return ACTIVE_DBC_SYNC


def get_current_dbc(is_async : bool = True):
    if is_async:
        return get_current_async_dbc()
    else:
        return get_current_sync_dbc()


def get_valid_objects():
    return ['file_records']

