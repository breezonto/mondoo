from dataclasses import dataclass

import os

PSQL_HOST  = os.getenv('PSQL_HOST', 'localhost')
PSQL_PORT  = os.getenv('PSQL_PORT', 5432)
PSQL_DB    = list(set(os.getenv('PSQL_DB').split(',')))
PSQL_USER  = os.getenv('PSQL_USER')
PSQL_PSSWD = os.getenv('PSQL_PWSD')

# PSQL_DB    = 'fd_meta'
# PSQL_USER  = 'ubuntu'
# PSQL_PSSWD = 'G.20260325'

@dataclass
class PostgresConfig:
    """PostgreSQL Connection Configuration"""

    host     : str = "localhost"
    port     : int = 5432
    database : str = "mydb"
    user     : str = "postgres"
    password : str = "your_password"

    # 连接池参数
    min_connections: int = 1
    max_connections: int = 10

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={self.user} password={self.password}"
        )
    

def get_default_psql_config():
    return PostgresConfig(
        host     = PSQL_HOST,
        port     = PSQL_PORT,
        database = PSQL_DB[0],
        user     = PSQL_USER,
        password = PSQL_PSSWD,
    )