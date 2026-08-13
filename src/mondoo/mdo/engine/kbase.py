from ..io.db.psql          import get_default_psql_config
from .configurator import LOCAL_EMBEDDING_MODEL_PATH

from haystack.components.embedders import (
    SentenceTransformersTextEmbedder, 
    SentenceTransformersDocumentEmbedder
)

from haystack                                 import Document
from haystack.document_stores.in_memory       import InMemoryDocumentStore
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever

import os
import json
import uuid
import sys
import logging


from ..io.db.psql_reader import PostgresReader

logger = logging.getLogger(__name__)

QUERY_EMBEDDER = None
RETRIEVER      = None
KSTORE         = None
DOC_EMBEDDER   = None


def _init_store_embedder_():
    global DOC_EMBEDDER
    DOC_EMBEDDER = SentenceTransformersDocumentEmbedder(model=LOCAL_EMBEDDING_MODEL_PATH)
    DOC_EMBEDDER.warm_up()
    
    
def _init_query_embedder_():
    global QUERY_EMBEDDER
    QUERY_EMBEDDER = SentenceTransformersTextEmbedder(model=LOCAL_EMBEDDING_MODEL_PATH)
    QUERY_EMBEDDER.warm_up()
    


def _read_chunk_columns_():
    config = get_default_psql_config()

    reader = PostgresReader(config, is_async = False)
    reader.connect()

    table_name = 'file_records'
    columns = ['chunks']
    
    result = reader.query(
        table_name,
        columns = columns,
    )

    reader.close()
    return result.rows


def init_knowledge_base():
    global QUERY_EMBEDDER
    global RETRIEVER
    global KSTORE
    global DOC_EMBEDDER
    
    KSTORE = InMemoryDocumentStore()

    docs = []
    _init_store_embedder_()

    # 3) Embed query
    _init_query_embedder_()
    
    # 4) Retriever
    RETRIEVER = InMemoryEmbeddingRetriever(document_store=KSTORE)

    rows = _read_chunk_columns_()
    for row in rows:
        data       = row.get('chunks')
        if data is not None:
            chunks     = data.get('chunks', [])
            file_id    = data.get('file_id')
            file_name = data.get('file_name', 'Unknown Title')
            file_type  = data.get('file_type', 'unknown')
            
            store_indexed_excerpt(
                file_id    = file_id,
                file_title = '.'.join([file_name, file_type]),
                file_type  = file_type,
                chunks     = chunks
            )
        

def store_indexed_excerpt(
    file_id    : str,
    file_title : str, 
    file_type  : str, 
    chunks     : list[dict]
) -> None:
    docs = []
    
    for i, chunk in enumerate(chunks):
        meta = {
            'title'    : file_title,
            'type'     : file_type,
            'count'    : chunk.get('count', -1),
            'page_idx' : chunk.get('page_idx', [])
        }
        docs.append(
            Document(
                id      = f'{file_id}-{i}',
                content = chunk["content"],
                meta    = meta
            )
        )   
    
    indexed_docs = DOC_EMBEDDER.run(documents=docs)['documents']
    KSTORE.write_documents(indexed_docs)


def store_indexed_excerpt_from_path(file_path: str) -> None:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        chunks = data.get('chunks', [])
        file_title = data.get('file_name', 'Unknown Title')
        file_type  = data.get('file_type', 'unknown')
        
        store_indexed_excerpt(
            file_title=file_title,
            file_type=file_type,
            chunks=chunks
        )


def get_top_k_excerpts(query: str, top_k: int = 3):
    query_embedding = QUERY_EMBEDDER.run(text=query)["embedding"]
    result_docs = RETRIEVER.run(query_embedding=query_embedding, top_k=top_k)
    return result_docs['documents']


def remove_excerpts_from_kb(
    file_id: str,
    *, 
    total_excerpts : int
) -> None:
    excerpt_ids = [f'{file_id}-{i}' for i in range(total_excerpts)]
    KSTORE.delete_documents(document_ids=excerpt_ids)


init_knowledge_base()
