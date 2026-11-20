from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import tools.build_pack as build_module
from tools.build_pack import build_pack
from tools.verify_pack import verify_pack


PARAMETER_FILE = """= Density =

@parameters
Density:
    #id: density
    Controls density.

    Low:
        Low density.
"""


def _write_zip(path: Path, files: dict[str, str]) -> Path:
    with ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    source = _write_zip(
        tmp_path / "source.zip",
        {
            "sop/density.txt": PARAMETER_FILE,
            "lop/empty.txt": "= Empty =\n",
        },
    )
    legacy = _write_zip(
        tmp_path / "legacy.zip",
        {
            "help/nodes/sop/density.txt": PARAMETER_FILE.replace(
                "    Controls density.",
                '    【<span style="color: #FFD700; font-weight: bold;">控制密度</span>】\n'
                "    Controls density.",
            ),
        },
    )
    return source, legacy


def test_build_then_verify(tmp_path):
    source, legacy = _fixtures(tmp_path)
    output = tmp_path / "out.zip"

    stats = build_pack(
        source,
        legacy,
        output,
        tmp_path / "work",
        network_translator=lambda values: ["低密度" for _ in values],
    )
    report = verify_pack(source, output)

    assert stats.files == 2
    assert stats.summaries == 2
    assert report.ok
    assert report.missing_files == 0
    assert report.extra_files == 0
    assert report.altered_source_files == 0
    assert report.invalid_marker_files == 0


def test_verify_detects_altered_source(tmp_path):
    source, _legacy = _fixtures(tmp_path)
    altered = _write_zip(
        tmp_path / "altered.zip",
        {
            "help/nodes/sop/density.txt": PARAMETER_FILE.replace(
                "Controls density.",
                "Changed density.",
            ),
            "help/nodes/lop/empty.txt": "= Empty =\n",
        },
    )

    report = verify_pack(source, altered)

    assert not report.ok
    assert report.altered_source_files == 1


def test_verify_detects_missing_file(tmp_path):
    source, _legacy = _fixtures(tmp_path)
    incomplete = _write_zip(
        tmp_path / "incomplete.zip",
        {
            "help/nodes/sop/density.txt": PARAMETER_FILE,
        },
    )

    report = verify_pack(source, incomplete)

    assert not report.ok
    assert report.missing_files == 1


def test_build_uses_default_network_translator(tmp_path, monkeypatch):
    source, legacy = _fixtures(tmp_path)
    monkeypatch.setattr(
        build_module,
        "translate_labels",
        lambda values: ["低密度" for _ in values],
    )

    stats = build_pack(
        source,
        legacy,
        tmp_path / "out.zip",
        tmp_path / "work",
    )

    assert stats.network_translated >= 1


def test_build_uses_local_fallback_after_translation_failure(tmp_path):
    source = _write_zip(
        tmp_path / "source.zip",
        {
            "sop/local.txt": """@parameters
N:
    Current chunk.
""",
        },
    )
    legacy = _write_zip(tmp_path / "legacy.zip", {})

    def offline(_values):
        raise OSError("offline")

    output = tmp_path / "out.zip"
    stats = build_pack(
        source,
        legacy,
        output,
        tmp_path / "work",
        network_translator=offline,
    )

    assert stats.failed_translations == 1
    with ZipFile(output) as archive:
        text = archive.read("help/nodes/sop/local.txt").decode("utf-8")
    assert "数量" in text
    assert verify_pack(source, output).ok


def test_build_cli_help_is_available():
    result = subprocess.run(
        [sys.executable, "-m", "tools.build_pack", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--source" in result.stdout


def test_verify_cli_help_is_available():
    result = subprocess.run(
        [sys.executable, "-m", "tools.verify_pack", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--pack" in result.stdout
