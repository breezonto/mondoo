from mondoo.mdo.io.db.psql import (
    PostgresConfig,
    PSQL_HOST, PSQL_PORT, PSQL_DB, PSQL_USER, PSQL_PSSWD
)

from mondoo.mdo.io.db.psql_reader import PostgresReader 
from mondoo.mdo.io.db.psql_writer import PostgresWriter

import asyncio


def test_sync():
    # 1. Configure connection
    config = PostgresConfig(
        host     = PSQL_HOST,
        port     = PSQL_PORT,
        database = PSQL_DB[0],
        user     = PSQL_USER,
        password = PSQL_PSSWD,
    )

    # 2. Initialize reader (automatically establish connection pool)
    reader = PostgresReader(config, is_async = False)
    reader.connect()

    try:
        # ══════════ Get all table names ══════════
        tables = reader.get_table_names()
        print(f"📋 Tables in database: {tables}")

        # ══════════ View table structure ══════════
        if tables:
            info = reader.get_table_info(tables[0])
            print(f"\n📐 Structure of table [{tables[0]}]:")
            for col in info.rows:
                print(f"  - {col['column_name']}: {col['data_type']}")

        # ══════════ Paginated query ══════════
        print("\n📄 Paginated query for file_records (Page 1):")
        result = reader.query(
            "file_records",
            page      = 1,
            page_size = 5,
            order_by  = "upload_time DESC",
        )
        for row in result.to_list():
            print(f"  {row['file_id']} | {row['stem']} | {row['stage']}")
        print(f"  📊 Total {result.total_count} rows | This page {result.row_count} rows")

        # ══════════ Query single record by file_id ══════════
        record = reader.query_by_id(
            "file_records",
            record_id = "YyLH6AEdJ3Db-1uyQ3HIo1MvdVorcSUDdinn0wGlKPE",
            id_column = "file_id",
            columns   = ["file_id", "stem", "ext", "size", "stage"],
        )
        print(f"\n🔍 Query single record: {record}")

        
        # ══════════ Total record count ══════════
        total = reader.count("file_records")
        print(f"\n🔢 Total records in file_records: {total}")

        
        # ══════════ Statistics grouped by stage ══════════
        print("\n⚡ Statistics grouped by stage:")
        sql_result = reader.execute_sql(
            "SELECT stage, COUNT(*) as cnt FROM file_records GROUP BY stage"
        )
        for row in sql_result.to_list():
            print(f"  {row['stage']}: {row['cnt']} 条")

        
        # ══════════ Conditional query: files with specific stage ══════════
        print("\n🔎 Conditional query (stage = 'stored'):")
        result = reader.query(
            "file_records",
            where        = "stage = %s",
            where_params = ("stored",),
            columns      = ["file_id", "stem", "size", "total_chunks"],
            order_by     = "size DESC",
            page         = 1,
            page_size    = 5,
        )
        for row in result.to_list():
            print(f"  {row['stem']} | Size: {row['size']} | Chunks: {row['total_chunks']}")
        print(f"  📊 Total {result.total_count} rows")

        
        # ══════════ Stream reading ══════════
        print("\n🌊 Streaming read file_records (batch size 1000):")
        for i, batch in enumerate(reader.stream_query("file_records", batch_size=1000)):
            print(f"  Batch {i}: read {len(batch)} rows")
            for row in batch:
                print(f"    - {row['file_id']} | {row['stage']}")
            break  # Only read the first batch for testing

    finally:
        # 3. Close connection pool
        reader.close()


