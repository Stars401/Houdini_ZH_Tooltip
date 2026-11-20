from pathlib import Path
from zipfile import ZipFile

from tools.translate_missing import (
    condense_context_summary,
    learn_legacy_pack,
    needs_context_translation,
    translate_missing_contexts,
    translate_missing_labels,
)
from tools.translation_memory import TranslationMemory
from tools.translation_memory import TranslationNotFound
import pytest


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


def test_forced_label_translation_replaces_raw_existing_value():
    memory = TranslationMemory()
    memory.add("Roughness", "Roughness", source="legacy-pack")

    stats = translate_missing_labels(
        ["Roughness"],
        memory,
        translator=lambda values: ["粗糙度" for _ in values],
        force=True,
    )

    assert stats.translated == 1
    assert memory.translate("Roughness", None) == ("粗糙度", "network")


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


def test_conflicting_labels_require_description_context(tmp_path):
    first = """@parameters
Group:
    #id: group
    【<span style="color: #FFD700; font-weight: bold;">第一个组</span>】
    First group description.
"""
    second = """@parameters
Group:
    #id: group
    【<span style="color: #FFD700; font-weight: bold;">第二个组</span>】
    Second group description.
"""
    pack = tmp_path / "legacy.zip"
    with ZipFile(pack, "w") as archive:
        archive.writestr("help/nodes/sop/first.txt", first)
        archive.writestr("help/nodes/sop/second.txt", second)
    memory = TranslationMemory()

    learn_legacy_pack(pack, memory)

    with pytest.raises(TranslationNotFound):
        memory.translate("Group", None)
    assert memory.translate("Group", "First group description.")[0] == "第一个组"
    assert memory.translate("Group", "Second group description.")[0] == "第二个组"


def test_context_translation_resolves_ambiguous_label(tmp_path):
    memory = TranslationMemory()
    memory.mark_ambiguous("Group")
    cache = tmp_path / "cache.json"
    seen = []

    def translator(values):
        seen.extend(values)
        return ["组：当前操作的几何点组"]

    stats = translate_missing_contexts(
        [("Group", "The point group to operate on.")],
        memory,
        translator,
        cache_path=cache,
    )

    assert stats.translated == 1
    assert seen == ["Group: The point group to operate on."]
    assert (
        memory.translate("Group", "The point group to operate on.")[0]
        == "组：当前操作的几何点组"
    )
    assert cache.exists()


def test_context_summary_strips_untranslated_label_and_condenses():
    assert condense_context_summary(
        "value",
        "value：要计算绝对值的输入。后续说明不应重复。",
    ) == "要计算绝对值的输入。"
    assert condense_context_summary(
        "Activation",
        "激活：打开和关闭该节点。此节点仅在数值大于零时生效。",
    ) == "激活：打开和关闭该节点。"


def test_needs_context_translation_skips_acronyms_but_retries_english_words():
    assert needs_context_translation("Roughness", "Roughness") is True
    assert needs_context_translation("`*`geo", "`*`geo") is True
    assert needs_context_translation("SOP", "SOP") is False
    assert needs_context_translation("RGB", "RGB") is False
    assert needs_context_translation("N", "N") is False
    assert needs_context_translation("Roughness", "粗糙度") is False
