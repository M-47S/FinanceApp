"""Простая in-memory авторизация: сессии на основе токена.

При логине проверяем credentials через реальное подключение к БД,
а затем храним их в памяти до logout / истечения TTL.
"""

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock

from API import DBConfig, FinanceAPI, FinanceAPIError


SESSION_TTL = timedelta(hours=8)


@dataclass
class UserSession:
    token: str
    user: str
    password: str
    config: DBConfig
    groups: list[str] = field(default_factory=list)
    is_admin: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)

    def is_expired(self) -> bool:
        return datetime.now() - self.last_seen > SESSION_TTL

    def touch(self) -> None:
        self.last_seen = datetime.now()

    def build_api(self) -> FinanceAPI:
        """Создаёт свежий FinanceAPI с credentials этой сессии."""
        return FinanceAPI(self.config)


class SessionStore:
    """Потокобезопасное хранилище сессий."""

    def __init__(self) -> None:
        self._sessions: dict[str, UserSession] = {}
        self._lock = Lock()

    def create(
        self,
        config: DBConfig,
        groups: list[str],
        is_admin: bool,
    ) -> UserSession:
        token = secrets.token_urlsafe(32)
        session = UserSession(
            token=token,
            user=config.user,
            password=config.password,
            config=config,
            groups=groups,
            is_admin=is_admin,
        )
        with self._lock:
            self._sessions[token] = session
        return session

    def get(self, token: str) -> UserSession | None:
        with self._lock:
            session = self._sessions.get(token)
        if session is None:
            return None
        if session.is_expired():
            self.remove(token)
            return None
        session.touch()
        return session

    def remove(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(token, None)

    def purge_expired(self) -> int:
        with self._lock:
            dead = [t for t, s in self._sessions.items() if s.is_expired()]
            for t in dead:
                self._sessions.pop(t, None)
        return len(dead)


# Глобальный singleton
sessions = SessionStore()


def authenticate(
    host: str, port: int, dbname: str,
    user: str, password: str, schema: str,
) -> UserSession:
    """
    Проверяет credentials через реальное подключение к БД.
    Возвращает созданную сессию.
    """
    config = DBConfig(
        host=host, port=port, dbname=dbname,
        user=user, password=password, schema=schema,
    )
    api = FinanceAPI(config)

    try:
        if not api.ping():
            raise RuntimeError("Не удалось подключиться к БД")
        groups = api.get_current_user_groups()
    except FinanceAPIError as e:
        raise

    is_admin = "admin_group" in groups
    return sessions.create(config, groups, is_admin)