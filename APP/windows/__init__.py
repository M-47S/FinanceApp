"""Окна приложения: авторизация, главное меню, загрузка данных, аналитика."""

from .login_window import LoginWindow
from .main_menu_window import MainMenuWindow
from .load_data_window import LoadDataWindow
from .analytics_window import AnalyticsWindow
from .manual_input_window import ManualInputWindow

__all__ = [
    "LoginWindow",
    "MainMenuWindow",
    "LoadDataWindow",
    "AnalyticsWindow",
    "ManualInputWindow",
]