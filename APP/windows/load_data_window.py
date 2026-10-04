"""Окно загрузки данных: из Excel или через интерактивный ввод."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QFileDialog, QLabel, QComboBox,
)

from API import FinanceAPIError
from APP.ui_helpers import show_message, FORBIDDEN_ICON_PATH


class LoadDataWindow(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.file_path: str | None = None

        self.setWindowTitle("Загрузка данных")
        self.setFixedSize(560, 300)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.db_edit = QLineEdit(session.dbname)
        self.db_edit.setReadOnly(True)

        self.table_combo = QComboBox()

        form.addRow("DB:", self.db_edit)
        form.addRow("TABLE:", self.table_combo)
        layout.addLayout(form)

        self.file_label = QLabel("Файл не выбран")
        self.file_label.setStyleSheet("color: gray;")
        layout.addWidget(self.file_label)

        # --- Кнопки ---
        btn_row = QHBoxLayout()

        self.choose_btn = QPushButton("Выбрать файл")
        self.choose_btn.setMinimumHeight(40)
        self.choose_btn.clicked.connect(self._choose_file)
        btn_row.addWidget(self.choose_btn)

        self.manual_btn = QPushButton("Интерактивная запись")
        self.manual_btn.setMinimumHeight(40)
        self.manual_btn.clicked.connect(self._open_manual_input)
        btn_row.addWidget(self.manual_btn)

        layout.addLayout(btn_row)

        self.load_btn = QPushButton("Загрузить из файла")
        self.load_btn.setMinimumHeight(40)
        self.load_btn.clicked.connect(self._do_load)
        layout.addWidget(self.load_btn)

        self._reload_tables()

    # ---------- таблицы ----------

    def _reload_tables(self):
        self.table_combo.clear()
        try:
            tables = self.session.api.get_tables()
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return
        self.table_combo.addItems(tables)

    # ---------- файл ----------

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
        table = self.table_combo.currentText()
        if not table:
            show_message(
                self, "Ошибка", "Выберите таблицу",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return
        if not self.file_path:
            show_message(
                self, "Ошибка", "Выберите файл",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        try:
            n = self.session.api.load_from_excel(
                table=table, file_path=self.file_path,
            )
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка загрузки", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        show_message(self, "Готово", f"Загружено строк: {n}")

    # ---------- ручной ввод ----------

    def _open_manual_input(self):
        table = self.table_combo.currentText()
        if not table:
            show_message(
                self, "Ошибка", "Выберите таблицу",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        from APP.windows.manual_input_window import ManualInputWindow
        self.manual_window = ManualInputWindow(self.session, table)
        self.manual_window.show()