from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from zipfile import BadZipFile, ZipFile

from tools.houdini_help import MARKER_PREFIX, MARKER_SUFFIX, strip_summaries


@dataclass(frozen=True)
class VerificationReport:
    files: int
    missing_files: int
    extra_files: int
    altered_source_files: int
    invalid_marker_files: int
    summaries: int
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not any(
            (
                self.missing_files,
                self.extra_files,
                self.altered_source_files,
                self.invalid_marker_files,
                self.errors,
            )
        )


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8-sig")


def _normalize_source_name(name: str) -> str:
    return name.replace("\\", "/")


def _normalize_pack_name(name: str) -> str:
    normalized = _normalize_source_name(name)
    prefix = "help/nodes/"
    return normalized[len(prefix) :] if normalized.startswith(prefix) else normalized


def verify_pack(source_zip: Path, pack_zip: Path) -> VerificationReport:
    errors: list[str] = []
    missing_files = 0
    extra_files = 0
    altered_source_files = 0
    invalid_marker_files = 0
    summaries = 0
    source_names: set[str] = set()

    try:
        with ZipFile(source_zip) as source, ZipFile(pack_zip) as pack:
            bad_source = source.testzip()
            bad_pack = pack.testzip()
            if bad_source:
                errors.append(f"source zip corrupt: {bad_source}")
            if bad_pack:
                errors.append(f"pack zip corrupt: {bad_pack}")

            source_names = {
                _normalize_source_name(name)
                for name in source.namelist()
                if not name.endswith("/")
            }
            pack_names = {
                _normalize_pack_name(name)
                for name in pack.namelist()
                if not name.endswith("/")
            }
            missing = source_names - pack_names
            extra = pack_names - source_names
            missing_files = len(missing)
            extra_files = len(extra)

            for name in sorted(source_names & pack_names):
                source_text = _decode(source.read(name))
                try:
                    pack_text = _decode(pack.read(f"help/nodes/{name}"))
                except KeyError:
                    pack_text = _decode(pack.read(name))
                if strip_summaries(pack_text) != source_text:
                    altered_source_files += 1

                marker_lines = [
                    line
                    for line in pack_text.splitlines()
                    if MARKER_PREFIX in line
                ]
                summaries += len(marker_lines)
                for line in marker_lines:
                    stripped = line.strip()
                    if (
                        not stripped.startswith(MARKER_PREFIX)
                        or not stripped.endswith(MARKER_SUFFIX)
                        or stripped == f"{MARKER_PREFIX}{MARKER_SUFFIX}"
                    ):
                        invalid_marker_files += 1
                        break
    except (BadZipFile, FileNotFoundError, UnicodeDecodeError) as exc:
        errors.append(str(exc))

    return VerificationReport(
        files=len(source_names),
        missing_files=missing_files,
        extra_files=extra_files,
        altered_source_files=altered_source_files,
        invalid_marker_files=invalid_marker_files,
        summaries=summaries,
        errors=tuple(errors),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a Houdini Chinese tooltip pack against official help.",
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--pack", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = verify_pack(args.source, args.pack)
    payload = {**asdict(report), "ok": report.ok}
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
