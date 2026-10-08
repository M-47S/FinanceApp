import logging
import psycopg2

from .report_parser import parse_monthly_report

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

logger = logging.getLogger(__name__)

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

    def load_dataframe(
        self,
        table: str,
        df: pd.DataFrame,
        *,
        source: str | None = None,
        row_numbers: Sequence[int] | None = None,
    ) -> int:
        """
        Построчная вставка с логом неудачных строк.

        source      — имя файла (для лога).
        row_numbers — список 1-индексированных номеров рядов в исходном файле
                    (по одному на каждую строку df). Если None —
                    используется порядковый номер df.
        """
        if df.empty:
            logger.info("load_dataframe: '%s' — пустой DataFrame", table)
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

        values_rows = [
            tuple(None if pd.isna(v) else v for v in row)
            for row in df.itertuples(index=False, name=None)
        ]

        src = source or "<dataframe>"
        inserted = 0
        failed = 0

        with self.db.cursor() as cur:
            for i, values in enumerate(values_rows, start=1):
                excel_row = row_numbers[i - 1] if row_numbers else i
                cur.execute("SAVEPOINT sp_row")
                try:
                    cur.execute(sql, values)
                    cur.execute("RELEASE SAVEPOINT sp_row")
                    inserted += 1
                except psycopg2.Error as e:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_row")
                    failed += 1
                    signature = dict(zip(cols, values))
                    logger.error(
                        "INSERT FAILED | table=%s.%s | source=%s | row=%d | "
                        "record=%r | error=%s",
                        self.schema, table, src, excel_row,
                        signature, str(e).strip(),
                    )

        logger.info(
            "load_dataframe: '%s.%s' | source=%s | inserted=%d | failed=%d",
            self.schema, table, src, inserted, failed,
        )
        return inserted
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
        
    def get_foreign_keys(self, table: str) -> dict[str, dict]:
        """
        Возвращает {column_name: {'ref_table': ..., 'ref_column': ...}}
        для всех FK-столбцов таблицы.
        Использует pg_constraint — не зависит от прав и работает стабильно.
        """
        sql = """
            SELECT
                a.attname         AS fk_column,
                tref.relname      AS ref_table,
                aref.attname      AS ref_column
            FROM pg_constraint c
            JOIN pg_class      t    ON t.oid  = c.conrelid
            JOIN pg_namespace  n    ON n.oid  = t.relnamespace
            JOIN pg_class      tref ON tref.oid = c.confrelid
            JOIN pg_attribute  a    ON a.attrelid = c.conrelid
                                AND a.attnum  = ANY(c.conkey)
            JOIN pg_attribute  aref ON aref.attrelid = c.confrelid
                                AND aref.attnum  = ANY(c.confkey)
            WHERE c.contype   = 'f'
            AND n.nspname   = %s
            AND t.relname   = %s
            ORDER BY a.attname
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            return {
                r["fk_column"]: {
                    "ref_table": r["ref_table"],
                    "ref_column": r["ref_column"],
                }
                for r in cur.fetchall()
            }
    
    def get_label_column(self, table: str) -> str | None:
        """
        Подбирает «отображаемую» колонку для dropdown'а —
        первую текстовую колонку. Если таких нет — None.
        """
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name   = %s
              AND data_type IN ('text', 'character varying', 'character')
            ORDER BY ordinal_position
            LIMIT 1
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            row = cur.fetchone()
            return row["column_name"] if row else None

    def get_fk_options(self, ref_table: str) -> list[tuple]:
        """
        Возвращает [(pk_value, label), ...] для dropdown'а.
        label = "<pk> - <name>", если у ref_table есть текстовая колонка,
        иначе label = "<pk>".
        """
        pk_cols = self.get_primary_key_columns(ref_table)
        if not pk_cols:
            return []

        pk = pk_cols[0]
        label_col = self.get_label_column(ref_table)

        if label_col:
            sql = (
                f'SELECT "{pk}" AS pk, "{label_col}" AS label '
                f'FROM "{self.schema}"."{ref_table}" '
                f'ORDER BY "{label_col}"'
            )
        else:
            sql = (
                f'SELECT "{pk}" AS pk, "{pk}"::text AS label '
                f'FROM "{self.schema}"."{ref_table}" '
                f'ORDER BY "{pk}"'
            )

        with self.db.cursor() as cur:
            cur.execute(sql)
            return [(r["pk"], r["label"]) for r in cur.fetchall()]

    def get_nullable_columns(self, table: str) -> set[str]:
        """Множество колонок, куда можно вставить NULL."""
        sql = """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name   = %s
              AND is_nullable  = 'YES'
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (self.schema, table))
            return {r["column_name"] for r in cur.fetchall()}
        
    def load_monthly_report(self, table: str, file_path) -> dict:
        """
        Загрузка месячного отчёта (формат 'Август.xlsx') в таблицу transactions.
        Возвращает {'total': int, 'inserted': int, 'failed': int}.
        """
        parsed = parse_monthly_report(file_path)
        total = len(parsed.df)
        logger.info(
            "Report '%s': %02d.%d, строк=%d",
            file_path, parsed.month, parsed.year, total,
        )

        df = parsed.df
        reason_map = self._name_to_id("reasons")
        type_map = self._name_to_id("op_types")

        rows: list[dict] = []
        row_numbers: list[int] = []
        failed = 0

        for _, r in df.iterrows():
            excel_row = int(r["_excel_row"])
            reason_id = self._resolve_reason(r["reason_name"], reason_map)
            type_id = type_map.get(r["type_name"])

            if reason_id is None:
                failed += 1
                logger.error(
                    "INSERT FAILED | table=%s.%s | source=%s | row=%d | "
                    "record=%r | error=reason '%s' not found",
                    self.schema, table, str(file_path), excel_row,
                    {
                        "op_date": r["op_date"],
                        "amount": r["amount"],
                        "reason_name": r["reason_name"],
                        "type_name": r["type_name"],
                    },
                    r["reason_name"],
                )
                continue

            if type_id is None:
                failed += 1
                logger.error(
                    "INSERT FAILED | table=%s.%s | source=%s | row=%d | "
                    "record=%r | error=op_type '%s' not found",
                    self.schema, table, str(file_path), excel_row,
                    {
                        "op_date": r["op_date"],
                        "amount": r["amount"],
                        "reason_name": r["reason_name"],
                        "type_name": r["type_name"],
                    },
                    r["type_name"],
                )
                continue

            rows.append({
                "amount": r["amount"],
                "op_date": r["op_date"],
                "reason_id": reason_id,
                "type_id": type_id,
            })
            row_numbers.append(excel_row)

        insert_df = pd.DataFrame(rows, columns=["amount", "op_date",
                                                "reason_id", "type_id"])

        inserted = self.load_dataframe(
            table, insert_df,
            source=str(file_path),
            row_numbers=row_numbers,
        )

        return {"total": total, "inserted": inserted, "failed": failed}


    def _name_to_id(self, table: str) -> dict[str, int]:
        """{name: id} для справочника reasons/op_types."""
        sql = f'SELECT id, name FROM "{self.schema}"."{table}"'
        with self.db.cursor() as cur:
            cur.execute(sql)
            return {r["name"]: r["id"] for r in cur.fetchall()}


    @staticmethod
    def _resolve_reason(source: str, mapping: dict[str, int]) -> int | None:
        """
        Источник → id в reasons.
        Правило:
        1) целиком («Еда» → id)
        2) первая часть до «|» («Помощь|Анастасия» → «Помощь»)
        """
        if not source:
            return None
        s = source.strip()
        if s in mapping:
            return mapping[s]
        if "|" in s:
            head = s.split("|", 1)[0].strip()
            if head in mapping:
                return mapping[head]
        return None