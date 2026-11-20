from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from zipfile import ZIP_DEFLATED, ZipFile

from tools.houdini_help import inject_summaries, iter_summary_anchors
from tools.network_translation import fallback_summary, translate_labels
from tools.translate_missing import (
    learn_legacy_pack,
    translate_missing_contexts,
    translate_missing_labels,
)
from tools.translation_memory import (
    TranslationMemory,
    TranslationNotFound,
    normalize_text,
)
from tools.verify_pack import verify_pack

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


def build_pack(
    source_zip: Path,
    legacy_zip: Path,
    output_zip: Path,
    work_dir: Path,
    network_translator: Callable[[list[str]], list[str]] = translate_labels,
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
        memory.ambiguous_labels.update(cached.ambiguous_labels)

    legacy_learned = learn_legacy_pack(legacy_zip, memory)

    records: list[tuple[str, bytes, str | None, bool]] = []
    unresolved: list[str] = []
    ambiguous_contexts: list[tuple[str, str | None]] = []
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
                        if normalize_text(anchor.label) in memory.ambiguous_labels:
                            ambiguous_contexts.append(
                                (anchor.label, anchor.description)
                            )
                        else:
                            unresolved.append(anchor.label)
            records.append((name, raw, text, has_bom))

    network_translated = 0
    failed_translations = 0
    if unresolved:
        label_stats = translate_missing_labels(
            unresolved,
            memory,
            network_translator,
            cache_path=actual_cache,
        )
        network_translated += label_stats.translated
        failed_translations += label_stats.failed
    if ambiguous_contexts:
        context_stats = translate_missing_contexts(
            ambiguous_contexts,
            memory,
            network_translator,
            cache_path=actual_cache,
        )
        network_translated += context_stats.translated
        failed_translations += context_stats.failed

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
            return fallback_summary(label, description)

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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and verify the complete Houdini Chinese tooltip pack.",
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--legacy", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path, default=Path("build/work"))
    parser.add_argument("--cache", type=Path)
    parser.add_argument(
        "--glossary",
        type=Path,
        default=Path("data/glossary_zh.json"),
    )
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    stats = build_pack(
        args.source,
        args.legacy,
        args.output,
        args.work_dir,
        network_translator=translate_labels,
        cache_path=args.cache,
        glossary_path=args.glossary,
    )
    report = verify_pack(args.source, args.output)
    payload = {
        "build": asdict(stats),
        "verification": {
            **asdict(report),
            "ok": report.ok,
        },
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
