#!/usr/bin/env python3
# server.py
from ..mdo.engine.configurator import LOGGING_YAML_PATH, get_global_config_value

from datetime import datetime
from pathlib  import Path
from os       import PathLike
from typing   import Dict, List, Optional

import subprocess
import os
import signal
import sys


exec_dir = os.getcwd()
os.chdir(os.path.join(Path(__file__).resolve().parent, '../'))


_apps    = get_global_config_value('service/apps')
_log_dir = get_global_config_value('service/log_base_dir')


def get_log_base_dir():
    return _log_dir


def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def select_apps(names : Optional[List[str]] = None):
    """Return dictionary of apps matching names. If names empty, return all."""
    if not names or len(names) < 1:
        return _apps
    
    selected = dict()

    for name, app in _apps.items():
        if name in names: selected[name] = app

    missing = set(names) - set(_apps.keys())
    # print('names: ', names)
    # print('_apps.keys():', _apps.keys())
    if missing:
        print(f"Warning: unknown app(s) {', '.join(missing)}")
    return selected



def build_envs(
    app_conf     : Dict,
    storage_conf : Dict
):
    env = os.environ.copy()
    
    env['ALLOWED_INCOMING_IPS'] = ','.join(app_conf['allowed_incoming_ips'])
    env['PROXY_URL']            = ','.join(app_conf['proxy_url'])

    storage_name = app_conf.get('storage', None)
    
    if storage_name is not None:
        redis_spec = storage_conf['redis'][storage_name]
        env['REDIS_HOST'] = str(redis_spec['host'])
        env['REDIS_PORT'] = str(redis_spec['port'])
        env['REDIS_DB']   = str(','.join(list(map(str, redis_spec['db']))))

        psql_spec = storage_conf['postgresql'][storage_name]
        env['PSQL_HOST']  = str(psql_spec['host'])
        env['PSQL_PORT']  = str(psql_spec['port'])
        env['PSQL_DB']    = str(','.join(list(map(str, psql_spec['db']))))
        env['PSQL_USER']  = str(psql_spec['user'])
        env['PSQL_PWSD']  = str(psql_spec['pwsd'])
    return env


def launch_apps(
    selected_apps : Dict,
    *, 
    log_base_dir  : PathLike[str],
    storage_conf  : Optional[Dict] = None
):
    for name, app in selected_apps.items():
        log_dir = os.path.join(log_base_dir, name)
        if app.get('log_dir', None) is not None and app.get('log_dir', None):
            log_dir = app['log_dir']
        
        os.makedirs(log_dir, exist_ok=True)
        timestamp = get_timestamp()
        log_path = os.path.join(log_dir, f'{name}-{timestamp}.log')
        print(f"Starting {app['script']} on port {app['port']} -> logging to {log_path}")
        log_file = open(log_path, 'a')

        env = build_envs(app, storage_conf)
        
        uvicorn_cmd = [
            'uv', 'run', '--no-sync',
            'python', '-m', 'uvicorn',
            app['script'].replace('/', '.').replace('.py', '') + ':app',
            '--host', app['host'],
            '--port', str(app['port']),
            '--log-config', LOGGING_YAML_PATH,
            '--workers', str(app.get('workers', 1))
        ]

        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                uvicorn_cmd,
                stdout        = log_file,
                stderr        = log_file,
                creationflags = DETACHED_PROCESS
            )
        else:
            subprocess.Popen(
                uvicorn_cmd,
                stdout     = log_file,
                stderr     = log_file,
                preexec_fn = os.setpgrp,
                env        = env
            )


def stop_apps(selected_apps : Dict):
    for name, app in selected_apps.items():
        port = app['port']
        if os.name == "nt":
            cmd = f'netstat -ano | findstr :{port}'
            result = subprocess.getoutput(cmd)
            if result:
                lines = result.strip().splitlines()
                for line in lines:
                    pid = line.split()[-1]
                    print(f"Killing PID {pid} on port {port}")
                    subprocess.call(f'taskkill /F /PID {pid}', shell=True)
            else:
                print(f"No process found on port {port}")
        else:
            cmd = f'lsof -ti:{port}'
            pids = subprocess.getoutput(cmd).strip().split()
            if pids and pids[0]:
                for pid in pids:
                    print(f"Killing PID {pid} on port {port}")
                    os.kill(int(pid), signal.SIGTERM)
            else:
                print(f"No process found on port {port}")
    print("Selected FastAPI apps stopped.")


def run_app(app : Dict):
    uvicorn_cmd = [
        'uv', 'run', '--no-sync',
        'python', '-m', 'uvicorn',
        app['script'].replace('/', '.').replace('.py', '') + ':app',
        '--host', app['host'],
        '--port', str(app['port']),
        '--log-config', LOGGING_YAML_PATH,
        '--workers', str(app.get('workers', 1))
    ]

    if os.name == "nt":
        subprocess.run(
            uvicorn_cmd,
            stdout=log_file,
            stderr=log_file,
        )
    else:
        subprocess.run(
            uvicorn_cmd,
            stdout=sys.stderr,
            stderr=sys.stderr,
        )


os.chdir(exec_dir)