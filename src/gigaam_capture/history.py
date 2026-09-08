from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import AppPaths, TranscriptionRecord


class HistoryStore:
    def __init__(self, paths: AppPaths):
        self._paths = paths

    def append(self, record: TranscriptionRecord) -> None:
        text_path = Path(record.text_path)
        text_path.write_text(record.text, encoding="utf-8")
        with self._paths.history_log.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def list_recent(self, limit: int = 20) -> list[TranscriptionRecord]:
        if not self._paths.history_log.exists():
            return []

        lines = self._paths.history_log.read_text(encoding="utf-8").splitlines()
        records: list[TranscriptionRecord] = []
        for line in reversed(lines[-limit:]):
            records.append(TranscriptionRecord(**json.loads(line)))
        return records
