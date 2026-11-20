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


def test_build_uses_context_translation_for_ambiguous_labels(tmp_path):
    source = _write_zip(
        tmp_path / "source.zip",
        {
            "sop/first.txt": """@parameters
Mode:
    #id: mode
    First point mode.
""",
            "sop/second.txt": """@parameters
Mode:
    #id: mode
    Second point mode.
""",
        },
    )
    legacy = _write_zip(
        tmp_path / "legacy.zip",
        {
            "help/nodes/sop/first.txt": """@parameters
Mode:
    #id: mode
    【<span style="color: #FFD700; font-weight: bold;">第一个模式</span>】
    Legacy first description.
""",
            "help/nodes/sop/second.txt": """@parameters
Mode:
    #id: mode
    【<span style="color: #FFD700; font-weight: bold;">第二个模式</span>】
    Legacy second description.
""",
        },
    )

    stats = build_pack(
        source,
        legacy,
        tmp_path / "out.zip",
        tmp_path / "work",
        network_translator=lambda values: [
            value.replace("Mode: ", "模式：") for value in values
        ],
    )

    assert stats.network_translated == 2
    with ZipFile(tmp_path / "out.zip") as archive:
        first = archive.read("help/nodes/sop/first.txt").decode("utf-8")
        second = archive.read("help/nodes/sop/second.txt").decode("utf-8")
    assert "模式：First point mode." in first
    assert "模式：Second point mode." in second


def test_build_context_translates_any_new_label_with_description(tmp_path):
    source = _write_zip(
        tmp_path / "source.zip",
        {
            "dop/pop.txt": """parameters id="common">>
    Activation:
        #channels: /activate

        Turns this node on and off.
""",
        },
    )
    legacy = _write_zip(tmp_path / "legacy.zip", {})
    prompts = []

    def translator(values):
        prompts.extend(values)
        return ["启用：控制节点开关"]

    stats = build_pack(
        source,
        legacy,
        tmp_path / "out.zip",
        tmp_path / "work",
        network_translator=translator,
    )

    assert stats.network_translated == 1
    assert prompts == ["Activation: Turns this node on and off."]
    with ZipFile(tmp_path / "out.zip") as archive:
        text = archive.read("help/nodes/dop/pop.txt").decode("utf-8")
    assert "启用：控制节点开关" in text


def test_build_retranslates_cached_network_labels_with_context(tmp_path):
    source = _write_zip(
        tmp_path / "source.zip",
        {
            "lop/material.txt": """@parameters
Roughness:
    Controls how rough the surface appears.
""",
        },
    )
    legacy = _write_zip(tmp_path / "legacy.zip", {})
    cache = tmp_path / "cache.json"
    cache.write_text(
        """{
  "version": 1,
  "glossary": {},
  "entries": {
    "roughness": {"value": "Roughness", "source": "network"}
  },
  "descriptions": {},
  "ambiguous_labels": []
}""",
        encoding="utf-8",
    )
    prompts = []

    def translator(values):
        prompts.extend(values)
        return ["粗糙度：控制表面看起来有多粗糙。"]

    build_pack(
        source,
        legacy,
        tmp_path / "out.zip",
        tmp_path / "work",
        network_translator=translator,
        cache_path=cache,
    )

    assert prompts == ["Roughness: Controls how rough the surface appears."]
    with ZipFile(tmp_path / "out.zip") as archive:
        text = archive.read("help/nodes/lop/material.txt").decode("utf-8")
    assert "粗糙度：控制表面看起来有多粗糙。" in text


def test_build_uses_small_context_batches(tmp_path):
    files = {}
    for index in range(6):
        files[f"sop/test{index}.txt"] = f"""@parameters
Label {index}:
    Unique description number {index}.
"""
    source = _write_zip(tmp_path / "source.zip", files)
    legacy = _write_zip(tmp_path / "legacy.zip", {})
    batch_sizes = []

    def translator(values):
        batch_sizes.append(len(values))
        return [f"翻译 {index}" for index, _value in enumerate(values)]

    build_pack(
        source,
        legacy,
        tmp_path / "out.zip",
        tmp_path / "work",
        network_translator=translator,
    )

    assert batch_sizes
    assert max(batch_sizes) <= 5


def test_build_retranslates_legacy_english_summary_with_context(tmp_path):
    source = _write_zip(
        tmp_path / "source.zip",
        {
            "sop/rough.txt": """@parameters
Roughness:
    Controls surface roughness.
""",
        },
    )
    legacy = _write_zip(
        tmp_path / "legacy.zip",
        {
            "help/nodes/sop/rough.txt": """@parameters
Roughness:
    【<span style="color: #FFD700; font-weight: bold;">Roughness</span>】
    Controls surface roughness.
""",
        },
    )
    prompts = []

    def translator(values):
        prompts.extend(values)
        return ["粗糙度：控制表面粗糙程度。"]

    build_pack(
        source,
        legacy,
        tmp_path / "out.zip",
        tmp_path / "work",
        network_translator=translator,
    )

    assert prompts == ["Roughness: Controls surface roughness."]


def test_build_force_translates_english_label_without_description(tmp_path):
    source = _write_zip(
        tmp_path / "source.zip",
        {
            "cop/rough.txt": """@parameters
Roughness:
    #contentfrom: /nodes/cop/source#rough
""",
        },
    )
    legacy = _write_zip(
        tmp_path / "legacy.zip",
        {
            "help/nodes/cop/rough.txt": """@parameters
Roughness:
    #contentfrom: /nodes/cop/source#rough
    【<span style="color: #FFD700; font-weight: bold;">Roughness</span>】
""",
        },
    )
    prompts = []

    def translator(values):
        prompts.extend(values)
        return ["粗糙度" for _ in values]

    build_pack(
        source,
        legacy,
        tmp_path / "out.zip",
        tmp_path / "work",
        network_translator=translator,
    )

    assert prompts == ["Roughness"]


def test_build_cache_overrides_legacy_raw_label(tmp_path):
    source = _write_zip(
        tmp_path / "source.zip",
        {
            "cop/rough.txt": """@parameters
Roughness:
    #contentfrom: /nodes/cop/source#rough
""",
        },
    )
    legacy = _write_zip(
        tmp_path / "legacy.zip",
        {
            "help/nodes/cop/rough.txt": """@parameters
Roughness:
    #contentfrom: /nodes/cop/source#rough
    【<span style="color: #FFD700; font-weight: bold;">Roughness</span>】
""",
        },
    )
    cache = tmp_path / "cache.json"
    cache.write_text(
        """{
  "version": 1,
  "glossary": {},
  "entries": {
    "roughness": {"value": "粗糙度", "source": "network"}
  },
  "descriptions": {},
  "ambiguous_labels": []
}""",
        encoding="utf-8",
    )

    build_pack(
        source,
        legacy,
        tmp_path / "out.zip",
        tmp_path / "work",
        network_translator=lambda _values: (_ for _ in ()).throw(
            AssertionError("network should not be called")
        ),
        cache_path=cache,
    )

    with ZipFile(tmp_path / "out.zip") as archive:
        text = archive.read("help/nodes/cop/rough.txt").decode("utf-8")
    assert "粗糙度" in text
