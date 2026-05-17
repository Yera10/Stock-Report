import os
from sqlalchemy import create_engine as _create_engine
from sqlalchemy.dialects.mysql import insert


def get_engine():
    return _create_engine(os.environ["DB_URL"])


def insert_ignore(table, conn, keys, data_iter):
    stmt = insert(table.table).prefix_with("IGNORE")
    conn.execute(stmt, [dict(zip(keys, row)) for row in data_iter])
