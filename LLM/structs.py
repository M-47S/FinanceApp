from dataclasses import dataclass, field
from typing import Dict, Literal

Role = Literal["user", "assistant", "system"]

# --- счётчики id (процесс-глобальные) --------------------------------------
_req_next: int = 1
_resp_next: int = 1


def _next_request_id() -> int:
    global _req_next
    val = _req_next
    _req_next += 1
    return val


def _next_response_id() -> int:
    global _resp_next
    val = _resp_next
    _resp_next += 1
    return val


def sync_request_counter(value: int) -> None:
    """Подтянуть счётчик запросов так, чтобы он был > value."""
    global _req_next
    _req_next = max(_req_next, value)


def sync_response_counter(value: int) -> None:
    global _resp_next
    _resp_next = max(_resp_next, value)


@dataclass(slots=True, frozen=True)
class Message:
    role: Role
    content: str

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("'content' must not be empty")

    def dict_form(self) -> Dict:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class LLMRequest:
    prompt: Message
    session_id: int
    id: int = field(default_factory=_next_request_id)


@dataclass(slots=True)
class LLMResponse:
    answer: str
    session_id: int
    req_id: int
    id: int = field(default_factory=_next_response_id)