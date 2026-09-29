"""Окно аналитики: обычный режим + SQL-Mode, экспорт результата."""

from pathlib import Path

import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QSpinBox, QLabel, QTextEdit,
    QFileDialog, QSplitter, QGroupBox,
)

from API import FinanceAPIError
from APP.ui_helpers import show_message, FORBIDDEN_ICON_PATH
from APP.widgets.result_table import ResultTable


class AnalyticsWindow(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.last_df: pd.DataFrame | None = None

        self.setWindowTitle("Аналитика")
        self.resize(1200, 700)

        root = QVBoxLayout(self)

        # ---------- Верхняя панель: переключатели режимов ----------
        top = QHBoxLayout()
        self.btn_normal = QPushButton("Обычный режим")
        self.btn_sql = QPushButton("SQL-Mode")
        for b in (self.btn_normal, self.btn_sql):
            b.setCheckable(True)
            b.setMinimumHeight(34)
        self.btn_normal.setChecked(True)
        self.btn_normal.clicked.connect(lambda: self._set_mode("normal"))
        self.btn_sql.clicked.connect(lambda: self._set_mode("sql"))
        top.addWidget(self.btn_normal)
        top.addWidget(self.btn_sql)
        top.addStretch()
        root.addLayout(top)

        # ---------- Основная область ----------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # Левая панель — управление
        left = QGroupBox("Параметры")
        left.setMaximumWidth(300)
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("Таблица:"))
        self.table_combo = QComboBox()
        self.table_combo.currentTextChanged.connect(self._reload_columns)
        left_layout.addWidget(self.table_combo)

        left_layout.addWidget(QLabel("Столбцы:"))
        self.columns_list = QListWidget()
        self.columns_list.setSelectionMode(
            QListWidget.SelectionMode.MultiSelection
        )
        left_layout.addWidget(self.columns_list, 1)

        left_layout.addWidget(QLabel("Количество записей:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(0, 10_000_000)
        self.limit_spin.setValue(1000)
        left_layout.addWidget(self.limit_spin)

        self.execute_btn = QPushButton("Выполнить")
        self.execute_btn.setMinimumHeight(34)
        self.execute_btn.clicked.connect(self._execute)
        left_layout.addWidget(self.execute_btn)

        splitter.addWidget(left)

        # Центр — таблица результатов
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(QLabel("Результат:"))
        self.result_table = ResultTable()
        center_layout.addWidget(self.result_table, 1)
        splitter.addWidget(center)

        # Правая панель — SQL (скрыта по умолчанию)
        self.sql_panel = QGroupBox("SQL-запрос")
        sql_layout = QVBoxLayout(self.sql_panel)
        self.sql_edit = QTextEdit()
        self.sql_edit.setPlaceholderText(
            "SELECT id, amount, op_date\n"
            "FROM report.transactions\n"
            "ORDER BY op_date DESC\n"
            "LIMIT 100;"
        )
        self.sql_edit.setStyleSheet(
            "font-family: monospace; font-size: 13px;"
        )
        sql_layout.addWidget(self.sql_edit, 1)

        sql_run = QPushButton("Выполнить SQL")
        sql_run.setMinimumHeight(34)
        sql_run.clicked.connect(self._execute_sql)
        sql_layout.addWidget(sql_run)

        self.sql_panel.setVisible(False)
        splitter.addWidget(self.sql_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        # ---------- Нижняя панель: сохранение ----------
        bottom = QHBoxLayout()
        bottom.addStretch()
        self.save_btn = QPushButton("💾 Сохранить как...")
        self.save_btn.setMinimumHeight(34)
        self.save_btn.clicked.connect(self._save)
        bottom.addWidget(self.save_btn)
        root.addLayout(bottom)

        # Загрузить список таблиц
        self._reload_tables()

    # ---------------- Режимы ----------------

    def _set_mode(self, mode: str):
        is_sql = mode == "sql"
        self.btn_normal.setChecked(not is_sql)
        self.btn_sql.setChecked(is_sql)
        self.sql_panel.setVisible(is_sql)

    # ---------------- Данные ----------------

    def _reload_tables(self):
        self.table_combo.clear()
        try:
            tables = self.session.api.get_tables()
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка",
                str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return
        self.table_combo.addItems(tables)

    def _reload_columns(self, table: str):
        self.columns_list.clear()
        if not table:
            return
        try:
            cols = self.session.api.get_columns(table)
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка",
                str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return
        for c in cols:
            item = QListWidgetItem(c)
            item.setSelected(True)
            self.columns_list.addItem(item)

    # ---------------- Выполнение ----------------

    def _selected_columns(self) -> list[str]:
        return [i.text() for i in self.columns_list.selectedItems()]

    def _execute(self):
        table = self.table_combo.currentText()
        if not table:
            show_message(
                self, "Ошибка",
                "Выберите таблицу",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        cols = self._selected_columns() or None
        limit = self.limit_spin.value() or None

        try:
            df = self.session.api.unload_to_dataframe(
                table=table, columns=cols, limit=limit,
            )
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка",
                str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        self.last_df = df
        self.result_table.load_dataframe(df)

    def _execute_sql(self):
        sql = self.sql_edit.toPlainText().strip()
        if not sql:
            show_message(
                self, "Ошибка",
                "Введите SQL",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        try:
            df = self.session.api.execute_sql(sql)
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка SQL",
                str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        self.last_df = df
        self.result_table.load_dataframe(df)

    # ---------------- Сохранение ----------------

    def _save(self):
        if self.last_df is None or self.last_df.empty:
            show_message(
                self, "Ошибка",
                "Нет данных для сохранения",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить результат", "result.xlsx",
            "Excel (*.xlsx);;CSV (*.csv)"
        )
        if not path:
            return

        try:
            ext = Path(path).suffix.lower()
            if ext == ".csv":
                self.last_df.to_csv(path, index=False)
            else:
                self.last_df.to_excel(
                    path, index=False, engine="openpyxl",
                )
        except Exception as e:
            show_message(
                self, "Ошибка сохранения",
                str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        show_message(self, "Готово", f"Сохранено: {path}")