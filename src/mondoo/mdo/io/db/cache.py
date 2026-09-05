"""

CacheHelper that wrap redis as the cache helper class. It mainly manages cache block as a mixed model with list, 
hash and set. List for sequential accessor, Hash for retrieving (random access) and Set for uniqueness check. 
For convenience, every data entry (i.e. item) is stored as an object.

"""

from typing import Optional, Dict

import redis
import os
import json
import logging

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv('REDIS_HOST', None)
REDIS_PORT = os.getenv('REDIS_PORT', None)
REDIS_DB   = os.getenv('REDIS_DB', None)

rh = redis.Redis(
    host = REDIS_HOST, 
    port = REDIS_PORT, 
    db   = REDIS_DB[0], # @TODO REDIS_DB is an array, the exact design is to be resolved
    decode_responses = True
)


def _write_entry_to_cache_(
    entry     : dict,
    *,
    list_name : str,
    hash_name : str,
    set_name  : str,
    id_field  : str = 'id'
):
    """
    write data to cache
    """
    if entry.get('data', None) is None:
        id_name = entry[id_field]
    else:
        id_name = entry['data'][id_field]

    logger.info(f"Entry: {entry}")

    # if id_name exists, update it
    rh.hset(hash_name, id_name, json.dumps(entry))

    if not rh.sismember(set_name, id_name):
        rh.rpush(list_name, id_name)
        rh.sadd(set_name, id_name)
        

def _remove_entry_from_cache_(
    id : str,
    *,
    list_name : str,
    hash_name : str,
    set_name  : str
):
    """
    @TODO
    """
        
    rh.hdel(hash_name, id)
    rh.lrem(list_name, 0, id)
    rh.srem(set_name, id)


def _read_entry_from_cache_(
    id : str,
    *,
    list_name : str,
    hash_name : str,
    set_name  : str
) -> Optional[dict]:
    """
    @TODO
    """

    data = rh.hget(hash_name, id)
    if data:
        return json.loads(data)
    
    return None


def _clear_all_entries_in_cache_(
    list_name : str,
    hash_name : str,
    set_name  : str
):
    """
    @TODO
    """

    fields = rh.hkeys(hash_name)
    if fields:
        rh.hdel(hash_name, *fields)

    rh.ltrim(list_name, 1, 0)
    
    members = rh.smembers(set_name)
    if members:
        rh.srem(set_name, *members)


class CacheHelper:
    """
    CacheHepler is a client manager to maninuplate data caching in Redis.
    For simplicity, it initially designed as a mixed data model with list, 
    hash and set. It might not be a good design, the exact design will be 
    proposed in the future with @TODO
    """

    def __init__(
        self,
        cache_name : str
    ):
        """
        @TODO comment
        """

        self._cache_name      = cache_name
        self._list_cache_name = f'{cache_name}_list'
        self._hash_cache_name = f'{cache_name}_hash'
        self._set_cache_name  = f'{cache_name}_set'


    def write_item(
        self, 
        obj      : dict,
        id_field : str,
        suffix   : str = ''
    ):
        """
        @TODO comment
        """
        if suffix != '':
            suffix = f'@{suffix}'

        _write_entry_to_cache_(
            obj,
            id_field  = id_field, 
            list_name = f'{self._list_cache_name}{suffix}',
            hash_name = f'{self._hash_cache_name}{suffix}',
            set_name  = f'{self._set_cache_name}{suffix}'
        )


    def read_item(
        self, 
        id     : str,
        suffix : str = ''
    ):
        """
        @TODO comment
        """

        if suffix != '':
            suffix = f'@{suffix}'
        
        return _read_entry_from_cache_(
            id,
            list_name = f'{self._list_cache_name}{suffix}',
            hash_name = f'{self._hash_cache_name}{suffix}',
            set_name  = f'{self._set_cache_name}{suffix}'
        )


    def remove_item(
        self,
        id     : str,
        suffix : str = ''
    ):
        """
        @TODO comment
        """

        if suffix != '':
            suffix = f'@{suffix}'
        
        _remove_entry_from_cache_(
            id,
            list_name = f'{self._list_cache_name}{suffix}',
            hash_name = f'{self._hash_cache_name}{suffix}',
            set_name  = f'{self._set_cache_name}{suffix}'
        )


    def read_all_items(
        self,
        suffix : str = ''
    ):
        """
        @TODO comment
        """

        if suffix != '':
            suffix = f'@{suffix}'
        
        ids = rh.lrange(''.join([self._list_cache_name, suffix]), 0, -1)

        data = []
        for curr_id in ids:
            instance = _read_entry_from_cache_(
                curr_id,
                list_name = f'{self._list_cache_name}{suffix}',
                hash_name = f'{self._hash_cache_name}{suffix}',
                set_name  = f'{self._set_cache_name}{suffix}'              
            )

            if instance:
                data.append(instance)

        return data


    def clear_all_items(
        self,
        suffix : str = ''
    ):
        """
        @TODO comment
        """

        if suffix != '':
            suffix = f'@{suffix}'

        _clear_all_entries_in_cache_(
            list_name = f'{self._list_cache_name}{suffix}',
            hash_name = f'{self._hash_cache_name}{suffix}',
            set_name  = f'{self._set_cache_name}{suffix}'
        )
        
    @property
    def list_name(self):
        return self._list_cache_name


    @property
    def hash_name(self):
        return self._hash_cache_name


    @property
    def set_name(self):
        return self._set_cache_name
    

    @property
    def cache_name(self):
        return self._cache_name
