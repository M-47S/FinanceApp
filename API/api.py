from pathlib import Path
from typing import Sequence

import pandas as pd

from .config import DBConfig
from .db import Database
from .exceptions import (
    ColumnNotFoundError,
    ExcelReadError,
    ExcelWriteError,
    TableNotFoundError,
    ValidationError,
)


class FinanceAPI:
    def __init__(self, config: DBConfig | None = None):
        self.config = config or DBConfig.from_env()
        self.db = Database(self.config)
        self.schema = self.config.schema

    # ---------- helpers ----------

    def _table_columns(self, table: str) -> set[str]:
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            rows = cur.fetchall()
        if not rows:
            raise TableNotFoundError(f"Table '{self.schema}.{table}' not found")
        return {r["column_name"] for r in rows}

    def _validate_columns(self, table: str, columns: Sequence[str]) -> None:
        existing = self._table_columns(table)
        missing = set(columns) - existing
        if missing:
            raise ColumnNotFoundError(
                f"Columns not found in '{self.schema}.{table}': {sorted(missing)}"
            )

    # ---------- 0. connection check ----------

    def ping(self) -> bool:
        """Return True if DB is reachable and credentials are valid."""
        with self.db.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            return cur.fetchone()["ok"] == 1
        
    # ---------- 1. load from dataframe into DB ----------

    def load_dataframe(self, table: str, df: pd.DataFrame) -> int:
        """
        Вставляет строки из DataFrame в таблицу.
        Колонки DataFrame должны совпадать с колонками таблицы.
        Возвращает число вставленных строк.
        """
        if df.empty:
            return 0

        self._table_columns(table)
        self._validate_columns(table, list(df.columns))

        cols = list(df.columns)
        col_sql = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))
        sql = (
            f'INSERT INTO "{self.schema}"."{table}" ({col_sql}) '
            f"VALUES ({placeholders})"
        )

        values = [
            tuple(None if pd.isna(v) else v for v in row)
            for row in df.itertuples(index=False, name=None)
        ]

        with self.db.cursor() as cur:
            cur.executemany(sql, values)
            return cur.rowcount

    # ---------- 2. load from Excel into DB ----------

    def load_from_excel(
        self,
        table: str,
        file_path: str | Path,
        sheet_name: str | int = 0,
    ) -> int:
        """Читает Excel и вставляет строки через load_dataframe()."""
        self._table_columns(table)  # ранняя проверка
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
        except Exception as e:
            raise ExcelReadError(f"Cannot read '{file_path}': {e}") from e
        return self.load_dataframe(table, df)

    # ---------- 3. unload from DB ----------

    def unload_to_dataframe(
        self,
        table: str,
        columns: Sequence[str] | None = None,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """SELECT specific columns from a table and return a DataFrame."""
        self._table_columns(table)
        if columns:
            self._validate_columns(table, columns)
            col_sql = ", ".join(f'"{c}"' for c in columns)
        else:
            col_sql = "*"

        sql = f'SELECT {col_sql} FROM "{self.schema}"."{table}"'
        params: list = []

        if limit is not None:
            if limit <= 0:
                raise ValidationError("limit must be a positive integer")
            sql += " LIMIT %s"
            params.append(limit)

        with self.db.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        return pd.DataFrame(rows)

    def unload_to_excel(
        self,
        table: str,
        file_path: str | Path,
        columns: Sequence[str] | None = None,
        limit: int | None = None,
        sheet_name: str = "Sheet1",
    ) -> int:
        """Dump selected rows to Excel. Returns the number of rows written."""
        df = self.unload_to_dataframe(table, columns, limit)
        try:
            df.to_excel(
                file_path,
                index=False,
                sheet_name=sheet_name,
                engine="openpyxl",
            )
        except Exception as e:
            raise ExcelWriteError(f"Cannot write '{file_path}': {e}") from e
        return len(df)

    # ---------- 4. custom SQL ----------

    def execute_sql(
        self,
        sql: str,
        params: Sequence | None = None,
    ) -> pd.DataFrame:
        """
        Execute raw SQL.
        - If it returns rows (SELECT/RETURNING) — returns a DataFrame.
        - If it doesn't (INSERT/UPDATE/DELETE without RETURNING) — returns empty DataFrame.
        """
        if not sql or not sql.strip():
            raise ValidationError("SQL is empty")

        with self.db.cursor() as cur:
            cur.execute(sql, params or ())
            if cur.description is None:
                return pd.DataFrame()
            rows = cur.fetchall()

        return pd.DataFrame(rows)
    
    def get_tables(self) -> list[str]:
        sql = """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema,))
            return [r["table_name"] for r in cur.fetchall()]

    def get_columns(self, table: str) -> list[str]:
        sql = """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            return [r["column_name"] for r in cur.fetchall()]
    
    def get_current_user_groups(self) -> list[str]:
        sql = """
            SELECT r.rolname FROM pg_auth_members m
            JOIN pg_roles r ON r.oid = m.roleid
            JOIN pg_roles u ON u.oid = m.member
            WHERE u.rolname = current_user
        """
        with self.db.cursor() as cur:
            cur.execute(sql)
            return [r["rolname"] for r in cur.fetchall()]
        
    def get_writable_columns(self, table: str) -> list[str]:
        """
        Колонки, доступные для ручной вставки.
        Исключает identity и generated (т.е. авто-генерируемые id).
        """
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND is_identity = 'NO'
              AND is_generated = 'NEVER'
            ORDER BY ordinal_position
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            return [r["column_name"] for r in cur.fetchall()]
        
    # ---------- manipulation helpers ----------
    
    def get_primary_key_columns(self, table: str) -> list[str]:
        sql = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            return [r["column_name"] for r in cur.fetchall()]

    def get_referenced_columns(self, table: str) -> set[str]:
        """Столбцы таблицы, на которые ссылаются FK из других таблиц."""
        sql = """
            SELECT DISTINCT a.attname AS column_name
            FROM pg_constraint c
            JOIN pg_class t      ON t.oid = c.confrelid
            JOIN pg_namespace n  ON n.oid = t.relnamespace
            JOIN pg_attribute a  ON a.attrelid = c.confrelid
                                AND a.attnum = ANY(c.confkey)
            WHERE c.contype = 'f'
              AND n.nspname = %s
              AND t.relname = %s
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            return {r["column_name"] for r in cur.fetchall()}

    def get_editable_columns(
        self, table: str, is_admin: bool = False,
    ) -> list[str]:
        """
        Колонки, доступные для редактирования.
        - identity / generated (т.е. id) — недоступны всем
        - FK-референсы — только админам
        """
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND is_identity = 'NO'
              AND is_generated = 'NEVER'
            ORDER BY ordinal_position
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            writable = [r["column_name"] for r in cur.fetchall()]

        if is_admin:
            return writable

        referenced = self.get_referenced_columns(table)
        return [c for c in writable if c not in referenced]

    def fetch_all(self, table: str, limit: int = 500) -> pd.DataFrame:
        """Все колонки таблицы, PK — в начале."""
        pk_cols = self.get_primary_key_columns(table)
        all_cols = self.get_columns(table)
        ordered = pk_cols + [c for c in all_cols if c not in pk_cols]
        return self.unload_to_dataframe(table, columns=ordered, limit=limit)

    def update_row(
        self, table: str, pk_values: dict, updates: dict,
    ) -> int:
        """UPDATE строки, идентифицированной по PK."""
        if not pk_values:
            raise ValidationError("Не указан первичный ключ")
        if not updates:
            return 0

        self._table_columns(table)
        self._validate_columns(table, list(updates.keys()))
        self._validate_columns(table, list(pk_values.keys()))

        set_sql = ", ".join(f'"{c}" = %s' for c in updates.keys())
        where_sql = " AND ".join(f'"{c}" = %s' for c in pk_values.keys())
        sql = f'UPDATE "{self.schema}"."{table}" SET {set_sql} WHERE {where_sql}'

        params = list(updates.values()) + list(pk_values.values())
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def delete_row(self, table: str, pk_values: dict) -> int:
        """DELETE строки, идентифицированной по PK."""
        if not pk_values:
            raise ValidationError("Не указан первичный ключ")

        self._table_columns(table)
        self._validate_columns(table, list(pk_values.keys()))

        where_sql = " AND ".join(f'"{c}" = %s' for c in pk_values.keys())
        sql = f'DELETE FROM "{self.schema}"."{table}" WHERE {where_sql}'

        with self.db.cursor() as cur:
            cur.execute(sql, list(pk_values.values()))
            return cur.rowcount