from mondoo.mdo.io.file.generic        import *
from ..configurator    import SOURCE_DIR, OBJECT_DIR
from ..dbc             import init_db_client_from_default_config, get_current_dbc

from datetime import datetime, timezone
from os       import PathLike
from pathlib  import Path
from typing   import List

from mondoo.mdo.io.db.redis import *

import os
import json
import threading
import logging
import uuid

logger = logging.getLogger(__name__)

class classproperty:
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, obj, cls):
        return self.fget(cls)


file_task_lock = threading.Lock()
    

init_db_client_from_default_config()


class FileManager: 
    _registry        = {}
    _default_object_dir      = OBJECT_DIR
    _default_source_file_dir = SOURCE_DIR
    _default_file_table_name = 'file_records'
    _file_record_cache_name  = 'file_record_cache'
    _cache_client = CacheWrapper(_file_record_cache_name)

    @classmethod
    def register(cls, *extensions):
        def decorator(reader_cls):
            for ext in extensions:
                cls._registry[ext.lower()] = reader_cls
            return reader_cls
        return decorator
    
    def __init__(self):
        pass
    
    @classmethod
    def open(
        cls, 
        path       : PathLike[str],
        meth_names : List[str],
        file_id    : str = None,
        **kwargs
    ):
      path_obj = Path(path)
      if not path_obj.exists():
          raise ValueError(f"Path {path} doesn't exist")
      
      if path_obj.is_file():
        ext  = path_obj.suffix.split('.')[-1]
        reader_cls = cls._get_reader_(ext)
        
        descriptor = reader_cls.set_descriptor(
            path       = path,
            cache_path = None,
            file_id    = file_id
        )
        
        obj = reader_cls.read(
            path              = path,
            meth_names        = meth_names, # meth_names
            intermediate_path = None,
            descriptor        = descriptor,
            **kwargs
        )
        
        return [obj]
        
      elif path_obj.is_dir():
          pass
    
    @classmethod
    def record(
        cls,
        file_id : str,
        record     : FileRecord 
    ):  
        db = get_current_dbc(is_async=False)

        if record.curr_slice == 0:
            try:
                data = {
                    'file_id'      : file_id,
                    'source_path'  : record.desc.source_path,
                    'target_path'  : record.desc.target_path,
                    'stem'         : record.desc.stem,
                    'ext'          : record.desc.ext,
                    'size'         : record.desc.size,
                    'stage'        : record.stage,
                    'curr_slice'   : record.curr_slice,
                    'total_slices' : record.total_slices,
                    'total_chunks' : record.total_chunks
                }

                db.insert(
                    table_name = cls._default_file_table_name,
                    data       = data,
                    returning  = False 
                )
            except Exception as e:
                raise RuntimeError(f"Failed creating new record: <{file_id}>") from e
        else:
            try:
                attributes = {
                    'source_path'  : record.desc.source_path,
                    'target_path'  : record.desc.target_path,
                    'size'         : record.desc.size,
                    'stage'        : record.stage,
                    'curr_slice'   : record.curr_slice,
                    'total_chunks' : record.total_chunks
                }
                
                db.update(
                    table_name   = cls._default_file_table_name,
                    data         = attributes,
                    where        = "file_id = %s",
                    where_params = (file_id,),
                    returning    = False
                )

            except Exception as e:
                raise RuntimeError(f"Failed updating record: <{file_id}>") from e
        
        record_time = datetime.now(timezone.utc)
        record_time_str = record_time.strftime("%Y-%m-%d %H:%M:%S.") + f"{record_time.microsecond // 1000:03d}"
        record_obj = record.model_dump()
        record_obj['complete_upload_time'] = record_time_str
        # write_data_to_redis(record_obj)
        cls._cache_client.write_data(record_obj, id_field='file_id')

    
    @classmethod
    async def record_async(
        cls,
        file_id : str,
        record  : FileRecord 
    ):  
        db = get_current_dbc(is_async=True)

        if record.curr_slice == 0:
            try:
                data = {
                    'file_id'      : file_id,
                    'source_path'  : record.desc.source_path,
                    'target_path'  : record.desc.target_path,
                    'stem'         : record.desc.stem,
                    'ext'          : record.desc.ext,
                    'size'         : record.desc.size,
                    'stage'        : record.stage,
                    'curr_slice'   : record.curr_slice,
                    'total_slices' : record.total_slices,
                    'total_chunks' : record.total_chunks
                }

                # NOTE: await
                await db.insert_async(
                    table_name = cls._default_file_table_name,
                    data       = data,
                    returning  = False 
                )
            except Exception as e:
                raise RuntimeError(f"Failed creating new record <{file_id}>") from e
        else:
            try:
                attributes = {
                    'source_path'  : record.desc.source_path,
                    'target_path'  : record.desc.target_path,
                    'size'         : record.desc.size,
                    'stage'        : record.stage,
                    'curr_slice'   : record.curr_slice,
                    'total_chunks' : record.total_chunks
                }
                
                # NOTE: await
                await db.update_async(
                    table_name   = cls._default_file_table_name,
                    data         = attributes,
                    where        = "file_id = %s",
                    where_params = (file_id,),
                    returning    = False
                )

            except Exception as e:
                raise RuntimeError(f"Failed updating record: <{file_id}>") from e
        
        record_time = datetime.now(timezone.utc)
        record_time_str = record_time.strftime("%Y-%m-%d %H:%M:%S.") + f"{record_time.microsecond // 1000:03d}"
        record_obj = record.model_dump()
        record_obj['complete_upload_time'] = record_time_str
        # write_data_to_redis(record_obj)
        cls._cache_client.write_data(record_obj, id_field='file_id')

    @classmethod
    def remove(cls, file_id):
        # remove_file_record(file_id)
        cls._cache_client.remove_record(file_id)
        try:
            db = get_current_dbc(is_async=False)
            
            db.remove(
                table_name   = cls._default_file_table_name,
                where        = "file_id = %s",
                where_params = (file_id,)
            )
        except Exception as e:
            raise RuntimeError(f"Failed deleting data row from PostgreSQL: {e}")

    
    @classmethod
    async def remove_async(cls, file_id):
        # remove_file_record(file_id)
        cls._cache_client.remove_record(file_id)
        try:
            db = get_current_dbc(is_async=True)
            # NOTE: await
            await db.remove_async(
                table_name   = cls._default_file_table_name,
                where        = "file_id = %s",
                where_params = (file_id,)
            )
        except Exception as e:
            raise RuntimeError(f"Failed deleting data row from PostgreSQL: {e}")


    @classmethod
    def get(
        cls,
        file_id : str
    ) -> FileRecord:
        data = cls._cache_client.read_record(file_id)
        if data:
            descriptor = FileDesc(
                file_id     = data['file_id'],
                source_path = data['source_path'],
                target_path = data['target_path'],
                stem        = data['stem'],
                ext         = data['ext'],
                size        = data['size'] 
            )
            
            return FileRecord(
                desc         = descriptor,
                stage        = data['stage'],
                curr_slice   = data['curr_slice'],
                total_slices = data['total_slices'],
                total_chunks = data['total_chunks']
            )
        
        return None
    
    @classmethod
    def get_all(cls) -> List[FileRecord]:
        rows = cls._cache_client.read_all_data()
        records = []
        for row in rows:
            data = row

            descriptor = FileDesc(
                file_id     = data['file_id'],
                source_path = data['source_path'],
                target_path = data['target_path'],
                stem        = data['stem'],
                ext         = data['ext'],
                size        = data['size'] 
            )
            
            records.append(FileRecord(
                desc         = descriptor,
                stage        = data['stage'],
                curr_slice   = data['curr_slice'],
                total_slices = data['total_slices'],
                total_chunks = data['total_chunks']
            ))
            
        return records
    
    @classmethod
    def clean_all(cls):
        cls._cache_client.clear_all_data(
            cls._cache_client.list_name,
            cls._cache_client.hash_name,
            cls._cache_client.set_name,
        )
        
    @classmethod
    def dump(
        cls,
        obj
    ) -> PathLike[str]:
        ext                        = obj.descriptor.ext
        reader_cls                 = cls._get_reader_(ext)
        target_path                = os.path.join(cls._default_object_dir, obj.descriptor.stem)
        obj.descriptor.target_path = target_path
        reader_cls.dump(obj.body, target_path)
        return target_path
        
    @classmethod
    def export(
        cls,
        obj
    ) -> tuple[PathLike[str], int, dict]:
        ext                        = obj.descriptor.ext
        reader_cls                 = cls._get_reader_(ext)
        target_path                = os.path.join(cls._default_object_dir, obj.descriptor.stem)
        obj.descriptor.target_path = target_path
        num_chunks, ret_obj = reader_cls.export(obj.body, obj.descriptor, target_path)
        return target_path, num_chunks, ret_obj
    
    @classmethod
    def get_available_methods(cls, ext : str):
        reader_cls = cls._get_reader_(ext)
        return reader_cls.methods
    
    
    @classproperty
    def context(cls) -> str:
        records = cls.get_all()
        views = [record.user_view for record in records]

        prompt = f"""
你当前可以访问一个文件管理系统。系统中已有文件的信息如下。

每个文件包含以下字段：
- filename：文件名（不包含扩展名）
- type：文件扩展名
- size：文件大小（字节）
- stage：当前处理阶段
- num_chunk：文件被拆分的 chunk 数量

当前系统中的文件列表如下：

{json.dumps(views, indent=2, ensure_ascii=False)}

请根据这些信息回答用户的问题。如果用户提到文件，请优先匹配文件名进行准确引用。
"""
        return prompt.strip()
        
    
    @classmethod
    def _get_reader_(cls, ext: str):
        try:
            return cls._registry[ext.lower()]
        except KeyError:
            raise ValueError(f"Unsupported extension: {ext}")
    
    
    @classproperty
    def registry(cls):
        return cls._registry.keys()
       
    @classproperty
    def object_dir(cls):
        return cls._default_object_dir
    
    @classproperty
    def source_dir(cls):
        return cls._default_source_file_dir
        

logger.info("\"The Object Directory [%s]\"", FileManager.object_dir)
logger.info("\"The Source Directory [%s]\"", FileManager.source_dir)


from mondoo.mdo.io.reader import *