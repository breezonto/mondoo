from ..engine.dbc import get_current_async_dbc, get_current_sync_dbc

import mondoo.mdo.engine.kbase as K
import logging


logger = logging.getLogger(__name__)


def store_excerpts_to_kb(
    file_id   : str,
    *,
    file_name : str,
    file_type : str
):
    try:
        db = get_current_sync_dbc()
    
        rows = db.read(
            table_name   = 'file_records',
            columns      = ['chunks'],
            where        = "file_id = %s",
            where_params = (file_id,),
            num          = 1
        )
        chunks = rows[0].get('chunks')

        K.store_indexed_excerpt(
            file_id    = file_id,
            file_title = file_name,
            file_type  = file_type,
            chunks     = chunks
        )

        logger.info("\"Stored Excerpts <%s>\"", file_id)
    
    except Exception as e:
        hint = f"Failed to Store Excerpts <{file_id}>: {str(e)}"
        logger.info(hint) 
        raise RuntimeError(hint)
    

async def store_excerpts_to_kb_async(
    file_id   : str,
    *,
    file_name : str,
    file_type : str
):
    try:
        db = get_current_async_dbc()
    
        rows = await db.read_async(
            table_name   = 'file_records',
            columns      = ['chunks'],
            where        = "file_id = %s",
            where_params = (file_id,),
            num          = 1
        )
        chunks = rows[0].get('chunks')

        K.store_indexed_excerpt(
            file_id    = file_id,
            file_title = '.'.join([file_name, file_type]),
            file_type  = file_type,
            chunks     = chunks
        )

        logger.info("\"Stored Excerpts <%s>\"", file_id)
    
    except Exception as e:
        hint = f"Failed to Store Excerpts <{file_id}>: {str(e)}"
        logger.info(hint) 
        raise RuntimeError(hint)


def recall_k_excerpts(query : str, k : int):
    result = K.get_top_k_excerpts(query, k)
    return result


def erase_excerpts_from_kb(
    file_id : str,
    *, 
    total_excerpts : int
):
    K.remove_excerpts_from_kb(file_id, total_excerpts=total_excerpts)