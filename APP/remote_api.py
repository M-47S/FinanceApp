"""HTTP-клиент к Finance API.

Дублирует публичный интерфейс FinanceAPI, но все операции
выполняются через HTTP-запросы к удалённому серверу.
"""

from pathlib import Path
from typing import Any, Sequence

import pandas as pd
import requests

from APP.exceptions import (
    ConnectionLostError,
    DBError,
    FinanceAPIError,
    TableNotFoundError,
    ValidationError,
)


class RemoteFinanceAPI:
    def __init__(self, base_url: str, token: str, timeout: float = 15.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        # timeout = (connect, read): быстро отваливаемся, если сервер недоступен
        self.timeout = (5.0, timeout)

    # ---------- internal ----------

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        """
        Универсальная обёртка над requests: ловит сетевые ошибки
        и превращает их в ConnectionLostError.
        """
        url = f"{self.base_url}{path}"
        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault("Authorization", f"Bearer {self.token}")

        try:
            return requests.request(
                method, url, headers=headers, timeout=self.timeout, **kwargs,
            )
        except requests.ConnectionError as e:
            raise ConnectionLostError(
                f"Нет связи с API ({self.base_url}). "
                "Проверьте, запущен ли сервер и доступна ли сеть."
            ) from e
        except requests.Timeout as e:
            raise ConnectionLostError(
                f"Сервер API не отвечает ({self.base_url}). "
                "Возможно, он перегружен или недоступен."
            ) from e
        except requests.RequestException as e:
            raise ConnectionLostError(f"Ошибка сети: {e}") from e
    # ---------- internal ----------

    def _headers(self, json: bool = False) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self.token}"}
        if json:
            h["Content-Type"] = "application/json"
        return h

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _check(self, response: requests.Response) -> None:
        if response.status_code < 400:
            return
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text

        code = response.status_code
        if code == 404:
            raise TableNotFoundError(detail)
        if code == 400:
            raise ValidationError(detail)
        if code == 401:
            raise DBError(f"Сессия истекла или недействительна: {detail}")
        if code == 403:
            raise FinanceAPIError(f"Доступ запрещён: {detail}")
        if code in (502, 503, 504):
            # API жив, но не может достучаться до БД (или прокси не отвечает)
            raise ConnectionLostError(
                f"API не может подключиться к БД: {detail}"
            )
        raise FinanceAPIError(f"[{code}] {detail}")

    # ---------- metadata ----------

    def get_tables(self) -> list[str]:
        r = self._request("GET", "/tables", headers=self._headers())
        self._check(r)
        return r.json()["tables"]

    def get_columns(self, table: str) -> list[str]:
        r = requests.get(self._url(f"/tables/{table}/columns"), headers=self._headers(), timeout=self.timeout)
        self._check(r)
        return r.json()["columns"]

    def get_writable_columns(self, table: str) -> list[str]:
        r = requests.get(self._url(f"/tables/{table}/writable"), headers=self._headers(), timeout=self.timeout)
        self._check(r)
        return r.json()["columns"]

    def get_primary_key_columns(self, table: str) -> list[str]:
        r = requests.get(self._url(f"/tables/{table}/pk"), headers=self._headers(), timeout=self.timeout)
        self._check(r)
        return r.json()["columns"]

    def get_foreign_keys(self, table: str) -> dict[str, dict]:
        r = requests.get(self._url(f"/tables/{table}/fks"), headers=self._headers(), timeout=self.timeout)
        self._check(r)
        return r.json()["fks"]

    def get_fk_options(self, ref_table: str) -> list[tuple]:
        r = requests.get(self._url(f"/fk-options/{ref_table}"), headers=self._headers(), timeout=self.timeout)
        self._check(r)
        return [tuple(x) for x in r.json()["options"]]

    def get_nullable_columns(self, table: str) -> set[str]:
        r = requests.get(self._url(f"/tables/{table}/nullable"), headers=self._headers(), timeout=self.timeout)
        self._check(r)
        return set(r.json()["columns"])

    def get_editable_columns(self, table: str, is_admin: bool = False) -> list[str]:
        # is_admin определяется на сервере по текущей сессии
        r = requests.get(self._url(f"/tables/{table}/editable"), headers=self._headers(), timeout=self.timeout)
        self._check(r)
        return r.json()["columns"]

    # ---------- data ----------

    def unload_to_dataframe(self, table, columns=None, limit=None) -> pd.DataFrame:
        params: dict = {}
        if columns:
            params["columns"] = ",".join(columns)
        if limit is not None:
            params["limit"] = limit
        r = self._request("GET", f"/data/{table}", headers=self._headers(), params=params)
        self._check(r)
        return pd.DataFrame(r.json()["rows"])

    def fetch_all(self, table: str, limit: int = 500) -> pd.DataFrame:
        pk_cols = self.get_primary_key_columns(table)
        all_cols = self.get_columns(table)
        ordered = pk_cols + [c for c in all_cols if c not in pk_cols]
        return self.unload_to_dataframe(table, columns=ordered, limit=limit)

    def load_from_excel(
        self,
        table: str,
        file_path: str | Path,
        sheet_name: str | int = 0,
    ) -> int:
        path = Path(file_path)
        with path.open("rb") as f:
            files = {"file": (path.name, f)}
            data = {"sheet_name": str(sheet_name)}
            r = requests.post(
                self._url(f"/data/{table}/load-excel"),
                headers=self._headers(),
                files=files,
                data=data,
                timeout=self.timeout,
            )
        self._check(r)
        return r.json()["inserted"]

    def load_dataframe(self, table: str, df: pd.DataFrame) -> int:
        rows = df.to_dict(orient="records")
        r = requests.post(
            self._url(f"/data/{table}/load-rows"),
            headers=self._headers(json=True),
            json=rows,
            timeout=self.timeout,
        )
        self._check(r)
        return r.json()["inserted"]

    def update_row(self, table: str, pk_values: dict, updates: dict) -> int:
        payload = {"table": table, "pk_values": pk_values, "updates": updates}
        r = requests.put(
            self._url(f"/data/{table}/row"),
            headers=self._headers(json=True),
            json=payload,
            timeout=self.timeout,
        )
        self._check(r)
        return r.json()["updated"]

    def delete_row(self, table: str, pk_values: dict) -> int:
        payload = {"table": table, "pk_values": pk_values}
        r = requests.request(
            "DELETE",
            self._url(f"/data/{table}/row"),
            headers=self._headers(json=True),
            json=payload,
            timeout=self.timeout,
        )
        self._check(r)
        return r.json()["deleted"]

    # ---------- SQL ----------

    def execute_sql(self, sql: str, params=None) -> pd.DataFrame:
        payload = {"sql": sql, "params": list(params) if params else None}
        r = self._request(
            "POST", "/sql",
            headers=self._headers(json=True),
            json=payload,
        )
        self._check(r)
        data = r.json()
        if not data.get("has_rows"):
            return pd.DataFrame()
        return pd.DataFrame(data["rows"])