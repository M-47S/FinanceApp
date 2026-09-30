"""Окна приложения."""

from .login_window import LoginWindow
from .main_menu_window import MainMenuWindow
from .load_data_window import LoadDataWindow
from .analytics_window import AnalyticsWindow
from .manual_input_window import ManualInputWindow
from .manipulate_window import ManipulateWindow

__all__ = [
    "LoginWindow",
    "MainMenuWindow",
    "LoadDataWindow",
    "AnalyticsWindow",
    "ManualInputWindow",
    "ManipulateWindow",
]