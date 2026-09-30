from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
)
from PyQt6.QtCore import Qt

from APP.session import CAN_LOAD, CAN_MANIPULATE
from APP.ui_helpers import show_message, FORBIDDEN_ICON_PATH


class MainMenuWindow(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setWindowTitle(f"Finance App — {session.user}")
        self.setFixedSize(400, 380)

        layout = QVBoxLayout(self)

        title = QLabel(f"Пользователь: {session.user}")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; padding: 10px;")
        layout.addWidget(title)

        self.load_btn = QPushButton("📥  Загрузка данных")
        self.load_btn.setMinimumHeight(60)
        self.load_btn.clicked.connect(self._open_load)
        layout.addWidget(self.load_btn)

        self.manipulate_btn = QPushButton("✏️  Манипуляция данными")
        self.manipulate_btn.setMinimumHeight(60)
        self.manipulate_btn.clicked.connect(self._open_manipulate)
        layout.addWidget(self.manipulate_btn)

        self.analytics_btn = QPushButton("📊  Аналитика")
        self.analytics_btn.setMinimumHeight(60)
        self.analytics_btn.clicked.connect(self._open_analytics)
        layout.addWidget(self.analytics_btn)

        self.logout_btn = QPushButton("Выйти")
        self.logout_btn.clicked.connect(self._logout)
        layout.addWidget(self.logout_btn)

    def _open_load(self):
        if not self.session.has(CAN_LOAD):
            show_message(
                self, "Доступ запрещён",
                "У вашей учётной записи нет прав на загрузку данных.\n"
                "Обратитесь к администратору.",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return
        from APP.windows.load_data_window import LoadDataWindow
        self.load_window = LoadDataWindow(self.session)
        self.load_window.show()

    def _open_manipulate(self):
        if not self.session.has(CAN_MANIPULATE):
            show_message(
                self, "Доступ запрещён",
                "У вашей учётной записи нет прав на манипуляцию данными.\n"
                "Обратитесь к администратору.",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return
        from APP.windows.manipulate_window import ManipulateWindow
        self.manipulate_window = ManipulateWindow(self.session)
        self.manipulate_window.show()

    def _open_analytics(self):
        from APP.windows.analytics_window import AnalyticsWindow
        self.analytics_window = AnalyticsWindow(self.session)
        self.analytics_window.show()

    def _logout(self):
        self.session.logout()
        from APP.windows.login_window import LoginWindow
        self.login = LoginWindow(self.session)
        self.login.show()
        self.close()