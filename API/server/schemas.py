"""Pydantic-модели запросов и ответов."""

from typing import Any

from pydantic import BaseModel, Field


# ---------- auth ----------

class LoginRequest(BaseModel):
    user: str
    password: str
    host: str | None = None
    port: int | None = None
    dbname: str | None = None
    db_schema: str | None = None


class LoginResponse(BaseModel):
    token: str
    user: str
    groups: list[str]
    is_admin: bool
    dbname: str
    db_schema: str


class LogoutResponse(BaseModel):
    ok: bool


# ---------- generic ----------

class PingResponse(BaseModel):
    ok: bool


class TablesResponse(BaseModel):
    tables: list[str]


class ColumnsResponse(BaseModel):
    columns: list[str]


class ForeignKeysResponse(BaseModel):
    fks: dict[str, dict[str, str]]


class FkOptionsResponse(BaseModel):
    options: list[tuple[Any, str]]


# ---------- data ----------

class RowsResponse(BaseModel):
    rows: list[dict[str, Any]]
    count: int


class InsertResponse(BaseModel):
    inserted: int


class UpdateRowRequest(BaseModel):
    table: str
    pk_values: dict[str, Any]
    updates: dict[str, Any]


class UpdateRowResponse(BaseModel):
    updated: int


class DeleteRowRequest(BaseModel):
    table: str
    pk_values: dict[str, Any]


class DeleteRowResponse(BaseModel):
    deleted: int


# ---------- sql ----------

class SqlRequest(BaseModel):
    sql: str
    params: list[Any] | None = None


class SqlResponse(BaseModel):
    rows: list[dict[str, Any]]
    columns: list[str]
    has_rows: bool