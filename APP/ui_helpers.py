"""Хелперы для UI: пути к ресурсам, message box'ы, обработка ошибок API."""

import inspect
from functools import wraps
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

from APP.exceptions import ConnectionLostError, FinanceAPIError


# --- Пути к ресурсам ---

IMAGES_DIR = Path(__file__).parent / "images"
APP_ICON_PATH = IMAGES_DIR / "app_icon.jpg"
FORBIDDEN_ICON_PATH = IMAGES_DIR / "forbidden.jpg"


# --- Иконка приложения ---

def set_app_icon(app: QApplication) -> None:
    """Ставит иконку приложения (таскбар, заголовок окна, Alt+Tab)."""
    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))


# --- Message box с кастомной иконкой ---

def _icon_pixmap(path: Path) -> QPixmap | None:
    if not path.exists():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaled(
        64,
        64,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def show_message(
    parent: QWidget | None,
    title: str,
    text: str,
    *,
    icon_path: Path | None = None,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
) -> None:
    """
    Показывает QMessageBox с кастомной иконкой (если передана).
    Если icon_path не указан — используется стандартная иконка Information.
    """
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(buttons)

    pixmap = _icon_pixmap(icon_path) if icon_path else None
    if pixmap is not None:
        box.setIconPixmap(pixmap)
    else:
        box.setIcon(QMessageBox.Icon.Information)

    if APP_ICON_PATH.exists():
        box.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    box.exec()


# --- Декоратор для безопасного вызова API ---

def safe_api_call():
    """
    Декоратор для методов окна. Ловит ошибки API и показывает сообщение,
    не давая приложению упасть или зависнуть.

    Автоматически отсекает лишние позиционные аргументы, которые Qt-сигналы
    (например, clicked(checked)) передают в слоты, не ожидающие их.
    """
    def decorator(method):
        sig = inspect.signature(method)
        # Сколько позиционных аргументов принимает метод (кроме self)
        positional = [
            p for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        # Если у метода есть *args — не обрезаем ничего
        has_varargs = any(
            p.kind == p.VAR_POSITIONAL for p in sig.parameters.values()
        )
        max_args = None if has_varargs else max(len(positional) - 1, 0)

        @wraps(method)
        def wrapper(self, *args, **kwargs):
            if max_args is not None:
                args = args[:max_args]
            try:
                return method(self, *args, **kwargs)
            except ConnectionLostError as e:
                show_message(
                    self,
                    "Соединение потеряно",
                    f"{e}\n\n"
                    "Проверьте, что сервер API и база данных запущены. "
                    "Попробуйте перезайти в приложение или нажать «Обновить».",
                    icon_path=FORBIDDEN_ICON_PATH,
                )
            except FinanceAPIError as e:
                show_message(
                    self, "Ошибка API",
                    str(e),
                    icon_path=FORBIDDEN_ICON_PATH,
                )
        return wrapper
    return decorator