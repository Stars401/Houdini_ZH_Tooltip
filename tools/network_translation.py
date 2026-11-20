from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GOOGLE_TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"
TOKEN_PATTERNS = (
    re.compile(r"`[^`]+`"),
    re.compile(r"@[A-Za-z0-9_.]+"),
    re.compile(r"__[^_\s][^_]*__"),
    re.compile(r"\$[A-Za-z0-9_.]+"),
)
SINGLE_LABEL_FALLBACKS = {
    "N": "数量",
    "C": "通道",
    "I": "索引",
    "NC": "通道总数",
    "R": "半径",
    "V": "速度",
    "P": "位置",
}


class TranslationBatchError(ValueError):
    pass


def protect_tokens(text: str) -> tuple[str, tuple[str, ...]]:
    tokens: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = f"ZXQTOKEN{len(tokens)}ZXQ"
        tokens.append(match.group(0))
        return token

    protected = text
    for pattern in TOKEN_PATTERNS:
        protected = pattern.sub(replace, protected)
    return (protected, tuple(tokens))


def restore_tokens(text: str, tokens: Sequence[str]) -> str:
    restored = text
    for index, token in enumerate(tokens):
        restored = restored.replace(f"ZXQTOKEN{index}ZXQ", token)
    return restored


def parse_google_payload(payload: object) -> str:
    try:
        segments = payload[0]  # type: ignore[index]
        return "".join(segment[0] for segment in segments)
    except (IndexError, KeyError, TypeError) as exc:
        raise TranslationBatchError("Unexpected translation response") from exc


def google_transport(text: str, timeout: float = 30.0) -> str:
    query = urlencode(
        {
            "client": "gtx",
            "sl": "en",
            "tl": "zh-CN",
            "dt": "t",
            "q": text,
        }
    )
    request = Request(
        f"{GOOGLE_TRANSLATE_URL}?{query}",
        headers={"User-Agent": "Mozilla/5.0 Houdini-ZH-Tooltip/2.1"},
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return parse_google_payload(payload)


def translate_labels(
    labels: Sequence[str],
    transport: Callable[[str], str] = google_transport,
) -> list[str]:
    if not labels:
        return []
    protected, tokens = protect_tokens("\n".join(labels))
    translated = transport(protected)
    lines = translated.splitlines()
    if len(lines) != len(labels):
        raise TranslationBatchError(
            f"Expected {len(labels)} translated lines, received {len(lines)}"
        )
    result = [restore_tokens(line.strip(), tokens) for line in lines]
    if any(not value for value in result):
        raise TranslationBatchError("Translation contained an empty line")
    return result


def fallback_summary(label: str, description: str | None) -> str:
    cleaned = label.strip()
    if cleaned.upper() in SINGLE_LABEL_FALLBACKS:
        return SINGLE_LABEL_FALLBACKS[cleaned.upper()]
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cleaned):
        return f"选项 {cleaned}"
    if cleaned:
        return cleaned
    if description:
        return description.strip()[:40]
    return "参数"
