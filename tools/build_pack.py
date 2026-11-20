from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from tools.houdini_help import inject_summaries, iter_summary_anchors
from tools.translate_missing import learn_legacy_pack, translate_missing_labels
from tools.translation_memory import TranslationMemory, TranslationNotFound

UTF8_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True)
class BuildStats:
    files: int
    summaries: int
    legacy_learned: int
    network_translated: int
    failed_translations: int


def _decode_help(raw: bytes) -> tuple[str, bool]:
    has_bom = raw.startswith(UTF8_BOM)
    return (raw.decode("utf-8-sig"), has_bom)


def _encode_help(text: str, has_bom: bool) -> bytes:
    return text.encode("utf-8-sig" if has_bom else "utf-8")


def _load_glossary(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    return payload.get("terms", payload)


def _fallback_summary(label: str, description: str | None) -> str:
    if label.strip():
        return label.strip()
    if description:
        return description.strip()[:40]
    return "参数"


def build_pack(
    source_zip: Path,
    legacy_zip: Path,
    output_zip: Path,
    work_dir: Path,
    network_translator: Callable[[list[str]], list[str]] | None = None,
    cache_path: Path | None = None,
    glossary_path: Path | None = None,
) -> BuildStats:
    glossary = _load_glossary(glossary_path or Path("data/glossary_zh.json"))
    actual_cache = cache_path or work_dir / "translation_cache.json"

    memory = TranslationMemory(glossary=glossary)
    if actual_cache.exists():
        cached = TranslationMemory.load(actual_cache)
        for key, value in cached.glossary.items():
            memory.glossary.setdefault(key, value)
        memory.entries.update(cached.entries)
        memory.description_entries.update(cached.description_entries)

    legacy_learned = learn_legacy_pack(legacy_zip, memory)

    records: list[tuple[str, bytes, str | None, bool]] = []
    unresolved: list[str] = []
    with ZipFile(source_zip) as source:
        for name in source.namelist():
            if name.endswith("/"):
                continue
            raw = source.read(name)
            text: str | None = None
            has_bom = False
            if name.lower().endswith(".txt"):
                text, has_bom = _decode_help(raw)
                for anchor in iter_summary_anchors(text):
                    try:
                        memory.translate(anchor.label, anchor.description)
                    except TranslationNotFound:
                        unresolved.append(anchor.label)
            records.append((name, raw, text, has_bom))

    network_translated = 0
    failed_translations = 0
    if unresolved and network_translator is not None:
        stats = translate_missing_labels(
            unresolved,
            memory,
            network_translator,
            cache_path=actual_cache,
        )
        network_translated = stats.translated
        failed_translations = stats.failed

    output_zip.parent.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    temporary_zip = output_zip.with_suffix(output_zip.suffix + ".tmp")
    if temporary_zip.exists():
        temporary_zip.unlink()

    summary_count = 0

    def translate(label: str, description: str | None) -> str:
        try:
            value, _source = memory.translate(label, description)
            return value
        except TranslationNotFound:
            return _fallback_summary(label, description)

    try:
        with ZipFile(temporary_zip, "w", compression=ZIP_DEFLATED) as output:
            for name, raw, text, has_bom in records:
                if text is None:
                    payload = raw
                else:
                    translated, count = inject_summaries(text, translate)
                    summary_count += count
                    payload = _encode_help(translated, has_bom)
                output.writestr(f"help/nodes/{name}", payload)
        temporary_zip.replace(output_zip)
    except Exception:
        if temporary_zip.exists():
            temporary_zip.unlink()
        raise

    return BuildStats(
        files=len(records),
        summaries=summary_count,
        legacy_learned=legacy_learned,
        network_translated=network_translated,
        failed_translations=failed_translations,
    )
