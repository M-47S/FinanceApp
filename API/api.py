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

    # ---------- 4. connection check ----------

    def ping(self) -> bool:
        """Return True if DB is reachable and credentials are valid."""
        with self.db.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            return cur.fetchone()["ok"] == 1

    # ---------- 1. load from Excel into DB ----------

    def load_from_excel(
        self,
        table: str,
        file_path: str | Path,
        sheet_name: str | int = 0,
    ) -> int:
        """
        Read an Excel file and INSERT rows into `table`.
        Columns in the file must match column names in the table.
        Returns the number of inserted rows.
        """
        self._table_columns(table)  # raises TableNotFoundError
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
        except Exception as e:
            raise ExcelReadError(f"Cannot read '{file_path}': {e}") from e

        if df.empty:
            return 0

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

    # ---------- 2. unload from DB ----------

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

    # ---------- 3. custom SQL ----------

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