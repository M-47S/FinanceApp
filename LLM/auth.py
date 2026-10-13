from __future__ import annotations

import base64
import time
import uuid
from dataclasses import dataclass

import httpx2


@dataclass
class _CachedToken:
    value: str
    expires_at: float  # unix timestamp, сек


class GigaChatAuth:
    """
    Менеджер access-токена GigaChat.
    Сам получает токен по OAuth и обновляет его за минуту до истечения.
    """

    OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    def __init__(
        self,
        auth_key: str,
        scope: str = "GIGACHAT_API_PERS",
        *,
        verify_ssl: bool = False,
        timeout: float = 30.0,
    ) -> None:
        # Ключ авторизации из личного кабинета — это уже готовый base64(client_id:client_secret).
        # Если передали client_id:client_secret «в чистом виде» — закодируем сами.
        if ":" in auth_key and not _looks_like_base64(auth_key):
            auth_key = base64.b64encode(auth_key.encode()).decode()

        self._auth_key = auth_key
        self._scope = scope
        self._verify_ssl = verify_ssl
        self._timeout = timeout
        self._cached: _CachedToken | None = None

    def get_token(self) -> str:
        now = time.time()
        # Обновляем за 60 секунд до истечения — как рекомендует документация.
        if self._cached is None or self._cached.expires_at - 60 <= now:
            self._refresh()
        return self._cached.value  # type: ignore[union-attr]

    def _refresh(self) -> None:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Basic {self._auth_key}",
        }
        data = {"scope": self._scope}

        with httpx2.Client(verify=self._verify_ssl, timeout=self._timeout) as client:
            resp = client.post(self.OAUTH_URL, headers=headers, data=data)

        if resp.status_code != 200:
            raise RuntimeError(
                f"GigaChat OAuth failed: {resp.status_code} {resp.text}"
            )

        payload = resp.json()
        token = payload["access_token"]
        expires_at_ms = payload.get("expires_at")
        if expires_at_ms:
            expires_at = expires_at_ms / 1000.0
        else:
            expires_at = time.time() + 30 * 60  # fallback по документации

        self._cached = _CachedToken(value=token, expires_at=expires_at)


def _looks_like_base64(s: str) -> bool:
    # грубая проверка: base64 без ':' и состоит из допустимых символов
    if ":" in s:
        return False
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=")
    return all(c in allowed for c in s) and len(s) % 4 == 0