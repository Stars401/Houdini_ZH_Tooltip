import pytest

from tools.network_translation import (
    TranslationBatchError,
    fallback_summary,
    parse_google_payload,
    protect_tokens,
    restore_tokens,
    translate_labels,
)


def test_protect_and_restore_inline_code_tokens():
    source = "Use `$N` with @P, __value__, and Houdini_ZH"

    protected, tokens = protect_tokens(source)

    assert "`$N`" not in protected
    assert "@P" not in protected
    assert "__value__" not in protected
    assert restore_tokens(protected, tokens) == source


def test_translate_labels_preserves_batch_shape():
    def transport(text: str) -> str:
        assert text.count("\n") == 1
        return "随机种子\n数量和位置"

    result = translate_labels(
        ["Seed", "Count and Position"],
        transport=transport,
    )

    assert result == ["随机种子", "数量和位置"]


def test_translate_labels_rejects_wrong_line_count():
    with pytest.raises(TranslationBatchError):
        translate_labels(
            ["Seed", "Amount"],
            transport=lambda _text: "随机种子",
        )


def test_parse_google_payload_joins_segments():
    payload = [
        [
            ["随机种子\n", "Seed"],
            ["数量和位置", "Count and Position"],
        ],
        None,
        "en",
    ]

    assert parse_google_payload(payload) == "随机种子\n数量和位置"


def test_fallback_summary_is_never_empty():
    assert fallback_summary("N", None) == "数量"
    assert fallback_summary("C", None) == "通道"
    assert fallback_summary("1", None) == "选项 1"
    assert fallback_summary("Unknown Label", None) == "Unknown Label"
