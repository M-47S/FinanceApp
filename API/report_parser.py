"""Парсер месячного отчёта (формат 'Август.xlsx')."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from .exceptions import ExcelReadError, ValidationError

META_ROW = 0
HEADER_ROW = 1
FIRST_DATA_ROW = 2                       # 0-индекс
EXCEL_FIRST_DATA_ROW = FIRST_DATA_ROW + 1  # 1-индекс для логов = 3

IGNORED_COLUMNS = {"общий баланс"}
REQUIRED_COLUMNS = {"Число", "Операция", "Источник", "Тип"}

MONTHS_RU = {
    "январь": 1, "февраль": 2, "март": 3, "апрель": 4,
    "май": 5, "июнь": 6, "июль": 7, "август": 8,
    "сентябрь": 9, "октябрь": 10, "ноябрь": 11, "декабрь": 12,
}


@dataclass
class ParsedReport:
    month: int
    year: int
    df: pd.DataFrame                 # op_date, amount, reason_name, type_name
    excel_first_data_row: int        # 1-индексированный первый ряд данных


def parse_monthly_report(
    file_path: str | Path,
    sheet_name: str | int = 0,
) -> ParsedReport:
    try:
        raw = pd.read_excel(
            file_path, sheet_name=sheet_name,
            header=None, engine="openpyxl",
        )
    except Exception as e:
        raise ExcelReadError(f"Cannot read '{file_path}': {e}") from e

    month, year = _parse_meta(raw, file_path)

    try:
        df = pd.read_excel(
            file_path, sheet_name=sheet_name,
            header=HEADER_ROW, engine="openpyxl",
        )
    except Exception as e:
        raise ExcelReadError(f"Cannot read '{file_path}': {e}") from e

    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValidationError(
            f"В '{file_path}' нет обязательных колонок: {sorted(missing)}"
        )

    drop = [c for c in df.columns
            if str(c).strip().lower() in IGNORED_COLUMNS]
    df = df.drop(columns=drop, errors="ignore")

    df["op_date"] = df["Число"].apply(lambda d: _to_date(year, month, d))
    df["amount"] = pd.to_numeric(df["Операция"], errors="coerce")
    df["reason_name"] = df["Источник"].astype(str).str.strip()
    df["type_name"] = df["Тип"].astype(str).str.strip()

    # сохраняем исходный excel-ряд рядом с данными — понадобится для лога
    df["_excel_row"] = range(
        EXCEL_FIRST_DATA_ROW, EXCEL_FIRST_DATA_ROW + len(df),
    )

    out = df[["op_date", "amount", "reason_name", "type_name", "_excel_row"]]
    # отсеиваем строки с пустыми/невалидными датой или суммой
    out = out.dropna(subset=["op_date", "amount"]).reset_index(drop=True)

    return ParsedReport(
        month=month, year=year,
        df=out,
        excel_first_data_row=EXCEL_FIRST_DATA_ROW,
    )


def _parse_meta(raw: pd.DataFrame, path) -> tuple[int, int]:
    try:
        month_name = str(raw.iloc[META_ROW, 0]).strip().lower()
        year = int(raw.iloc[META_ROW, 1])
    except Exception as e:
        raise ValidationError(
            f"Не удалось прочитать Месяц/Год из '{path}' (ряд 1)"
        ) from e
    if month_name not in MONTHS_RU:
        raise ValidationError(f"Неизвестный месяц: '{month_name}'")
    return MONTHS_RU[month_name], year


def _to_date(year: int, month: int, day) -> date | None:
    try:
        d = int(day)
        last = calendar.monthrange(year, month)[1]
        if 1 <= d <= last:
            return date(year, month, d)
    except (ValueError, TypeError):
        pass
    return None