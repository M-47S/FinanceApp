import sys
import ctypes

from PyQt6.QtWidgets import QApplication
from APP.session import Session
from APP.ui_helpers import set_app_icon
from APP.windows.login_window import LoginWindow


def main():
    # AppUserModelID нужен только на Windows (для корректной иконки в таскбаре).
    # На Linux/macOS этого API не существует.
    if sys.platform == "win32":
        myappid = "M-47S.FinanceApp.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)
    set_app_icon(app)

    session = Session()
    login = LoginWindow(session)
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()