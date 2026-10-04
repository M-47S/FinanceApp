"""Сессия пользователя: авторизация через удалённый API, права, состояние."""

from dataclasses import dataclass, field
from typing import Optional

import requests

from APP.remote_api import RemoteFinanceAPI


CAN_LOAD = "can_load"
CAN_ANALYTICS = "can_analytics"
CAN_MANIPULATE = "can_manipulate"


@dataclass
class Session:
    api_url: str = ""
    user: Optional[str] = None
    token: Optional[str] = None
    api: Optional[RemoteFinanceAPI] = None
    permissions: set[str] = field(default_factory=set)
    groups: list[str] = field(default_factory=list)
    is_admin: bool = False
    dbname: str = ""
    schema: str = "report"

    def is_authenticated(self) -> bool:
        return self.api is not None and self.token is not None

    def login(
        self,
        api_url: str,
        user: str,
        password: str,
        schema: str | None = None,
    ) -> None:
        api_url = api_url.rstrip("/")
        payload: dict = {"user": user, "password": password}
        if schema:
            payload["db_schema"] = schema

        try:
            r = requests.post(
                f"{api_url}/auth/login", json=payload, timeout=15,
            )
        except requests.RequestException as e:
            raise RuntimeError(f"Не удалось связаться с API: {e}")

        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except Exception:
                detail = r.text
            raise RuntimeError(f"Ошибка входа: {detail}")

        data = r.json()
        self.api_url = api_url
        self.user = data["user"]
        self.token = data["token"]
        self.groups = data.get("groups", [])
        self.is_admin = data.get("is_admin", False)
        self.dbname = data.get("dbname", "")
        self.schema = data.get("db_schema", "report")
        self.permissions = self._resolve(self.groups)
        self.api = RemoteFinanceAPI(api_url, self.token)

    def logout(self) -> None:
        if self.api_url and self.token:
            try:
                requests.post(
                    f"{self.api_url}/auth/logout",
                    headers={"Authorization": f"Bearer {self.token}"},
                    timeout=5,
                )
            except requests.RequestException:
                pass
        self.api_url = ""
        self.user = None
        self.token = None
        self.api = None
        self.permissions = set()
        self.groups = []
        self.is_admin = False
        self.dbname = ""
        self.schema = "report"

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    @staticmethod
    def _resolve(groups: list[str]) -> set[str]:
        perms = {CAN_ANALYTICS}
        if "admin_group" in groups or "writer_group" in groups:
            perms.add(CAN_LOAD)
            perms.add(CAN_MANIPULATE)
        return perms