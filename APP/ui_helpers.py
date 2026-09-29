"""Хелперы для UI: пути к ресурсам и кастомные message box'ы."""

from pathlib import Path

from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget

# --- Пути к ресурсам ---

IMAGES_DIR = Path(__file__).parent / "images"
APP_ICON_PATH = IMAGES_DIR / "app_icon.jpg"
FORBIDDEN_ICON_PATH = IMAGES_DIR / "forbidden.jpg"


# --- Иконка приложения ---

def set_app_icon(app: QApplication) -> None:
    """Ставит иконку приложения (видна в таскбаре, заголовке окна, Alt+Tab)."""
    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))


# --- Message box с кастомной иконкой ---

def _icon_pixmap(path: Path) -> QPixmap | None:
    if not path.exists():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    # Приводим к разумному размеру, чтобы не растягивало layout
    return pixmap.scaled(
        64, 64,
        aspectRatioMode=1,      # KeepAspectRatio
        transformMode=1,        # SmoothTransformation
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

    # Иконка самого окна сообщения (в заголовке) — та же, что у приложения
    if APP_ICON_PATH.exists():
        box.setWindowIcon(QIcon(str(APP_ICON_PATH)))

    box.exec()