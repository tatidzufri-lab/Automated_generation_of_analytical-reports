"""Счётчик платных вызовов модели за сутки (публичное демо).

Хранится в JSON рядом с выгрузками (`storage/outputs` примонтирован как том),
поэтому переживает перезапуск контейнера. Сутки — по UTC.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DailyCounter:
    def __init__(self, path: Path, limit: int) -> None:
        self.path = path
        self.limit = limit
        self._lock = threading.Lock()

    def _today(self) -> str:
        return datetime.now(tz=UTC).strftime("%Y-%m-%d")

    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("date") == self._today():
                return data
        except (OSError, ValueError):
            pass
        return {"date": self._today(), "count": 0}

    def try_acquire(self) -> bool:
        """Засчитывает вызов и возвращает True, если суточный лимит ещё не исчерпан."""
        if self.limit <= 0:
            return True
        with self._lock:
            data = self._read()
            if data["count"] >= self.limit:
                return False
            data["count"] += 1
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(data), encoding="utf-8")
            except OSError:
                logger.exception("Не удалось записать счётчик %s", self.path)
            return True
