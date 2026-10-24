import sys
import ctypes

from PyQt6.QtWidgets import QApplication
from APP.session import Session
from APP.ui_helpers import set_app_icon
from APP.windows.login_window import LoginWindow
from API.logging_config import setup_logging


def main():
    setup_logging()          # <-- добавить первой строк
    # 1. Уникальный ID для приложения — ДО создания QApplication
    myappid = "M-47S.FinanceApp.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # 2. Создаём приложение
    app = QApplication(sys.argv)

    # 3. Ставим иконку
    set_app_icon(app)

    session = Session()
    login = LoginWindow(session)
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()