async def test_async():
    # 1. Configure connection
    config = PostgresConfig(
        host     = PSQL_HOST,
        port     = PSQL_PORT,
        database = PSQL_DB[0],
        user     = PSQL_USER,
        password = PSQL_PSSWD,
    )

    # 2. Initialize reader (automatically establish connection pool)
    reader = PostgresReader(config, is_async=True)
    await reader.connect()

    try:
        # ══════════ Get all table names ══════════
        tables = await reader.get_table_names()
        print(f"📋 Tables in database: {tables}")

        # ══════════ View table structure ══════════
        if tables:
            info = await reader.get_table_info(tables[0])
            print(f"\n📐 Structure of table [{tables[0]}]:")
            for col in info.rows:
                print(f"  - {col['column_name']}: {col['data_type']}")

        # ══════════ Paginated query ══════════
        print("\n📄 Paginated query for file_records (Page 1):")
        result = await reader.query(
            "file_records",
            page=1,
            page_size=5,
            order_by="upload_time DESC",
        )
        for row in result.to_list():
            print(f"  {row['file_id']} | {row['stem']} | {row['stage']}")
        print(f"  📊 Total {result.total_count} rows | This page {result.row_count} rows")

        # ══════════ Query single record by file_id ══════════
        record = await reader.query_by_id(
            "file_records",
            record_id = "YyLH6AEdJ3Db-1uyQ3HIo1MvdVorcSUDdinn0wGlKPE",
            id_column = "file_id",
            columns   = ["file_id", "stem", "ext", "size", "stage"],
        )
        print(f"\n🔍 Query single record: {record}")

        
        # ══════════ Total record count ══════════
        total = await reader.count("file_records")
        print(f"\n🔢 Total records in file_records: {total}")

        
        # ══════════ Statistics grouped by stage ══════════
        print("\n⚡ Statistics grouped by stage:")
        sql_result = await reader.execute_sql(
            "SELECT stage, COUNT(*) as cnt FROM file_records GROUP BY stage"
        )
        for row in sql_result.to_list():
            print(f"  {row['stage']}: {row['cnt']} rows")

        
        # ══════════ Conditional query: files with specific stage ══════════
        print("\n🔎 Conditional query (stage = 'stored'):")
        result = await reader.query(
            "file_records",
            where        = "stage = %s",
            where_params = ("stored",),
            columns      = ["file_id", "stem", "size", "total_chunks"],
            order_by     = "size DESC",
            page         = 1,
            page_size    = 5,
        )
        for row in result.to_list():
            print(f"  {row['stem']} | Size: {row['size']} | Chunks: {row['total_chunks']}")
        print(f"  📊 Total {result.total_count} rows")

        
        # ══════════ Stream reading ══════════
        print("\n🌊 Streaming read file_records (batch size 1000):")
        batch_idx = 0
        async for batch in reader.stream_query("file_records", batch_size=1000):
            print(f"  Batch {batch_idx + 1}: read {len(batch)} rows")
            for row in batch:
                print(f"    - {row['file_id']} | {row['stage']}")
            batch_idx += 1
            break  # Only read the first batch for testing


    finally:
        # 3. Close connection pool
        await reader.close()



