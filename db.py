from sqlalchemy import create_engine
from contextlib import contextmanager
from config import DB_URL

# Cria a engine uma vez por processo
engine = create_engine(DB_URL)


@contextmanager
def get_connection():
    """Context manager simples para obter uma conexão SQLAlchemy.

    Usage:
        with get_connection() as conn:
            conn.execute(...)
    """
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()
