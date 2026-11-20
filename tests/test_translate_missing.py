from pathlib import Path
from zipfile import ZipFile

from tools.translate_missing import (
    learn_legacy_pack,
    translate_missing_labels,
)
from tools.translation_memory import TranslationMemory


MARKER = '【<span style="color: #FFD700; font-weight: bold;">控制密度</span>】'


def _write_legacy_fixture(path: Path) -> Path:
    content = f"""= Density =

@parameters
Density:
    #id: density
    {MARKER}
    Controls density.
"""
    with ZipFile(path, "w") as archive:
        archive.writestr("help/nodes/sop/density.txt", content)
    return path


def test_learning_preserves_parent_label_and_description(tmp_path):
    pack = _write_legacy_fixture(tmp_path / "legacy.zip")
    memory = TranslationMemory()

    count = learn_legacy_pack(pack, memory)

    assert count == 1
    assert memory.translate("Density", None)[0] == "控制密度"
    assert memory.translate("Unknown", "Controls density.")[0] == "控制密度"


def test_network_batches_and_deduplicates_labels():
    calls = []
    memory = TranslationMemory()

    stats = translate_missing_labels(
        ["Alpha", "Beta", "alpha"],
        memory,
        batch_size=1,
        translator=lambda values: calls.append(values)
        or [f"译:{value}" for value in values],
    )

    assert stats.translated == 2
    assert stats.network_calls == 2
    assert calls == [["Alpha"], ["Beta"]]
    assert memory.translate("Alpha", None)[0] == "译:Alpha"


def test_network_failure_retries_once_then_continues():
    attempts = {"Alpha": 0, "Beta": 0}

    def translator(values):
        label = values[0]
        attempts[label] += 1
        if label == "Alpha" and attempts[label] == 1:
            raise OSError("temporary")
        return [f"译:{value}" for value in values]

    memory = TranslationMemory()
    stats = translate_missing_labels(
        ["Alpha", "Beta"],
        memory,
        batch_size=1,
        translator=translator,
    )

    assert stats.translated == 2
    assert stats.failed == 0
    assert stats.network_calls == 3


def test_network_permanent_failure_does_not_loop():
    calls = []

    def translator(values):
        calls.append(values)
        raise OSError("offline")

    memory = TranslationMemory()
    stats = translate_missing_labels(
        ["Alpha", "Beta"],
        memory,
        batch_size=1,
        translator=translator,
    )

    assert stats.translated == 0
    assert stats.failed == 2
    assert stats.failed_labels == ("Alpha", "Beta")
    assert len(calls) == 4


def test_cache_is_saved_after_each_successful_batch(tmp_path):
    cache = tmp_path / "cache.json"

    def translator(values):
        assert cache.exists() is False or values[0] == "Beta"
        return [f"译:{value}" for value in values]

    memory = TranslationMemory()
    stats = translate_missing_labels(
        ["Alpha", "Beta"],
        memory,
        batch_size=1,
        translator=translator,
        cache_path=cache,
    )

    assert stats.translated == 2
    assert cache.exists()
    assert TranslationMemory.load(cache).translate("Beta", None)[0] == "译:Beta"
