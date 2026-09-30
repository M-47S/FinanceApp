"""Окно интерактивного ввода строк в таблицу БД."""

import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QTableWidget, QHeaderView,
)

from API import FinanceAPIError
from APP.ui_helpers import show_message, FORBIDDEN_ICON_PATH


class ManualInputWindow(QWidget):
    def __init__(self, session, table: str):
        super().__init__()
        self.session = session
        self.table = table
        self.columns: list[str] = []

        self.setWindowTitle(f"Интерактивная запись — {table}")
        self.resize(900, 500)

        root = QVBoxLayout(self)

        # --- Верхняя панель ---
        top = QHBoxLayout()
        top.addWidget(QLabel(f"Таблица: <b>{table}</b>"))
        top.addStretch()

        top.addWidget(QLabel("Число записей:"))
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 1000)
        self.rows_spin.setValue(1)
        self.rows_spin.valueChanged.connect(self._resize_rows)
        top.addWidget(self.rows_spin)

        root.addLayout(top)

        # --- Таблица ввода ---
        self.table_widget = QTableWidget()
        self.table_widget.setAlternatingRowColors(True)
        root.addWidget(self.table_widget, 1)

        # --- Нижняя панель ---
        bottom = QHBoxLayout()
        bottom.addStretch()

        self.clear_btn = QPushButton("Очистить")
        self.clear_btn.clicked.connect(self._clear)
        bottom.addWidget(self.clear_btn)

        self.save_btn = QPushButton("Сохранить в БД")
        self.save_btn.setMinimumHeight(34)
        self.save_btn.clicked.connect(self._save)
        bottom.addWidget(self.save_btn)

        root.addLayout(bottom)

        # Загружаем колонки таблицы
        self._load_columns()

    # ---------- инициализация ----------

    def _load_columns(self):
        try:
            self.columns = self.session.api.get_writable_columns(self.table)
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        if not self.columns:
            show_message(
                self, "Ошибка",
                f"В таблице '{self.table}' нет столбцов, доступных для записи.",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        self.table_widget.setColumnCount(len(self.columns))
        self.table_widget.setHorizontalHeaderLabels(self.columns)
        self.table_widget.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._resize_rows(self.rows_spin.value())

    def _resize_rows(self, n: int):
        self.table_widget.setRowCount(n)

    # ---------- действия ----------

    def _clear(self):
        self.table_widget.clearContents()

    def _collect_dataframe(self) -> pd.DataFrame:
        """Собирает заполненные строки в DataFrame, пропуская пустые."""
        rows = []
        for i in range(self.table_widget.rowCount()):
            row = []
            is_empty = True
            for j in range(self.table_widget.columnCount()):
                item = self.table_widget.item(i, j)
                text = item.text().strip() if item else ""
                if text:
                    is_empty = False
                    row.append(text)
                else:
                    row.append(None)
            if not is_empty:
                rows.append(row)

        return pd.DataFrame(rows, columns=self.columns)

    def _save(self):
        df = self._collect_dataframe()
        if df.empty:
            show_message(
                self, "Ошибка", "Нет данных для сохранения",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        try:
            n = self.session.api.load_dataframe(self.table, df)
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка сохранения", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        show_message(self, "Готово", f"Добавлено строк: {n}")
        self._clear()
        self.rows_spin.setValue(1)