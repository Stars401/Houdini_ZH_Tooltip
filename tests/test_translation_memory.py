import json
from pathlib import Path

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


def test_description_specific_translation_wins_over_label_translation():
    memory = TranslationMemory()
    memory.add("Mode", "通用模式", source="legacy-pack")
    memory.add_description("The collision response mode.", "碰撞响应模式", source="manual")

    assert memory.translate("Mode", "The collision response mode.") == (
        "碰撞响应模式",
        "manual",
    )
    assert memory.translate("Mode", None)[0] == "通用模式"


def test_save_falls_back_when_atomic_replace_is_locked(tmp_path, monkeypatch):
    path = tmp_path / "cache.json"
    memory = TranslationMemory()
    memory.add("Seed", "随机种子", source="manual")

    def locked_replace(_self, _target):
        raise PermissionError("locked")

    monkeypatch.setattr(Path, "replace", locked_replace)
    memory.save(path)

    assert TranslationMemory.load(path).translate("Seed", None)[0] == "随机种子"
