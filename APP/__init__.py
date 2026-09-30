"""APP — слой графического интерфейса (PyQt6) приложения Finance App.

Содержит окна (windows), виджеты (widgets) и объект сессии (Session),
который связывает GUI с пакетом API.
"""

from .session import Session, CAN_LOAD, CAN_ANALYTICS

__all__ = [
    "Session",
    "CAN_LOAD",
    "CAN_ANALYTICS",
]