from typing import Optional, Dict

import redis
import os
import json


REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', 6379)
REDIS_DB   = list(set(map(int, os.getenv('REDIS_DB').split(','))))


rh = redis.Redis(
    host = REDIS_HOST, 
    port = REDIS_PORT, 
    db   = REDIS_DB[0], # REDIS_DB是一个数组
    decode_responses = True
)


def _write_data_to_redis_(
    record    : dict,
    *,
    id_field  : str,
    list_name : str,
    hash_name : str,
    set_name  : str
):
    id_name = record[id_field]
    rh.hset(hash_name, id_name, json.dumps(record))
    if not rh.sismember(set_name, id_name):
        rh.rpush(list_name, id_name)
        rh.sadd(set_name, id_name)
        

def _remove_data_from_redis_(
    id : str,
    *,
    list_name : str,
    hash_name : str,
    set_name  : str
):
    rh.hdel(hash_name, id)
    rh.lrem(list_name, 0, id)
    rh.srem(set_name, id)


def _read_data_from_redis_(
    id : str,
    *,
    list_name : str,
    hash_name : str,
    set_name  : str
) -> Optional[dict]:
    data = rh.hget(hash_name, id)
    if data:
        return json.loads(data)
    
    return None


def _clear_all_from_redis_(
    list_name : str,
    hash_name : str,
    set_name  : str
):
    fields = rh.hkeys(hash_name)
    if fields:
        rh.hdel(hash_name, *fields)

    rh.ltrim(list_name, 1, 0)
    
    members = rh.smembers(set_name)
    if members:
        rh.srem(set_name, *members)


class CacheHelper:
    def __init__(
        self,
        cache_name : str
    ):
        self._cache_name      = cache_name
        self._list_cache_name = f'{cache_name}@list'
        self._hash_cache_name = f'{cache_name}@hash'
        self._set_cache_name  = f'{cache_name}@set'


    def write_data(
        self, 
        obj      : dict,
        id_field : str,
        suffix   : str = ''
    ):
        _write_data_to_redis_(
            obj,
            id_field  = id_field, 
            list_name = f'{self._list_cache_name}-{suffix}',
            hash_name = f'{self._hash_cache_name}-{suffix}',
            set_name  = f'{self._set_cache_name}-{suffix}'
        )


    def read_record(
        self, 
        id     : str,
        suffix : str = ''
    ):
        return _read_data_from_redis_(
            id,
            list_name = f'{self._list_cache_name}-{suffix}',
            hash_name = f'{self._hash_cache_name}-{suffix}',
            set_name  = f'{self._set_cache_name}-{suffix}'
        )


    def remove_record(
        self,
        id     : str,
        suffix : str = ''
    ):
        _remove_data_from_redis_(
            id,
            list_name = f'{self._list_cache_name}-{suffix}',
            hash_name = f'{self._hash_cache_name}-{suffix}',
            set_name  = f'{self._set_cache_name}-{suffix}'
        )


    def read_all_data(
        self,
        suffix : str = ''
    ):
        ids = rh.lrange(''.join([self._list_cache_name, '-', suffix]), 0, -1)
        data = []
        for curr_id in ids:
            instance = _read_data_from_redis_(
                curr_id,
                list_name = f'{self._list_cache_name}-{suffix}',
                hash_name = f'{self._hash_cache_name}-{suffix}',
                set_name  = f'{self._set_cache_name}-{suffix}'              
            )
            if instance:
                data.append(instance)
        return data


    def clear_all_data(
        self,
        suffix : str = ''
    ):
        _clear_all_from_redis_(
            list_name = f'{self._list_cache_name}-{suffix}',
            hash_name = f'{self._hash_cache_name}-{suffix}',
            set_name  = f'{self._set_cache_name}-{suffix}'
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
