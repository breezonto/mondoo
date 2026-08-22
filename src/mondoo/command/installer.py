from mondoo.configurator import get_global_config_value

from typing            import Optional
from typing_extensions import TypeAlias
from pathlib           import Path
from collections.abc   import Mapping
from os                import PathLike

import os
import subprocess
import getpass


SERIAL_NUMBER = 0

StrOrBytesPath: TypeAlias = str | bytes | PathLike[str] | PathLike[bytes]

def run(
    cmd_literal    : str,
    *,
    env            : Optional[Mapping[bytes, StrOrBytesPath] | Mapping[str, StrOrBytesPath]]  = None,
    capture_output : bool = False,
    text           : Optional[bool] = None,
    check          : bool = False
):
    global SERIAL_NUMBER
    print(f"{'*'*30}")
    print(f"instruction # {SERIAL_NUMBER} >> {cmd_literal}")

    result = subprocess.run(
        cmd_literal.split(' '), 
        env            = env, 
        capture_output = capture_output,
        text           = text,
        check          = check
    )
    
    print(f"{'*'*30}\n")
    
    SERIAL_NUMBER += 1

    return result


def psql_by_postgres(
    sql     : str,
    in_text : bool = False
):
    if in_text:
        subprocess.run(
            [
                'sudo', '-u', 'postgres',
                'psql', '-v', 'ON_ERROR_STOP=1'
            ],
            input = sql,
            check = True,
            text  = True
        )
    else:
        subprocess.run(
            [
                'sudo', '-u', 'postgres',
                'psql', '-v', 'ON_ERROR_STOP=1', '-c', sql,
            ],
            check=True,
        )


def install_database():
    # Update package index
    run("sudo apt update")

    # Install packages
    run("sudo apt install -y redis-server")
    run("sudo apt install -y postgresql postgresql-contrib")

    # Enable and start Redis
    run("sudo systemctl enable redis-server")
    run("sudo systemctl start redis-server")

    # Enable and start PostgreSQL
    run("sudo systemctl enable postgresql")
    run("sudo systemctl start postgresql")

    # Test Redis
    result = run(
        "redis-cli ping", 
        capture_output = True, 
        text           = True, 
        check          = True
    )

    if result.stdout.strip() == "PONG":
        print("✓ Redis is running.")
    else:
        raise RuntimeError("Redis did not respond with PONG.")

    print("✓ PostgreSQL installed and started.")


def setup_database():
    default_user = getpass.getuser()
    default_db   = get_global_config_value('storage/postgresql/db')[0]

    username = (input(f">> PostgreSQL username [press Enter, default={default_user}]: ").strip() or default_user)
    password = getpass.getpass(">> PostgreSQL password: ")
    dbname = input(f">> Database Name [press Enter, default = {default_db}]: ").strip() or default_db
    
    current_dir = Path(__file__).resolve().parent

    # create user
    user_template_path = Path(
        os.path.join(current_dir, '../template/sql/role_creation.sql.template')
    )
    user_sql_template : str = user_template_path.read_text()
    user_sql = user_sql_template.format(user_name=username, user_pwsd=password)
    psql_by_postgres(user_sql)
    
    # create database
    db_template_path = Path(
        os.path.join(current_dir, '../template/sql/database_creation.sql.template')
    )
    db_sql_template : str = db_template_path.read_text()
    db_sql = db_sql_template.format(user_name=username, db_name=dbname)
    psql_by_postgres(db_sql, in_text = True)

    # Grant privileges (optional since mdo owns the DB)
    psql_by_postgres("""
    GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {user_name};
    """.format(db_name=dbname, user_name=username))

    # create data table
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    dt_template_path = Path(
        os.path.join(current_dir, '../template/sql/table_creation.sql.template')
    )
    run(f"psql -U {username} -d {dbname} -v ON_ERROR_STOP=1 -f {str(dt_template_path)}", env=env)


def init():
    install_database()
    setup_database()


if __name__ == "__main__":
    init()