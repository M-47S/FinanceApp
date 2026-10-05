"""Точка входа FastAPI-приложения."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from API import (
    DBConnectionError,
    DBQueryError,
    FinanceAPIError,
    TableNotFoundError,
    ColumnNotFoundError,
    ValidationError,
)
from .routers import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Finance App API",
        version="0.1.0",
        description="HTTP-обёртка над FinanceAPI для GUI Finance App.",
    )

    # CORS — на случай, если позже появится web-клиент.
    # Для desktop-клиента не нужен, но не мешает.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],       # ⚠ в проде сузить до конкретных источников
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Отображение исключений FinanceAPI → HTTP-статусы ---
    @app.exception_handler(TableNotFoundError)
    async def _table_not_found(request: Request, exc: TableNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ColumnNotFoundError)
    async def _column_not_found(request: Request, exc: ColumnNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def _validation(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(DBConnectionError)
    async def _db_conn(request: Request, exc: DBConnectionError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(DBQueryError)
    async def _db_query(request: Request, exc: DBQueryError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(FinanceAPIError)
    async def _generic(request: Request, exc: FinanceAPIError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    app.include_router(router)
    return app


app = create_app()