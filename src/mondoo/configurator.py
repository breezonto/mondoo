from os      import PathLike
from typing  import List, Optional, Dict
from pathlib import Path
import os
import yaml


ASSETS_YAML_PATH  = os.path.join(Path(__file__).resolve().parent, 'config/assets.yaml')
SERVICE_YAML_PATH = os.path.join(Path(__file__).resolve().parent, 'config/service.yaml')
STORAGE_YAML_PATH = os.path.join(Path(__file__).resolve().parent, 'config/storage.yaml')

LOGGING_YAML_PATH     = os.path.join(Path(__file__).resolve().parent, 'config/internal/logging.yaml')
MCP_LOGGING_YAML_PATH = os.path.join(Path(__file__).resolve().parent, 'config/internal/mcp_logging.yaml')

DOCUMENTS_DIR     = '/home/guard/workspace/documents'


def load_yaml_config(conf_path : PathLike[str]) -> Dict:
    with open(conf_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return cfg


assets  = load_yaml_config(ASSETS_YAML_PATH)
storage = load_yaml_config(STORAGE_YAML_PATH)
service = load_yaml_config(SERVICE_YAML_PATH)

global_config = {
    'assets'  : assets,
    'storage' : storage,
    'service' : service 
}

"""
    Configurations of Resources
"""
ENV_OBJECT_DIR = os.getenv('OBJECT_DIR')
ENV_SOURCE_DIR = os.getenv('SOURCE_DIR')

OBJECT_DIR = assets['object_dir'] if ENV_OBJECT_DIR == '' or ENV_OBJECT_DIR is None else ENV_OBJECT_DIR
SOURCE_DIR = assets['source_dir'] if ENV_SOURCE_DIR == '' or ENV_SOURCE_DIR is None else ENV_SOURCE_DIR

SOCK_PATH_4_KALEIDO = assets['sock_path_4_kaleido']
SOCK_PATH_4_META    = assets['sock_path_4_meta']
SOCK_PATH_4_GATEWAY = assets['sock_path_4_gateway']

"""
    Configurations of data storage subsystem
"""
LOCAL_LLM_MODEL_PATH       = assets['default_local_llm_path']
LOCAL_EMBEDDING_MODEL_PATH = assets['default_embedding_model_path']


"""
    Configurations of URLs and endpoints
"""
BACKEND_BASE = 'http://10.8.100.3'
REMOTE_API_ENDPOINT = assets['remote_llm_api']
LOCAL_API_ENDPOINT  = assets['local_llm_api']
API_ENDPOINT = {
    'remote' : REMOTE_API_ENDPOINT,
    'local'  : LOCAL_API_ENDPOINT
}

AMAP_URI = 'https://restapi.amap.com/v3/weather/weatherInfo'
AMAP_KEY = '5a71decd973017adc209ff068b509a47'


"""
    Misceallaneous Configurations
"""
END_FRAME = '\n\t\n\t\n'


def get_global_config_value(key_path: str):
    chain = key_path.split('/')
    val = global_config
    for entry in chain:
        val = val[entry]
    return val



def set_global_config_value(key_path: str, obj):
    chain = key_path.split('/')

    parent = global_config

    for entry in chain[:-1]:
        parent = parent[entry]

    parent[chain[-1]] = obj
    

config_file_path = {
    'assets'  : ASSETS_YAML_PATH,
    'service' : SERVICE_YAML_PATH,
    'storage' : STORAGE_YAML_PATH
}


"""
    Data Storage
"""

FD_TABLE = os.getenv('fd_table', 'file_records')

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', 6379)
REDIS_DB   = list(set(map(int, os.getenv('REDIS_DB').split(','))))

# PSQL_HOST = storage['postgresql']['host']
# PSQL_PORT = storage['postgresql']['port']
# PSQL_DB   = storage['postgresql']['db']


def get_configuration_file_path(names : Optional[List[str]] = None):
    global config_file_path

    opath = []
    if names is not None and len(names) > 0:
        for name, path in config_file_path.items():
            if name in names:
                opath.append(path)
    else:
        opath = config_file_path.values()
    
    return opath