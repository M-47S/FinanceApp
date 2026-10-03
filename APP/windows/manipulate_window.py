"""Окно манипуляции данными: редактирование и удаление строк + SQL-Mode."""

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox,
    QLabel, QTextEdit, QSplitter, QGroupBox, QDialog,
    QFormLayout, QLineEdit, QDialogButtonBox, QSpinBox,
    QMessageBox,
)

from API import FinanceAPIError
from APP.ui_helpers import show_message, FORBIDDEN_ICON_PATH
from APP.widgets.result_table import ResultTable


class EditRowDialog(QDialog):
    """Диалог редактирования одной строки."""

    def __init__(self, parent, columns: list[str], values: dict[str, Any]):
        super().__init__(parent)
        self.setWindowTitle("Редактирование строки")
        self.setMinimumWidth(440)
        self.editors: dict[str, QLineEdit] = {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        for col in columns:
            edit = QLineEdit()
            val = values.get(col)
            edit.setText("" if val is None else str(val))
            self.editors[col] = edit
            form.addRow(f"{col}:", edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> dict[str, Any]:
        """Введённые значения. Пустые строки → None (NULL)."""
        result: dict[str, Any] = {}
        for col, edit in self.editors.items():
            text = edit.text().strip()
            result[col] = text if text else None
        return result


class ManipulateWindow(QWidget):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self.current_table: str = ""
        self.pk_columns: list[str] = []

        self.setWindowTitle("Манипуляция данными")
        self.resize(1200, 700)

        root = QVBoxLayout(self)

        # --- Переключатель режимов ---
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

        # --- Основной splitter ---
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter, 1)

        # Левая панель
        left = QGroupBox("Управление")
        left.setMaximumWidth(280)
        left_layout = QVBoxLayout(left)

        left_layout.addWidget(QLabel("Таблица:"))
        self.table_combo = QComboBox()
        self.table_combo.currentTextChanged.connect(self._on_table_changed)
        left_layout.addWidget(self.table_combo)

        left_layout.addWidget(QLabel("Лимит записей:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100_000)
        self.limit_spin.setValue(500)
        left_layout.addWidget(self.limit_spin)

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.setMinimumHeight(34)
        self.refresh_btn.setToolTip(
            "Перезагрузить список таблиц и данные"
        )
        self.refresh_btn.clicked.connect(self._refresh)
        left_layout.addWidget(self.refresh_btn)

        left_layout.addStretch()

        self.edit_btn = QPushButton("✏  Редактировать")
        self.edit_btn.setMinimumHeight(38)
        self.edit_btn.clicked.connect(self._edit_selected)
        left_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑  Удалить")
        self.delete_btn.setMinimumHeight(38)
        self.delete_btn.clicked.connect(self._delete_selected)
        left_layout.addWidget(self.delete_btn)

        splitter.addWidget(left)

        # Центр — таблица данных
        center = QWidget()
        center_layout = QVBoxLayout(center)
        self.data_label = QLabel("Данные: —")
        center_layout.addWidget(self.data_label)
        self.result_table = ResultTable()
        self.result_table.setSelectionBehavior(
            self.result_table.SelectionBehavior.SelectRows
        )
        self.result_table.setSelectionMode(
            self.result_table.SelectionMode.ExtendedSelection
        )
        center_layout.addWidget(self.result_table, 1)
        splitter.addWidget(center)

        # Правая панель — SQL
        self.sql_panel = QGroupBox("SQL-запрос")
        sql_layout = QVBoxLayout(self.sql_panel)
        self.sql_edit = QTextEdit()
        self.sql_edit.setPlaceholderText(
            "-- Пример:\n"
            "UPDATE report.reasons SET name = 'Food' WHERE id = 1;\n"
            "DELETE FROM report.transactions WHERE id = 5;\n"
            "SELECT * FROM report.reasons;"
        )
        self.sql_edit.setStyleSheet(
            "font-family: monospace; font-size: 13px;"
        )
        sql_layout.addWidget(self.sql_edit, 1)

        self.sql_run = QPushButton("Выполнить SQL")
        self.sql_run.setMinimumHeight(34)
        self.sql_run.clicked.connect(self._execute_sql)
        sql_layout.addWidget(self.sql_run)

        self.sql_panel.setVisible(False)
        splitter.addWidget(self.sql_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        self._reload_tables()

    # ---------------- Режимы ----------------

    def _set_mode(self, mode: str):
        is_sql = mode == "sql"
        self.btn_normal.setChecked(not is_sql)
        self.btn_sql.setChecked(is_sql)
        self.sql_panel.setVisible(is_sql)

    # ---------------- Таблицы и данные ----------------

    def _reload_tables(self, preserve: str | None = None):
        try:
            tables = self.session.api.get_tables()
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        self.table_combo.blockSignals(True)
        self.table_combo.clear()
        self.table_combo.addItems(tables)

        target = preserve if preserve and preserve in tables else (
            tables[0] if tables else ""
        )
        if target:
            self.table_combo.setCurrentText(target)
        self.table_combo.blockSignals(False)

        if target:
            self._on_table_changed(target)
    
    def _on_table_changed(self, table: str):
        if not table:
            return
        self.current_table = table
        try:
            self.pk_columns = self.session.api.get_primary_key_columns(table)
        except FinanceAPIError:
            self.pk_columns = []
        self._reload_data()

    def _reload_data(self):
        if not self.current_table:
            return
        limit = self.limit_spin.value()
        try:
            df = self.session.api.fetch_all(
                self.current_table, limit=limit,
            )
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        pk_display = ", ".join(self.pk_columns) if self.pk_columns else "—"
        self.data_label.setText(
            f"Данные: {self.current_table}  "
            f"(строк: {len(df)}, PK: {pk_display})"
        )
        self.result_table.load_dataframe(df)
    
    def _refresh(self):
        """Полное обновление: список таблиц + данные."""
        current_table = self.table_combo.currentText()
        self._reload_tables(preserve=current_table)
    # ---------------- Редактирование ----------------

    def _edit_selected(self):
        rows = self.result_table.get_selected_rows()
        if len(rows) != 1:
            show_message(
                self, "Ошибка",
                "Выберите ровно одну строку для редактирования.",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        if not self.pk_columns:
            show_message(
                self, "Ошибка",
                f"У таблицы '{self.current_table}' нет первичного ключа. "
                "Редактирование невозможно.",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        row_data = self.result_table.get_row_raw(rows[0])

        try:
            editable = self.session.api.get_editable_columns(
                self.current_table, is_admin=self.session.is_admin,
            )
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        if not editable:
            show_message(
                self, "Ошибка",
                "Нет столбцов, доступных для редактирования.",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        dialog = EditRowDialog(self, editable, row_data)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        updates = dialog.get_values()
        pk_values = {c: row_data.get(c) for c in self.pk_columns}

        try:
            n = self.session.api.update_row(
                self.current_table, pk_values, updates,
            )
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка обновления", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        show_message(self, "Готово", f"Обновлено строк: {n}")
        self._reload_data()

    # ---------------- Удаление ----------------

    def _delete_selected(self):
        rows = self.result_table.get_selected_rows()
        if not rows:
            show_message(
                self, "Ошибка",
                "Выберите хотя бы одну строку для удаления.",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        if not self.pk_columns:
            show_message(
                self, "Ошибка",
                f"У таблицы '{self.current_table}' нет первичного ключа. "
                "Удаление невозможно.",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        pk_list = []
        for r in rows:
            row_data = self.result_table.get_row_raw(r)
            pk_list.append({c: row_data.get(c) for c in self.pk_columns})

        reply = QMessageBox.question(
            self, "Подтверждение",
            f"Удалить {len(pk_list)} строк(и) из '{self.current_table}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        errors: list[str] = []
        for pk in pk_list:
            try:
                deleted += self.session.api.delete_row(self.current_table, pk)
            except FinanceAPIError as e:
                errors.append(f"{pk}: {e}")

        msg = f"Удалено строк: {deleted}"
        if errors:
            msg += f"\n\nОшибки ({len(errors)}):\n" + "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... и ещё {len(errors) - 5}"

        show_message(self, "Результат", msg)
        self._reload_data()

    # ---------------- SQL ----------------

    def _execute_sql(self):
        sql = self.sql_edit.toPlainText().strip()
        if not sql:
            show_message(
                self, "Ошибка", "Введите SQL",
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        try:
            df = self.session.api.execute_sql(sql)
        except FinanceAPIError as e:
            show_message(
                self, "Ошибка SQL", str(e),
                icon_path=FORBIDDEN_ICON_PATH,
            )
            return

        # Пустой DataFrame без колонок = DML/DDL без RETURNING
        if df.empty and len(df.columns) == 0:
            show_message(
                self, "Готово",
                "Запрос выполнен (нет строк для отображения).",
            )
            self._reload_data()
        else:
            self.result_table.load_dataframe(df)
            self.data_label.setText(f"Результат SQL  (строк: {len(df)})")