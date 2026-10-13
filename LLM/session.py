from __future__ import annotations

from datetime import datetime as dt
from itertools import count
from pathlib import Path
from typing import List

from . import structs as _structs
from .api import LLMApi
from .logs import LLMLogs
from .structs import LLMRequest, LLMResponse, Message


DEFAULT_SYSTEM_PROMPT = (
    "Ты — полезный ассистент в приложении. У тебя есть ограничение на длину ответа: "
    "до 7000 токенов. Отвечай кратко и по существу. "
    "Если нужно больше, разбей ответ на части. "
    "Не повторяй вопрос пользователя и не проси лишних данных. "
    "Поскольку ты в приложении, отвечай в виде MARKDOWN — для красивого вывода."
)

# --- виды событий в .llg ---
EV_OPEN = "session_open"
EV_RESUME = "session_resume"
EV_CLOSE = "session_close"
EV_REQUEST = "request"
EV_RESPONSE = "response"


class LLMSession:
    _session_counter = count(1)

    def __init__(
        self,
        api: LLMApi,
        *,
        session_id: int | None = None,
        system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
        keep_history: bool = True,
        log_dir: str | Path | None = None,
        log_path: str | Path | None = None,
        resume: bool = False,
    ) -> None:
        self._id = session_id if session_id is not None else next(self._session_counter)
        self._api = api
        self._keep_history = keep_history
        self._history: List[Message] = []
        self._closed = False

        # --- путь к файлу сессии ----------------------------------------
        if log_path is not None:
            path = Path(log_path)
        else:
            base = f"LLM_Session_{self._id}.llg"
            path = (Path(log_dir) / base) if log_dir else Path(base)
        self._logger = LLMLogs(path)

        self._system: Message | None = (
            Message(role="system", content=system_prompt) if system_prompt else None
        )

        if resume:
            self._logger.event(EV_RESUME, session_id=self._id)
        else:
            self._logger.event(
                EV_OPEN,
                session_id=self._id,
                system_prompt=system_prompt,
                api={
                    "model": getattr(api, "model", None),
                    "base_url": getattr(api, "base_url", None),
                },
            )

    # --- свойства ---------------------------------------------------------
    @property
    def id(self) -> int:
        return self._id

    @property
    def history(self) -> List[Message]:
        return list(self._history)

    @property
    def log_path(self) -> Path:
        return self._logger.path
    
    @property
    def base_model(self) -> str:
        return self._api.model

    # --- логирование ------------------------------------------------------
    def save_info(self, info_line: str) -> None:
        if not info_line:
            raise ValueError("'info_line' must not be empty")
        self._logger.log(info_line)

    # --- основной сценарий ------------------------------------------------
    def ask(
        self,
        request: LLMRequest,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        if self._closed:
            raise RuntimeError("Session is closed")
        if not isinstance(request, LLMRequest):
            raise TypeError("'request' must be an instance of LLMRequest")

        if request.session_id != self._id:
            request.session_id = self._id

        self._logger.event(
            EV_REQUEST,
            id=request.id,
            role=request.prompt.role,
            content=request.prompt.content,
        )

        messages: List[Message] = []
        if self._system is not None:
            messages.append(self._system)
        messages.extend(self._history)
        messages.append(request.prompt)

        answer = self._api.ask(messages, temperature=temperature, max_tokens=max_tokens)

        response = LLMResponse(
            answer=answer,
            session_id=self._id,
            req_id=request.id,
        )
        self._logger.event(
            EV_RESPONSE,
            id=response.id,
            req_id=request.id,
            content=answer,
        )

        if self._keep_history:
            self._history.append(request.prompt)
            self._history.append(Message(role="assistant", content=answer))

        return response

    def reset(self) -> None:
        self._history.clear()
        self.save_info("History cleared")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._logger.event(EV_CLOSE, session_id=self._id)
        self._logger.close()

    # --- восстановление ---------------------------------------------------
    @classmethod
    def load(
        cls,
        path: str | Path,
        api: LLMApi,
        *,
        keep_history: bool = True,
    ) -> "LLMSession":
        """
        Восстановить сессию из .llg.

        api должен быть совместим с исходным (модель, base_url, токен).
        Токен в файл не сохраняется по понятным причинам.
        """
        records = LLMLogs.read(path)
        if not records:
            raise ValueError(f"Empty or missing session log: {path}")

        open_rec = next((r for r in records if r.get("kind") == EV_OPEN), None)
        if open_rec is None:
            raise ValueError(
                f"No '{EV_OPEN}' record in {path}; файл не является сессией LLMSession "
                f"или записан в старом текстовом формате."
            )

        session_id = int(open_rec["session_id"])
        system_prompt = open_rec.get("system_prompt")

        # Создаём объект в режиме resume: файл не перезаписывается, пишем только resume-маркер.
        obj = cls(
            api,
            session_id=session_id,
            system_prompt=system_prompt,
            keep_history=keep_history,
            log_path=path,
            resume=True,
        )

        # --- восстановление истории -------------------------------------
        pending: dict[int, str] = {}
        max_req_id = 0
        max_resp_id = 0

        for r in records:
            kind = r.get("kind")
            if kind == EV_REQUEST:
                rid = int(r.get("id", 0))
                pending[rid] = r.get("content", "")
                max_req_id = max(max_req_id, rid)
            elif kind == EV_RESPONSE:
                rid = int(r.get("id", 0))
                req_id = int(r.get("req_id", 0))
                user_text = pending.pop(req_id, None)
                if user_text is None:
                    # ответ без соответствующего запроса — пропускаем
                    continue
                obj._history.append(Message(role="user", content=user_text))
                if r.get("content"):
                    obj._history.append(
                        Message(role="assistant", content=r["content"])
                    )
                max_resp_id = max(max_resp_id, rid)

        # --- подтягиваем глобальные счётчики, чтобы id не пересекались ----
        _structs.sync_request_counter(max_req_id + 1)
        _structs.sync_response_counter(max_resp_id + 1)

        return obj

    # --- контекстный менеджер --------------------------------------------
    def __enter__(self) -> "LLMSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()