def test_sync():
    config = PostgresConfig(
        host     = PSQL_HOST,
        port     = PSQL_PORT,
        database = PSQL_DB[0],
        user     = PSQL_USER,
        password = PSQL_PSSWD,
    )

    writer = PostgresWriter(config, is_async=False)
    reader = PostgresReader(config, is_async=False)

    writer.connect()
    reader.connect()

    try:
        # ══════════ Insert single record ══════════
        print("\n📝 Insert single record:")
        data = {
            "file_id": "test_file_001",
            "stem": "example",
            "ext": ".txt",
            "size": 1234,
            "stage": "uploaded",
        }
        writer.insert("file_records", data)
        print("  ✅ Inserted test_file_001")

        # ══════════ Query inserted record ══════════
        record = reader.query_by_id(
            "file_records",
            "test_file_001",
            id_column="file_id",
        )
        print(f"  🔍 Queried: {record}")

        # ══════════ Batch insert ══════════
        print("\n📦 Batch insert:")
        batch_data = [
            {
                "file_id": f"batch_{i}",
                "stem": f"file_{i}",
                "ext": ".log",
                "size": i * 100,
                "stage": "uploaded",
            }
            for i in range(3)
        ]
        writer.insert_many("file_records", batch_data)
        print(f"  ✅ Inserted {len(batch_data)} records")

        # ══════════ Update ══════════
        print("\n✏️ Update record:")
        updated = writer.update(
            "file_records",
            data={"stage": "processed"},
            where="file_id = %s",
            where_params=("test_file_001",),
            returning=True,
        )
        print(f"  🔄 Updated: {updated}")

        # ══════════ Upsert (insert or update) ══════════
        print("\n🔁 Upsert record:")
        upsert_data = {
            "file_id": "test_file_001",
            "stem": "example_updated",
            "ext": ".txt",
            "size": 9999,
            "stage": "stored",
        }
        result = writer.upsert(
            "file_records",
            upsert_data,
            conflict_columns=["file_id"],
            returning=True,
        )
        print(f"  ⚡ Upsert result: {result}")

        # ══════════ Verify upsert ══════════
        record = reader.query_by_id(
            "file_records",
            "test_file_001",
            id_column="file_id",
        )
        print(f"  🔍 After upsert: {record}")

        # ══════════ Delete ══════════
        print("\n🗑️ Delete record:")
        deleted = writer.delete(
            "file_records",
            where="file_id = %s",
            where_params=("test_file_001",),
        )
        print(f"  ❌ Deleted rows: {deleted}")

        # ══════════ Verify deletion ══════════
        record = reader.query_by_id(
            "file_records",
            "test_file_001",
            id_column="file_id",
        )
        print(f"  🔍 After delete: {record}")

    finally:
        writer.close()
        reader.close()


async def test_async():
    config = PostgresConfig(
        host     = PSQL_HOST,
        port     = PSQL_PORT,
        database = PSQL_DB[0],
        user     = PSQL_USER,
        password = PSQL_PSSWD,
    )

    writer = PostgresWriter(config, is_async=True)
    reader = PostgresReader(config, is_async=True)

    await writer.connect()
    await reader.connect()

    try:
        # ══════════ Insert ══════════
        print("\n📝 Insert single record:")
        data = {
            'file_id' : "async_test_001",
            'stem'    : "async_example",
            'ext'     : ".txt",
            'size'    : 2048,
            'stage'   : "uploaded",
        }
        await writer.insert("file_records", data)
        print("  ✅ Inserted async_test_001")

        # ══════════ Query ══════════
        record = await reader.query_by_id(
            "file_records",
            "async_test_001",
            id_column="file_id",
        )
        print(f"  🔍 Queried: {record}")

        # ══════════ Update ══════════
        print("\n✏️ Update:")
        updated = await writer.update(
            "file_records",
            {"stage": "processed"},
            where="file_id = %s",
            where_params=("async_test_001",),
            returning=True,
        )
        print(f"  🔄 Updated: {updated}")

        # ══════════ Upsert ══════════
        print("\n🔁 Upsert:")
        upsert_data = {
            "file_id": "async_test_001",
            "stem": "async_updated",
            "ext": ".txt",
            "size": 8888,
            "stage": "stored",
        }
        result = await writer.upsert(
            "file_records",
            upsert_data,
            conflict_columns=["file_id"],
            returning=True,
        )
        print(f"  ⚡ Upsert result: {result}")

        # ══════════ Delete ══════════
        print("\n🗑️ Delete:")
        deleted = await writer.delete(
            "file_records",
            where="file_id = %s",
            where_params=("async_test_001",),
        )
        print(f"  ❌ Deleted rows: {deleted}")

        # ══════════ Verify ══════════
        record = await reader.query_by_id(
            "file_records",
            "async_test_001",
            id_column="file_id",
        )
        print(f"  🔍 After delete: {record}")

    finally:
        await writer.close()
        await reader.close()


if __name__ == '__main__':
    # test_sync()
    asyncio.run(test_async())