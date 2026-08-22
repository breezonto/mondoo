from mondoo.configurator import load_yaml_config, set_global_config_value

from os       import PathLike
from argparse import _SubParsersAction, ArgumentParser
from pathlib  import Path
from typing   import Dict

import argparse
import os
import sys


"""
    @TODO comment
"""

def build_command_init_subparser(subparsers : _SubParsersAction):
    p : ArgumentParser = subparsers.add_parser('init')
    p.add_argument(
        '--install',
        action = 'store_true',
        help   = "Install the database dependencies, PostgreSQL, Redis and SQLite" 
    )
    p.add_argument(
        '--setup',
        action = 'store_true',
        help   = "Automatically setup user, database and data table"
    )
    p.set_defaults(func=command_init)

    return subparsers


"""
    @TODO comment
"""

def command_init(args):
    from .command.installer import install_database, setup_database
    if not args.install and not args.setup:
        print("No option selected, Please enter --install or --setup")
        return
    
    if args.install:
        install_database()

    if args.setup:
        setup_database()


"""
    @TODO comment
"""

def build_command_launch_subparser(subparsers : _SubParsersAction):
    p : ArgumentParser = subparsers.add_parser('launch')
    p.add_argument(
        '-C', '--conf-file-paths',
        nargs='*',
        metavar = "CONFIG FILE PATH(S)",
        help = "List of config file path(s) OR the directory including all of them"
    )
    p.add_argument(
        "--filter",
        nargs   = '+',
        metavar = 'SERVICES',
        help    = "List of services to launch"
    )

    p.set_defaults(func=command_launch)

    return subparsers


"""
    @TODO comment
"""

def command_launch(args):
    from .command.server import get_log_base_dir, select_apps, launch_apps

    if args.conf_file_paths is not None and len(args.conf_file_paths) > 0:
        pivotal_path = Path(args.conf_file_paths[0])
        cfgs = dict()
        
        if pivotal_path.is_dir() and len(args.conf_file_paths) == 1:
            config_paths = [c.resolve() for c in pivotal_path.glob('*.yaml')]
            for config_path in config_paths: 
                name = config_path.stem
                cfgs[name] = load_yaml_config(str(config_path))
        
        elif pivotal_path.is_dir():
            print("Only accept one directory inclduing config yaml files", file=sys.stderr)
        
        elif pivotal_path.is_file():
            for conf_path in args.conf_file_paths:
                config_path = Path(conf_path).resolve()
                name = config_path.stem
                cfgs[name] = load_yaml_config(str(config_path))

        service      : Dict          = cfgs['service']
        apps         : Dict          = service['apps']
        log_base_dir : PathLike[str] = service.get('log_base_dir', './logs')

        set_global_config_value('service', cfgs['service'])
    else:
        apps         = select_apps()
        log_base_dir = get_log_base_dir()


    if args.filter is not None:
        filtered_app_names = args.filter
        filtered_apps = dict()
        for name, app in apps.items():
            if name in filtered_app_names:
                filtered_apps[name] = app
        apps = filtered_apps
    
    launch_apps(
        apps, 
        log_base_dir = log_base_dir,
        storage_conf = cfgs.get('storage', None)
    )
    

"""
    @TODO comment
"""
def build_command_run_subparser(subparsers : _SubParsersAction):
    p : ArgumentParser = subparsers.add_parser('run')
    p.add_argument('service_name',      help = 'The would launched service app name')
    p.add_argument(
        '--host', 
        type = str,
        help = "The host of run service"
    )
    p.add_argument(
        '--port', 
        type = int,
        help = "The port number of run service"
    )
    p.add_argument(
        '--proxy-url', 
        type = str,
        help = "Exposed URL for proxy"
    )
    p.add_argument(
        '--log-dir', 
        type = str,
        help = "The directory of ouput log of run service"
    )
    p.add_argument(
        '--storage-backend', 
        type = str,
        help = "Picked data storage backend"
    )
    p.set_defaults(func=command_run)

    return subparsers


"""
    @TODO comment
"""

def command_run(args):
    from .command.server import run_app, select_apps
    apps = select_apps()
    name = args.service_name
    app  = apps[name]

    app['host']      = args.host      if args.host      is not None else app['host']
    app['port']      = args.port      if args.port      is not None else app['port']
    app['proxy_url'] = args.proxy_url if args.proxy_url is not None else app['proxy_url']

    run_app(app)
    

"""
    @TODO comment
""" 

def build_command_stop_subparser(subparsers : _SubParsersAction):
    p : ArgumentParser = subparsers.add_parser('stop')
    p.add_argument('service_name', type= str, help = 'The would stopped service app name')
    p.set_defaults(func=command_stop)

    return subparsers


"""
    @TODO comment
"""

def command_stop(args):
    from .command.server import select_apps, stop_apps
    apps = select_apps([args.service_name])
    stop_apps(apps)


"""
    @TODO comment
"""
def build_command_config_subparser(subparsers : _SubParsersAction):
    p : ArgumentParser = subparsers.add_parser('config')
    p.add_argument(
        '--dump', '-D',
        nargs   = '*',
        metavar = "CONFIG DOMAIN",
        default = None,
        help    = "List of configuration files"
    )
    p.add_argument(
        '--out-dir', '-O',
        type    = str,
        default = None,
        help    = "Output directory of saving config files"
    )

    p.set_defaults(func=command_config)

    return subparsers


"""
    @TODO comment
"""

def command_config(args):
    import shutil
    from mondoo.configurator import get_configuration_file_path
    if args.dump is not None:
        select = args.dump
        config_path = get_configuration_file_path(select)
    else:
        config_path = get_configuration_file_path()

    dst = Path.cwd()
    if args.out_dir is not None:
        dst = args.out_dir
        os.makedirs(dst, exist_ok=True)

    for current_path in config_path:
        src = Path(current_path)
        shutil.copy(src, dst)


def main():
    parser = argparse.ArgumentParser(prog='estar')

    subparsers = parser.add_subparsers(dest='command', required=True)

    build_command_init_subparser(subparsers)
    build_command_config_subparser(subparsers)
    build_command_launch_subparser(subparsers)
    build_command_run_subparser(subparsers)
    build_command_stop_subparser(subparsers)

    args = parser.parse_args()
    args.func(args)