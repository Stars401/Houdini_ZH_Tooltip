from __future__ import annotations

from collections.abc import Callable, Iterable
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
from zipfile import ZipFile

from tools.houdini_help import LABEL_RE
from tools.translation_memory import (
    TranslationMemory,
    TranslationNotFound,
    normalize_text,
)

MARKER_VALUE_RE = re.compile(
    r"【<span style=\"color: #FFD700; font-weight: bold;\">"
    r"(?P<value>.*?)</span>】"
)


@dataclass(frozen=True)
class TranslationStats:
    translated: int
    failed: int
    network_calls: int
    failed_labels: tuple[str, ...]


def _plain_lines(text: str) -> list[str]:
    return [line.rstrip("\r\n").lstrip("\ufeff") for line in text.splitlines()]


def _learned_parent_label(lines: list[str], marker_index: int) -> str | None:
    for index in range(marker_index - 1, max(-1, marker_index - 8), -1):
        line = lines[index]
        if not line.strip():
            continue
        match = LABEL_RE.match(line)
        if match is not None:
            return match.group("label").strip()
    return None


def _learned_description(lines: list[str], marker_index: int) -> str | None:
    for line in lines[marker_index + 1 :]:
        stripped = line.strip()
        if not stripped or MARKER_VALUE_RE.search(line):
            continue
        if stripped.startswith(("#", ":", "=", "[Image:", "* ", "- ")):
            return None
        if LABEL_RE.match(line):
            return None
        return stripped
    return None


def learn_legacy_pack(path: Path, memory: TranslationMemory) -> int:
    learned = 0
    label_values: dict[str, Counter[str]] = defaultdict(Counter)
    with ZipFile(path) as archive:
        for name in archive.namelist():
            normalized_name = name.replace("\\", "/")
            if not normalized_name.endswith(".txt"):
                continue
            text = archive.read(name).decode("utf-8-sig", errors="replace")
            lines = _plain_lines(text)
            for index, line in enumerate(lines):
                match = MARKER_VALUE_RE.search(line)
                if match is None:
                    continue
                value = match.group("value").strip()
                if not value:
                    continue
                label = _learned_parent_label(lines, index)
                if label:
                    label_values[label][value] += 1
                description = _learned_description(lines, index)
                if description:
                    memory.add_description(
                        description,
                        value,
                        source="legacy-pack",
                    )
                learned += 1
    for label, values in label_values.items():
        if len(values) == 1:
            value = next(iter(values))
            memory.add(label, value, source="legacy-pack")
        else:
            memory.mark_ambiguous(label)
    return learned


def translate_missing_labels(
    labels: Iterable[str],
    memory: TranslationMemory,
    translator: Callable[[list[str]], list[str]],
    batch_size: int = 60,
    cache_path: Path | None = None,
) -> TranslationStats:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    unique: list[str] = []
    seen: set[str] = set()
    for label in labels:
        cleaned = label.strip()
        key = normalize_text(cleaned)
        if not cleaned or key in seen:
            continue
        seen.add(key)
        try:
            memory.translate(cleaned, None)
        except TranslationNotFound:
            unique.append(cleaned)

    translated = 0
    failed_labels: list[str] = []
    network_calls = 0

    for start in range(0, len(unique), batch_size):
        batch = unique[start : start + batch_size]
        result: list[str] | None = None
        for _attempt in range(2):
            network_calls += 1
            try:
                candidate = list(translator(batch))
                if len(candidate) != len(batch):
                    raise ValueError(
                        f"Translator returned {len(candidate)} values for {len(batch)} labels"
                    )
                if any(not value.strip() for value in candidate):
                    raise ValueError("Translator returned an empty value")
                result = [value.strip() for value in candidate]
                break
            except Exception:
                result = None

        if result is None:
            failed_labels.extend(batch)
            continue

        for label, value in zip(batch, result, strict=True):
            memory.add(label, value, source="network")
            translated += 1
        if cache_path is not None:
            memory.save(cache_path)

    return TranslationStats(
        translated=translated,
        failed=len(failed_labels),
        network_calls=network_calls,
        failed_labels=tuple(failed_labels),
    )


def translate_missing_contexts(
    pairs: Iterable[tuple[str, str | None]],
    memory: TranslationMemory,
    translator: Callable[[list[str]], list[str]],
    batch_size: int = 20,
    cache_path: Path | None = None,
) -> TranslationStats:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    unique: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for label, description in pairs:
        if not label.strip() or not description or not description.strip():
            continue
        key = (normalize_text(label), normalize_text(description))
        if key in seen:
            continue
        seen.add(key)
        try:
            memory.translate(label, description)
        except TranslationNotFound:
            unique.append((label.strip(), description.strip()))

    translated = 0
    failed_labels: list[str] = []
    network_calls = 0

    for start in range(0, len(unique), batch_size):
        batch = unique[start : start + batch_size]
        prompts = [f"{label}: {description}" for label, description in batch]
        result: list[str] | None = None
        for _attempt in range(2):
            network_calls += 1
            try:
                candidate = list(translator(prompts))
                if len(candidate) != len(batch):
                    raise ValueError(
                        f"Translator returned {len(candidate)} values for {len(batch)} contexts"
                    )
                if any(not value.strip() for value in candidate):
                    raise ValueError("Translator returned an empty context summary")
                result = [value.strip() for value in candidate]
                break
            except Exception:
                result = None

        if result is None:
            failed_labels.extend(label for label, _description in batch)
            continue

        for (label, description), value in zip(batch, result, strict=True):
            memory.add_description(
                description,
                value,
                source="network-context",
            )
            translated += 1
        if cache_path is not None:
            memory.save(cache_path)

    return TranslationStats(
        translated=translated,
        failed=len(failed_labels),
        network_calls=network_calls,
        failed_labels=tuple(failed_labels),
    )
