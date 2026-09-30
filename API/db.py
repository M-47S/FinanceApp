from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from .config import DBConfig
from .exceptions import DBConnectionError, DBQueryError


class Database:
    def __init__(self, config: DBConfig):
        self.config = config

    @contextmanager
    def connect(self):
        try:
            conn = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                dbname=self.config.dbname,
                user=self.config.user,
                password=self.config.password,
                options=f"-c search_path={self.config.schema},public",
            )
        except Exception as e:
            # Ловим всё, включая UnicodeDecodeError от русских сообщений Windows
            msg = str(e) or e.__class__.__name__
            raise DBConnectionError(f"Не удалось подключиться к БД: {msg}") from e
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def cursor(self):
        """Open a cursor; commit on success, rollback on error."""
        with self.connect() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    yield cur
                conn.commit()
            except psycopg2.Error as e:
                conn.rollback()
                raise DBQueryError(str(e)) from e
            except Exception:
                conn.rollback()
                raise