"""Все HTTP-эндпоинты API."""

from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from API import FinanceAPI
from .auth import authenticate, sessions
from .deps import get_api, get_session
from .schemas import (
    ColumnsResponse, DeleteRowRequest, DeleteRowResponse,
    FkOptionsResponse, ForeignKeysResponse, InsertResponse,
    LoginRequest, LoginResponse, LogoutResponse, PingResponse,
    RowsResponse, SqlRequest, SqlResponse, TablesResponse,
    UpdateRowRequest, UpdateRowResponse,
)

router = APIRouter()


# ==================== AUTH ====================

@router.post("/auth/login", response_model=LoginResponse, tags=["auth"])
def login(payload: LoginRequest):
    try:
        session = authenticate(
            user=payload.user,
            password=payload.password,
            host=payload.host,
            port=payload.port,
            dbname=payload.dbname,
            schema=payload.db_schema,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
    return LoginResponse(
        token=session.token,
        user=session.user,
        groups=session.groups,
        is_admin=session.is_admin,
        dbname=session.config.dbname,
        db_schema=session.config.schema,
    )


@router.post("/auth/logout", response_model=LogoutResponse, tags=["auth"])
def logout(session=Depends(get_session)):
    sessions.remove(session.token)
    return LogoutResponse(ok=True)


@router.get("/auth/me", response_model=LoginResponse, tags=["auth"])
def me(session=Depends(get_session)):
    return LoginResponse(
        token=session.token,
        user=session.user,
        groups=session.groups,
        is_admin=session.is_admin,
        dbname=session.config.dbname,
        db_schema=session.config.schema,
    )
    
@router.get("/tables/{table}/editable", response_model=ColumnsResponse, tags=["metadata"])
def get_editable(
    table: str,
    session=Depends(get_session),
    api: FinanceAPI = Depends(get_api),
):
    return ColumnsResponse(
        columns=api.get_editable_columns(table, is_admin=session.is_admin)
    )


# ==================== CONNECTION ====================

@router.get("/ping", response_model=PingResponse, tags=["connection"])
def ping(api: FinanceAPI = Depends(get_api)):
    return PingResponse(ok=api.ping())


# ==================== METADATA ====================

@router.get("/tables", response_model=TablesResponse, tags=["metadata"])
def get_tables(api: FinanceAPI = Depends(get_api)):
    return TablesResponse(tables=api.get_tables())


@router.get("/tables/{table}/columns", response_model=ColumnsResponse, tags=["metadata"])
def get_columns(table: str, api: FinanceAPI = Depends(get_api)):
    return ColumnsResponse(columns=api.get_columns(table))


@router.get("/tables/{table}/writable", response_model=ColumnsResponse, tags=["metadata"])
def get_writable_columns(table: str, api: FinanceAPI = Depends(get_api)):
    return ColumnsResponse(columns=api.get_writable_columns(table))


@router.get("/tables/{table}/pk", response_model=ColumnsResponse, tags=["metadata"])
def get_pk(table: str, api: FinanceAPI = Depends(get_api)):
    return ColumnsResponse(columns=api.get_primary_key_columns(table))


@router.get("/tables/{table}/fks", response_model=ForeignKeysResponse, tags=["metadata"])
def get_fks(table: str, api: FinanceAPI = Depends(get_api)):
    return ForeignKeysResponse(fks=api.get_foreign_keys(table))


@router.get("/fk-options/{ref_table}", response_model=FkOptionsResponse, tags=["metadata"])
def get_fk_options(ref_table: str, api: FinanceAPI = Depends(get_api)):
    return FkOptionsResponse(options=api.get_fk_options(ref_table))


@router.get("/tables/{table}/nullable", response_model=ColumnsResponse, tags=["metadata"])
def get_nullable(table: str, api: FinanceAPI = Depends(get_api)):
    cols = api.get_nullable_columns(table)
    return ColumnsResponse(columns=sorted(cols))


# ==================== UNLOAD (SELECT) ====================

@router.get("/data/{table}", response_model=RowsResponse, tags=["data"])
def unload(
    table: str,
    columns: str | None = None,
    limit: int | None = None,
    api: FinanceAPI = Depends(get_api),
):
    cols = [c for c in columns.split(",")] if columns else None
    df = api.unload_to_dataframe(table, columns=cols, limit=limit)
    return _df_to_response(df)


@router.get("/data/{table}/excel", tags=["data"])
def unload_excel(
    table: str,
    columns: str | None = None,
    limit: int | None = None,
    api: FinanceAPI = Depends(get_api),
):
    cols = [c for c in columns.split(",")] if columns else None
    df = api.unload_to_dataframe(table, columns=cols, limit=limit)
    return _df_to_excel(df, filename=f"{table}.xlsx")


# ==================== LOAD (INSERT) ====================

@router.post("/data/{table}/load-excel", response_model=InsertResponse, tags=["data"])
async def load_excel(
    table: str,
    file: UploadFile = File(...),
    sheet_name: str = Form("0"),
    api: FinanceAPI = Depends(get_api),
):
    content = await file.read()
    try:
        df = pd.read_excel(BytesIO(content), sheet_name=sheet_name, engine="openpyxl")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot parse Excel: {e}")

    n = api.load_dataframe(table, df)
    return InsertResponse(inserted=n)


@router.post("/data/{table}/load-rows", response_model=InsertResponse, tags=["data"])
def load_rows(
    table: str,
    rows: list[dict[str, Any]],
    api: FinanceAPI = Depends(get_api),
):
    if not rows:
        return InsertResponse(inserted=0)
    df = pd.DataFrame(rows)
    n = api.load_dataframe(table, df)
    return InsertResponse(inserted=n)


# ==================== MANIPULATION ====================

@router.put("/data/{table}/row", response_model=UpdateRowResponse, tags=["manipulation"])
def update_row(
    table: str,
    payload: UpdateRowRequest,
    api: FinanceAPI = Depends(get_api),
):
    n = api.update_row(table, payload.pk_values, payload.updates)
    return UpdateRowResponse(updated=n)


@router.delete("/data/{table}/row", response_model=DeleteRowResponse, tags=["manipulation"])
def delete_row(
    table: str,
    payload: DeleteRowRequest,
    api: FinanceAPI = Depends(get_api),
):
    n = api.delete_row(table, payload.pk_values)
    return DeleteRowResponse(deleted=n)


# ==================== SQL ====================

@router.post("/sql", response_model=SqlResponse, tags=["sql"])
def execute_sql(payload: SqlRequest, api: FinanceAPI = Depends(get_api)):
    df = api.execute_sql(payload.sql, payload.params)
    has_rows = len(df.columns) > 0
    return SqlResponse(
        rows=df.to_dict(orient="records") if has_rows else [],
        columns=list(df.columns),
        has_rows=has_rows,
    )


@router.post("/sql/excel", tags=["sql"])
def execute_sql_excel(payload: SqlRequest, api: FinanceAPI = Depends(get_api)):
    df = api.execute_sql(payload.sql, payload.params)
    if df.empty and len(df.columns) == 0:
        raise HTTPException(status_code=400, detail="Запрос не вернул строк")
    return _df_to_excel(df, filename="query_result.xlsx")


# ==================== helpers ====================

def _df_to_response(df: pd.DataFrame) -> RowsResponse:
    records = df.to_dict(orient="records")
    return RowsResponse(rows=records, count=len(records))


def _df_to_excel(df: pd.DataFrame, filename: str) -> StreamingResponse:
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )