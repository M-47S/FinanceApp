"""FastAPI-зависимости: извлечение сессии и построение FinanceAPI."""

from fastapi import Depends, Header, HTTPException, status

from API import FinanceAPI
from .auth import UserSession, sessions


def get_session(
    authorization: str | None = Header(default=None),
) -> UserSession:
    """
    Достаёт сессию из заголовка `Authorization: Bearer <token>`.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    session = sessions.get(token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session


def get_api(session: UserSession = Depends(get_session)) -> FinanceAPI:
    """Создаёт FinanceAPI с credentials текущей сессии."""
    return session.build_api()


def require_admin(session: UserSession = Depends(get_session)) -> UserSession:
    if not session.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора",
        )
    return session