"""Виджет таблицы результатов с числовой сортировкой и доступом к raw-значениям."""

from typing import Any

import pandas as pd
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem


class _DataItem(QTableWidgetItem):
    """Ячейка, которая помнит исходное значение и сортируется как число."""

    def __init__(self, value: Any):
        display = "" if value is None else str(value)
        super().__init__(display)
        self._raw = value

    def raw(self) -> Any:
        return self._raw

    def __lt__(self, other):
        a = self._raw
        b = getattr(other, "_raw", None)
        try:
            return float(a) < float(b)
        except (TypeError, ValueError):
            return str(a) < str(b)


class ResultTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def load_dataframe(self, df: pd.DataFrame) -> None:
        self.setSortingEnabled(False)
        self.clear()
        self.setRowCount(len(df))
        self.setColumnCount(len(df.columns))
        self.setHorizontalHeaderLabels([str(c) for c in df.columns])

        for i, (_, row) in enumerate(df.iterrows()):
            for j, val in enumerate(row):
                self.setItem(i, j, _DataItem(val))

        self.resizeColumnsToContents()
        self.setSortingEnabled(True)

    def get_row_raw(self, row: int) -> dict[str, Any]:
        """Словарь {имя_колонки: исходное_значение} для строки."""
        result: dict[str, Any] = {}
        for j in range(self.columnCount()):
            header_item = self.horizontalHeaderItem(j)
            if header_item is None:
                continue
            header = header_item.text()
            item = self.item(row, j)
            if isinstance(item, _DataItem):
                result[header] = item.raw()
            elif item is None:
                result[header] = None
            else:
                text = item.text()
                result[header] = text if text else None
        return result

    def get_selected_rows(self) -> list[int]:
        """Индексы выделенных строк (в визуальном порядке)."""
        return sorted({idx.row() for idx in self.selectedIndexes()})