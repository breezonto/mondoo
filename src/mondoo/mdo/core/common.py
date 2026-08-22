from mondoo.configurator import BACKEND_BASE, MCP_LOGGING_YAML_PATH

from datetime import datetime
from pathlib  import Path

import yaml


def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


BASE_LOG_DIR = Path('logs')


def setup_mcp_logging(mcp_server_name: str):
    config_path = MCP_LOGGING_YAML_PATH

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Create service log directory
    service_log_dir = BASE_LOG_DIR / 'mcp' / mcp_server_name
    service_log_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped logfile
    ts = get_timestamp()

    logfile = service_log_dir / f"{mcp_server_name}-{ts}.log"

    # Inject logfile path
    config["handlers"]["mcp_file"]["filename"] = str(logfile)

    # logging.config.dictConfig(config)

    return config