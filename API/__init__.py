"""API — публичный интерфейс для работы с БД PostgreSQL.

Скрывает внутренности (соединение, конфиг, исключения) и предоставляет
один класс FinanceAPI + набор кастомных исключений.
"""

from .api import FinanceAPI
from .config import DBConfig
from .exceptions import (
    FinanceAPIError,
    DBError,
    DBConnectionError,
    DBQueryError,
    ValidationError,
    TableNotFoundError,
    ColumnNotFoundError,
    ExcelError,
    ExcelReadError,
    ExcelWriteError,
)

__all__ = [
    "FinanceAPI",
    "DBConfig",
    "FinanceAPIError",
    "DBError",
    "DBConnectionError",
    "DBQueryError",
    "ValidationError",
    "TableNotFoundError",
    "ColumnNotFoundError",
    "ExcelError",
    "ExcelReadError",
    "ExcelWriteError",
]