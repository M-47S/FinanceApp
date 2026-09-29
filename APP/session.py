from dataclasses import dataclass, field
from typing import Optional
from API import DBConfig, FinanceAPI

# Права
CAN_LOAD = "can_load"
CAN_ANALYTICS = "can_analytics"


@dataclass
class Session:
    user: Optional[str] = None
    config: Optional[DBConfig] = None
    api: Optional[FinanceAPI] = None
    permissions: set[str] = field(default_factory=set)

    def is_authenticated(self) -> bool:
        return self.api is not None

    def login(self, host: str, port: int, dbname: str,
              user: str, password: str, schema: str = "report") -> None:
        config = DBConfig(host=host, port=port, dbname=dbname,
                          user=user, password=password, schema=schema)
        api = FinanceAPI(config)

        if not api.ping():
            raise RuntimeError("Не удалось подключиться к БД")

        groups = api.get_current_user_groups()

        self.user = user
        self.config = config
        self.api = api
        self.permissions = self._resolve(groups)

    def logout(self) -> None:
        self.user = None
        self.config = None
        self.api = None
        self.permissions = set()

    def has(self, permission: str) -> bool:
        return permission in self.permissions

    @staticmethod
    def _resolve(groups: list[str]) -> set[str]:
        perms = {CAN_ANALYTICS}  # аналитика доступна всем авторизованным
        if "admin_group" in groups or "writer_group" in groups:
            perms.add(CAN_LOAD)
        return perms