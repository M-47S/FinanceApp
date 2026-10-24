from __future__ import annotations

import atexit
import json
from datetime import datetime as dt
from pathlib import Path
from typing import Any


class LLMLogs:
    """
    Журнал сессии в формате JSON Lines (.llg).

    Одна строка = одно событие. Формат append-only, пригоден
    для восстановления сессии и человекочитаем.
    """

    def __init__(self, filename: str | Path) -> None:
        self.__logfile = Path(filename)
        self.__logfile.parent.mkdir(parents=True, exist_ok=True)
        self.__logfile.touch(exist_ok=True)
        self.__closed = False
        atexit.register(self.close)

    @property
    def path(self) -> Path:
        return self.__logfile

    # --- запись ----------------------------------------------------------
    def event(self, kind: str, **payload: Any) -> dict:
        if self.__closed:
            raise RuntimeError("Logger is closed")
        record = {
            "ts": dt.now().isoformat(timespec="seconds"),
            "kind": kind,
            **payload,
        }
        with self.__logfile.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def log(self, text: str) -> None:
        """Обратная совместимость: произвольная текстовая строка."""
        self.event("text", text=text)

    # --- чтение ----------------------------------------------------------
    @staticmethod
    def read(path: str | Path) -> list[dict]:
        p = Path(path)
        if not p.exists():
            return []
        records: list[dict] = []
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    # битую строку молча пропускаем — логи не должны ломать restore
                    continue
        return records

    # --- lifecycle -------------------------------------------------------
    def close(self) -> None:
        if self.__closed:
            return
        self.__closed = True

    def __enter__(self) -> "LLMLogs":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()