"""PostgreSQL connection and Gold table loading."""
import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect, text

TABLES = ["customers_gold", "transactions_gold", "customer_summary", "sales_summary"]


def build_database_url():
    """Encode credentials so characters such as @ cannot become part of the host."""
    user = quote_plus(os.environ["DB_USER"])
    password = quote_plus(os.environ["DB_PASSWORD"])
    host = os.environ["DB_HOST"]
    port = int(os.getenv("DB_PORT", "5432"))
    database = quote_plus(os.environ["DB_NAME"])
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"


def get_engine():
    return create_engine(build_database_url(), pool_pre_ping=True)


def verify_connection():
    engine = get_engine()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    finally:
        engine.dispose()


def load_to_postgres(gold):
    engine = get_engine()
    counts = {}
    try:
        with engine.begin() as connection:
            for table in TABLES:
                gold[table].to_sql(table, connection, if_exists="replace", index=False)
                counts[table] = len(gold[table])
    finally:
        engine.dispose()
    return counts


def get_table_counts():
    engine = get_engine()
    try:
        with engine.connect() as connection:
            existing = set(inspect(connection).get_table_names())
            return {
                table: connection.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar_one()
                for table in TABLES if table in existing
            }
    finally:
        engine.dispose()
