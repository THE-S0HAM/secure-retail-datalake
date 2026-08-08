"""Load Gold CSV data into PostgreSQL using simple replace loads."""
from sqlalchemy import create_engine, text
from config.settings import db_url

TABLES = ["customers_gold", "transactions_gold", "customer_summary", "sales_summary"]


def get_engine():
    return create_engine(db_url(), pool_pre_ping=True)


def verify_connection():
    engine = get_engine()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    engine.dispose()
    return True


def load_gold_data(gold_data):
    """Replace current analytical tables, making repeated full runs idempotent."""
    engine = get_engine()
    counts = {}
    try:
        with engine.begin() as connection:
            for table_name in TABLES:
                frame = gold_data[table_name]
                frame.to_sql(table_name, connection, if_exists="replace", index=False)
                counts[table_name] = len(frame)
    finally:
        engine.dispose()
    return counts


def required_tables_exist():
    engine = get_engine()
    try:
        with engine.connect() as connection:
            rows = connection.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
            tables = {row[0] for row in rows}
        return all(table in tables for table in TABLES)
    finally:
        engine.dispose()
