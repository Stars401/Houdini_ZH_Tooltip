from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata


class TranslationNotFound(KeyError):
    pass


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip().casefold()


def _description_key(description: str) -> str:
    return normalize_text(description)[:160]


@dataclass(frozen=True)
class TranslationEntry:
    value: str
    source: str


class TranslationMemory:
    def __init__(self, glossary: Mapping[str, str] | None = None) -> None:
        self.glossary = {
            normalize_text(label): value.strip()
            for label, value in (glossary or {}).items()
            if label.strip() and value.strip()
        }
        self.entries: dict[str, TranslationEntry] = {}
        self.description_entries: dict[str, TranslationEntry] = {}
        self.ambiguous_labels: set[str] = set()

    def add(self, label: str, value: str, source: str) -> None:
        key = normalize_text(label)
        cleaned = value.strip()
        if key and cleaned:
            self.entries[key] = TranslationEntry(value=cleaned, source=source)

    def add_description(self, description: str, value: str, source: str) -> None:
        key = _description_key(description)
        cleaned = value.strip()
        if key and cleaned:
            self.description_entries[key] = TranslationEntry(
                value=cleaned,
                source=source,
            )

    def mark_ambiguous(self, label: str) -> None:
        key = normalize_text(label)
        if key:
            self.ambiguous_labels.add(key)

    def translate(
        self,
        label: str,
        description: str | None,
    ) -> tuple[str, str]:
        label_key = normalize_text(label)
        if label_key in self.glossary:
            return (self.glossary[label_key], "glossary")
        if description:
            description_key = _description_key(description)
            if description_key in self.description_entries:
                entry = self.description_entries[description_key]
                return (entry.value, entry.source)
        if label_key in self.ambiguous_labels:
            raise TranslationNotFound(label)
        if label_key in self.entries:
            entry = self.entries[label_key]
            return (entry.value, entry.source)
        raise TranslationNotFound(label)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "glossary": dict(sorted(self.glossary.items())),
            "entries": {
                key: {"value": entry.value, "source": entry.source}
                for key, entry in sorted(self.entries.items())
            },
            "descriptions": {
                key: {"value": entry.value, "source": entry.source}
                for key, entry in sorted(self.description_entries.items())
            },
            "ambiguous_labels": sorted(self.ambiguous_labels),
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        try:
            temporary.replace(path)
        except PermissionError:
            path.write_bytes(temporary.read_bytes())
            temporary.unlink(missing_ok=True)

    @classmethod
    def load(cls, path: Path) -> "TranslationMemory":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if "entries" not in payload:
            memory = cls()
            for label, value in payload.items():
                memory.add(label, value, source="legacy-flat")
            return memory

        memory = cls(glossary=payload.get("glossary", {}))
        for key, raw_entry in payload.get("entries", {}).items():
            memory.add(
                key,
                raw_entry["value"],
                source=raw_entry.get("source", "cache"),
            )
        for key, raw_entry in payload.get("descriptions", {}).items():
            memory.description_entries[key] = TranslationEntry(
                value=raw_entry["value"],
                source=raw_entry.get("source", "cache"),
            )
        memory.ambiguous_labels.update(payload.get("ambiguous_labels", []))
        return memory
