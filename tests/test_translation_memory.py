import json

import pytest

from tools.translation_memory import (
    TranslationMemory,
    TranslationNotFound,
    normalize_text,
)


def test_glossary_overrides_machine_value():
    memory = TranslationMemory(glossary={"Density Scale": "密度缩放"})
    memory.add("Density Scale", "密度标度", source="machine")

    assert memory.translate("Density Scale", None) == ("密度缩放", "glossary")


def test_cache_round_trip(tmp_path):
    path = tmp_path / "translations.json"
    memory = TranslationMemory()
    memory.add("Seed", "随机种子", source="manual")
    memory.save(path)

    loaded = TranslationMemory.load(path)

    assert loaded.translate("Seed", None) == ("随机种子", "manual")


def test_description_fallback_and_normalization():
    memory = TranslationMemory()
    description = "  Controls   the overall density.\nUsed by smoke. "
    memory.add_description(description, "控制整体密度", source="legacy")

    value, source = memory.translate(
        "Unknown Label",
        "controls the overall density. used by smoke.",
    )

    assert value == "控制整体密度"
    assert source == "legacy"
    assert normalize_text(description) == "controls the overall density. used by smoke."


def test_missing_translation_is_explicit():
    memory = TranslationMemory()

    with pytest.raises(TranslationNotFound):
        memory.translate("Not Translated", None)


def test_loads_legacy_flat_cache(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps({"Seed": "随机种子"}, ensure_ascii=False),
        encoding="utf-8",
    )

    memory = TranslationMemory.load(path)

    assert memory.translate("seed", None)[0] == "随机种子"
