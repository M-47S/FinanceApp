from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QMessageBox, QLabel, QSpinBox,
)
from PyQt6.QtCore import Qt
from APP.ui_helpers import show_message, FORBIDDEN_ICON_PATH


class LoginWindow(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setWindowTitle("Finance App — Вход")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)

        title = QLabel("Авторизация")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        form = QFormLayout()

        self.host_edit = QLineEdit("localhost")
        self.port_edit = QSpinBox()
        self.port_edit.setRange(1, 65535)
        self.port_edit.setValue(5432)
        self.db_edit = QLineEdit("FinDB")
        self.user_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Host:", self.host_edit)
        form.addRow("Port:", self.port_edit)
        form.addRow("Database:", self.db_edit)
        form.addRow("User:", self.user_edit)
        form.addRow("Password:", self.password_edit)

        layout.addLayout(form)

        self.login_btn = QPushButton("Войти")
        self.login_btn.clicked.connect(self._on_login)
        layout.addWidget(self.login_btn)

        self.password_edit.returnPressed.connect(self._on_login)

    def _on_login(self):
        try:
            self.session.login(...)
        except Exception as e:
            show_message(
                self,
                "Ошибка входа",
                str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return