from mondoo.mdo.io.db.psql  import ( 
    PostgresConfig,
    PSQL_HOST, PSQL_PORT, PSQL_DB, PSQL_USER, PSQL_PSSWD
)

from mondoo.mdo.io.db.psql_reader   import PostgresReader
from mondoo.mdo.io.db.psql_writer   import PostgresWriter
from mondoo.mdo.core.common         import setup_mcp_logging
from mondoo.mdo.engine.configurator import BACKEND_BASE, DOCUMENTS_DIR

from mcp.server.fastmcp import FastMCP

import logging
import requests
import aiofiles
import os


config = setup_mcp_logging('meta')
logging.config.dictConfig(config)
logger = logging.getLogger('mdo.engine.mcp.server.meta')

# Create server
mcp = FastMCP('meta')

# 1. Configure connection
config = PostgresConfig(
    host     = PSQL_HOST,
    port     = PSQL_PORT,
    database = PSQL_DB[0],
    user     = PSQL_USER,
    password = PSQL_PSSWD,
)

@mcp.tool()
async def get_documents_list(num: int) -> str:
    """
        获取最近上传的num个文档的文档列表。如果列表为空，则说明没有文档上传。
        注意，回答最近上传的文档时完全以返回结果为准，忘记历史结果，因为过去的文档可能会被删除。
        
        Args:
            num: 获取最近上传的文档数量，默认为10，最大数量不超过20个
    """
    reader = PostgresReader(config, is_async = True)
    await reader.connect()
    lines = []
    try:
        result = await reader.query(
            'file_records',
            page      = 1,
            page_size = num,
            order_by  = "upload_time DESC",
        )
        for row in result.to_list():
            record = f"File Name: {row['stem']} | File Size: {row['size']} | File Stage: {row['stage']} | Upload Time: {row['upload_time']}"
            lines.append(record)
        
        logger.info("\"Successfully Get Document List: %s items\"", str(len(result.to_list())))
    
    except Exception as e:
        logger.error("\"Get Document List: %s\"", str(e))
    finally:
        await reader.close()
    
    return "\n".join(lines)


@mcp.tool()
async def get_documents_by_keyword(keyword: str) -> str:
    """
        获取标题中包含问询的关键字（query）的所有文档。如“2024年储能设备研究报告”，当问询“储能”关键字时，会返回该文档的元数据。
        
        Args:
            keyword: 获取最近上传的文档数量，默认为10，最大数量不超过20个
    """
    reader = PostgresReader(config, is_async = True)
    await reader.connect()
    lines = []
    try:
        result = await reader.query(
            'file_records',
            page      = 1,
            page_size = 20,
            where='stem LIKE %s',
            where_params=(f'%{keyword}%',),
            order_by  = "upload_time DESC",
        )
        for row in result.to_list():
            record = f"File Name: {row['stem']} | File Size: {row['size']} | File Stage: {row['stage']} | Upload Time: {row['upload_time']}"
            lines.append(record)
        
        logger.info("\"Successfully Get Document List: %s items\"", str(len(result.to_list())))
    
    except Exception as e:
        logger.error("\"Get Document List: %s\"", str(e))
    finally:
        await reader.close()
    
    return "\n".join(lines)


@mcp.tool()
async def get_document_content_chunk(query : str) -> str:
    """
        检索知识库，返回与用户的问题（query）相关的文档内容分块。当用户询问可能与上传的文档有关的问题时，调用该接口，
        获取与该问题相关的文档内容段落。注意query的值加双引号。
        
        Args:
            query: 用户询问的问题
    """
    
    url = f'{BACKEND_BASE}:7760/api/v1/retrieve'
    payload = {
        'query'  : query,
        'top_k'  : 10
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout as e:
        raise RuntimeError(f"KB retrieve request timeout: {url}") from e
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"KB retrieve HTTP error: {resp.status_code} {resp.text}") from e
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"KB retrieve request failed: {str(e)}") from e
    except Exception as e:
        raise RuntimeError(f"Unexpected KB retrieve error: {str(e)}") from e

    results = data.get('results')
    retrieved = []
    for result in results:
        retrieved.append(
'''
文档标题：{title} | 页码：{page} | 字数：{count}
段落内容：
{excerpt} 
'''.format(
        title   = result.get('source'), 
        page    = result.get('page'),
        count   = result.get('count'),
        excerpt = result.excerpt.replace('\t\t', "")
    )
)

    return f'{'-\n':20}'.join(retrieved)

@mcp.tool()
async def get_document_full_content(title: str) -> str:
    """
        指定文档标题（title），获得该文档全文的内容。
        Args:
            title: 文档标题，注意不要加文件类型后缀或者扩展后缀。
    """
    # Prevent path traversal such as "../../../etc/passwd"
    safe_title = os.path.basename(title)

    file_path = os.path.join(
        DOCUMENTS_DIR,
        f"{safe_title}.md"
    )
    
    try:
        async with aiofiles.open(
            file_path,
            mode='r',
            encoding='utf-8'
        ) as f:
            content = await f.read()
        
        logger.info("Successfully Get Document Full Content from [%s]", title)
        return content

    except FileNotFoundError as e:
        logger.error("Document [%s] Not Found: %s", title, str(e))
        return f"Document '{title}' not found."
    
    except Exception as e:
        logger.error("Failed to Read Document: %s", str(e))
        return f"Failed to read document: {str(e)}"


@mcp.tool()
async def get_document_summary(title : str) -> str:
    """
        指定文档标题（title），可以得到该文档的内容总结。默认情况下，先调用此接口查询内容总结是否存在；
        如果内容总结不存在，则需要自己读取文件内容的全文并进行总结。
        
        Args:
            title: 文档标题，注意不要加文件类型后缀或者扩展后缀。
    """
    reader = PostgresReader(config, is_async = True)
    await reader.connect()
    try:
        result = await reader.query(
            table        = 'file_records',
            columns      = ['summary'],
            where        = 'stem = %s',
            where_params = (title,),
            page         = 1,
            page_size    = 1
        )

        rows = result.to_list()

        if not rows:
            logger.error("Document [%s] Not Found When Set Summary", title)
            return f"Document '{title}' not found."

        logger.info("\"Successfully Get Document Summary [%s]", title)
        return rows[0].get("summary", "")
    finally:
        await reader.close()


@mcp.tool()
async def set_document_summary(title : str, summary : str) -> str:
    """
        指定文档标题（title），并给出对应的文档内容总结（summary）， 可将其存入数据库。下次需要全文内容总结时，
        直接调用get_document_summary即可。
        
        Args:
            title: 文档标题，注意不要加文件类型后缀或者扩展后缀。
    """
    writer = PostgresWriter(config, is_async=True)
    await writer.connect()
    try:
        result = await writer.update(
            table="file_records",
            data={ "summary": summary},
            where="stem = %s",
            where_params=(title,),
            returning=True
        )
        
        if not result:
            logger.error("Document [%s] Not Found When Set Summary", title)
            return f"Document '{title}' not found."
        
        logger.info("\"Successfully Set Document Summary [%s]", title)
        return f"Summary updated for document '{title}'."
    finally:
        await writer.close()


# Run server (stdio transport)
if __name__ == "__main__":
    mcp.run()