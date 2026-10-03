from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QLineEdit,
    QPushButton, QLabel, QSpinBox,
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

        # --- Password + кнопка «показать/скрыть» в одной строке ---
        pwd_row = QHBoxLayout()
        pwd_row.setContentsMargins(0, 0, 0, 0)
        pwd_row.setSpacing(4)

        pwd_row.addWidget(self.password_edit, 1)

        self.toggle_pwd_btn = QPushButton("👁")
        self.toggle_pwd_btn.setCheckable(True)
        self.toggle_pwd_btn.setFixedWidth(36)
        self.toggle_pwd_btn.setToolTip("Показать / скрыть пароль")
        self.toggle_pwd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_pwd_btn.clicked.connect(self._toggle_password)
        pwd_row.addWidget(self.toggle_pwd_btn)

        form.addRow("Host:", self.host_edit)
        form.addRow("Port:", self.port_edit)
        form.addRow("Database:", self.db_edit)
        form.addRow("User:", self.user_edit)
        form.addRow("Password:", pwd_row)

        layout.addLayout(form)

        self.login_btn = QPushButton("Войти")
        self.login_btn.clicked.connect(self._on_login)
        layout.addWidget(self.login_btn)

        self.password_edit.returnPressed.connect(self._on_login)

    def _on_login(self):
        try:
            self.session.login(
                host=self.host_edit.text().strip(),
                port=self.port_edit.value(),
                dbname=self.db_edit.text().strip(),
                user=self.user_edit.text().strip(),
                password=self.password_edit.text(),
            )
        except Exception as e:
            show_message(
                self,
                "Ошибка входа",
                str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        from APP.windows.main_menu_window import MainMenuWindow
        self.menu = MainMenuWindow(self.session)
        self.menu.show()
        self.close()
        
    def _toggle_password(self):
        if self.toggle_pwd_btn.isChecked():
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_pwd_btn.setText("🙈")
        else:
            self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_pwd_btn.setText("👁")