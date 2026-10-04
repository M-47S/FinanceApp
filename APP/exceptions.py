"""Кастомные исключения Finance App.

Живут отдельно от API, чтобы GUI-контейнер не тянул psycopg2.
"""


class FinanceAPIError(Exception):
    """Base exception for all errors raised by the finance API."""


# --- Database ---
class DBError(FinanceAPIError):
    """Base for database-related errors."""


class DBConnectionError(DBError):
    """Could not establish a connection to PostgreSQL."""


class DBQueryError(DBError):
    """SQL query failed to execute."""


# --- Validation ---
class ValidationError(FinanceAPIError):
    """Input parameters are invalid."""


class TableNotFoundError(ValidationError):
    """Requested table does not exist in the schema."""


class ColumnNotFoundError(ValidationError):
    """One or more requested columns do not exist in the table."""


# --- Excel ---
class ExcelError(FinanceAPIError):
    """Base for Excel-related errors."""


class ExcelReadError(ExcelError):
    """Failed to read an Excel file."""


class ExcelWriteError(ExcelError):
    """Failed to write an Excel file."""