# LLM/api.py
from __future__ import annotations

import os
from pathlib import Path

import httpx2
from dotenv import load_dotenv
from openai import OpenAI

from .auth import GigaChatAuth
from .structs import Message

ENV_PATH = Path(__file__).resolve().parent / ".env"   # ← рядом с api.py
load_dotenv(ENV_PATH, override=True)

DEFAULT_BASE_URL = os.getenv("GIGACHAT_BASE_URL", "https://api.giga.chat/v1")
DEFAULT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-2")
DEFAULT_TIMEOUT = float(os.getenv("GIGACHAT_TIMEOUT", "60"))
DEFAULT_VERIFY = os.getenv("GIGACHAT_VERIFY_SSL", "false").lower() in {"1", "true", "yes"}
DEFAULT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")


class LLMApiError(RuntimeError):
    """Ошибка обращения к LLM-бэкенду."""


class LLMApi:
    def __init__(
        self,
        access_token: str | None = None,
        *,
        auth_key: str | None = None,
        scope: str = DEFAULT_SCOPE,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        verify_ssl: bool = DEFAULT_VERIFY,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._auth: GigaChatAuth | None = None

        token = access_token or os.getenv("access_token") or os.getenv("GIGACHAT_ACCESS_TOKEN")

        if token:
            # Старый режим: статичный токен (умрёт через 30 минут).
            self._client = OpenAI(
                base_url=base_url,
                api_key=token,
                http_client=_AuthInjectingClient(self._auth, verify=verify_ssl, timeout=timeout),
            )
        else:
            # Новый режим: автополучение и автообновление токена.
            key = auth_key or os.getenv("GIGACHAT_AUTH_KEY")
            if not key:
                raise ValueError(
                    "Не задан ни access_token, ни GIGACHAT_AUTH_KEY. "
                    "Для автоматического обновления токена укажите ключ авторизации."
                )
            self._auth = GigaChatAuth(key, scope=scope, verify_ssl=verify_ssl, timeout=timeout)
            # Создаём клиент с пустым ключом — заголовок подставит кастомный httpx.Client.
            self._client = OpenAI(
                base_url=base_url,
                api_key="placeholder",  # реальный токен подставится в auth-хуке
                http_client=_AuthInjectingClient(self._auth, verify=verify_ssl, timeout=timeout),
            )

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    def ask(self, messages, *, temperature=None, max_tokens=None) -> str:
        payload = [m.dict_form() for m in messages]
        extra = {}
        if temperature is not None:
            extra["temperature"] = temperature
        if max_tokens is not None:
            extra["max_tokens"] = max_tokens

        try:
            response = self._client.chat.completions.create(
                model=self._model, messages=payload, **extra,
            )
        except Exception as exc:
            raise LLMApiError(f"LLM request failed: {exc}") from exc

        if not response.choices:
            raise LLMApiError("LLM returned no choices")
        return response.choices[0].message.content or ""

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class _AuthInjectingClient(httpx2.Client):
    """httpx.Client, который перед каждым запросом подставляет свежий Bearer-токен."""

    def __init__(self, giga_auth: GigaChatAuth, **kwargs):
        super().__init__(**kwargs)
        self._giga_auth = giga_auth          # ← другое имя, не конфликтует с httpx

    def send(self, request, **kwargs):
        request.headers["Authorization"] = f"Bearer {self._giga_auth.get_token()}"
        return super().send(request, **kwargs)