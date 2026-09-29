from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem
import pandas as pd


class _NumericItem(QTableWidgetItem):
    """Ячейка, которая сортируется как число, если значение числовое."""

    def __init__(self, value):
        super().__init__(str(value) if value is not None else "")
        self._raw = value

    def __lt__(self, other):
        try:
            return float(self._raw) < float(other._raw)
        except (TypeError, ValueError):
            return super().__lt__(other)


class ResultTable(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def load_dataframe(self, df: pd.DataFrame) -> None:
        # Отключаем сортировку на время заполнения — иначе строки разъезжаются
        self.setSortingEnabled(False)
        self.clear()
        self.setRowCount(len(df))
        self.setColumnCount(len(df.columns))
        self.setHorizontalHeaderLabels([str(c) for c in df.columns])

        for i, (_, row) in enumerate(df.iterrows()):
            for j, val in enumerate(row):
                item = _NumericItem(val) if isinstance(val, (int, float)) else QTableWidgetItem(
                    "" if val is None else str(val)
                )
                self.setItem(i, j, item)

        self.resizeColumnsToContents()
        self.setSortingEnabled(True)