"""Окно загрузки данных из Excel в БД."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QFileDialog, QLabel,
)

from API import FinanceAPIError
from APP.ui_helpers import show_message, FORBIDDEN_ICON_PATH


class LoadDataWindow(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.file_path: str | None = None

        self.setWindowTitle("Загрузка данных")
        self.setFixedSize(520, 260)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.db_edit = QLineEdit(session.config.dbname)
        self.db_edit.setReadOnly(True)
        self.table_edit = QLineEdit()
        self.table_edit.setPlaceholderText("например: reasons")

        form.addRow("DB:", self.db_edit)
        form.addRow("TABLE:", self.table_edit)
        layout.addLayout(form)

        self.file_label = QLabel("Файл не выбран")
        self.file_label.setStyleSheet("color: gray;")
        layout.addWidget(self.file_label)

        self.choose_btn = QPushButton("Выбрать файл")
        self.choose_btn.clicked.connect(self._choose_file)
        layout.addWidget(self.choose_btn)

        self.load_btn = QPushButton("Загрузить")
        self.load_btn.clicked.connect(self._do_load)
        layout.addWidget(self.load_btn)

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите Excel-файл", "",
            "Excel files (*.xlsx *.xls);;All files (*.*)"
        )
        if path:
            self.file_path = path
            self.file_label.setText(Path(path).name)
            self.file_label.setStyleSheet("color: black;")

    def _do_load(self):
        table = self.table_edit.text().strip()
        if not table:
            show_message(
                self, "Ошибка",
                "Укажите название таблицы",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        if not self.file_path:
            show_message(
                self, "Ошибка",
                "Выберите файл",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        try:
            n = self.session.api.load_from_excel(
                table=table,
                file_path=self.file_path,
            )
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка загрузки",
                str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        show_message(self, "Готово", f"Загружено строк: {n}")