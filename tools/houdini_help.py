from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

MARKER_PREFIX = '【<span style="color: #FFD700; font-weight: bold;">'
MARKER_SUFFIX = "</span>】"
MARKER_LINE_RE = re.compile(
    r"^\s*【<span style=\"color: #FFD700; font-weight: bold;\">"
    r".*?</span>】\s*$"
)
LABEL_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<label>::[^:]{1,159}|[^:=\[\]<#\s][^:]{0,159}):[ \t]*"
    r"(?P<newline>\r?\n)?$"
)
SECTION_LABELS = {
    "NOTE",
    "TIP",
    "WARNING",
    "EXAMPLE",
    "EXAMPLES",
    "OVERVIEW",
    "PARAMETERS",
}
DIRECTIVE_PREFIXES = (
    "#id:",
    "#channels:",
    "#kagroup:",
    "#contentfrom:",
)
SECTION_HEADERS = {
    "@parameters",
    "@inputs",
    "@outputs",
    "@input",
    "@output",
    "@locals",
    "@attributes",
    "@top_attributes",
}


@dataclass(frozen=True)
class SummaryAnchor:
    label: str
    description: str | None
    insert_after: int
    indent: str
    block_end: int


def _indent_width(line: str) -> int:
    prefix = line[: len(line) - len(line.lstrip(" \t"))]
    return len(prefix.expandtabs(4))


def _is_marker(line: str) -> bool:
    return bool(MARKER_LINE_RE.match(line))


def _line_text(line: str) -> str:
    return line.rstrip("\r\n").lstrip("\ufeff")


def _newline_for(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def _is_section_start(line: str) -> bool:
    stripped = _line_text(line).strip()
    if stripped.endswith(":"):
        stripped = stripped[:-1].rstrip()
    return stripped in SECTION_HEADERS or (
        stripped.startswith('parameters id="') and stripped.endswith(">>")
    )


def _section_ranges(lines: list[str]) -> list[tuple[int, int]]:
    starts = [
        index
        for index, line in enumerate(lines)
        if _is_section_start(line)
    ]
    return [
        (start + 1, starts[position + 1] if position + 1 < len(starts) else len(lines))
        for position, start in enumerate(starts)
    ]


def _block_end(lines: list[str], start: int, end: int, indent: int) -> int:
    for index in range(start + 1, end):
        line = lines[index]
        if not _line_text(line).strip():
            continue
        if _indent_width(line) <= indent:
            return index
    return end


def _direct_indices(
    lines: list[str],
    block_start: int,
    block_end: int,
) -> list[int]:
    nonblank = [
        index
        for index in range(block_start + 1, block_end)
        if _line_text(lines[index]).strip() and not _is_marker(lines[index])
    ]
    if not nonblank:
        return []
    minimum = min(_indent_width(lines[index]) for index in nonblank)
    return [index for index in nonblank if _indent_width(lines[index]) == minimum]


def _description(
    lines: list[str],
    direct_indices: list[int],
) -> str | None:
    chunks: list[str] = []
    for index in direct_indices:
        text = _line_text(lines[index]).strip()
        if not text:
            continue
        if text.startswith(("#", ":", "=", "[Image:", "* ", "- ")):
            continue
        if LABEL_RE.match(_line_text(lines[index])):
            continue
        chunks.append(text)
        next_index = index + 1
        while next_index < len(lines):
            next_text = _line_text(lines[next_index]).strip()
            if not next_text:
                break
            if next_text.startswith(("#", ":", "=", "[Image:", "* ", "- ")):
                break
            chunks.append(next_text)
            next_index += 1
        break
    return " ".join(chunks) or None


def _anchor_for_label(
    lines: list[str],
    label_index: int,
    end: int,
) -> SummaryAnchor | None:
    match = LABEL_RE.match(_line_text(lines[label_index]))
    if match is None:
        return None

    raw_label = match.group("label").strip()
    label = raw_label[2:] if raw_label.startswith("::") else raw_label
    if label.upper() in SECTION_LABELS:
        return None

    indent = _indent_width(lines[label_index])
    block_end = _block_end(lines, label_index, end, indent)
    direct = _direct_indices(lines, label_index, block_end)
    if not direct:
        return None

    first_direct = direct[0]
    directives = [
        index
        for index in range(label_index + 1, first_direct + 1)
        if _line_text(lines[index]).strip().startswith(DIRECTIVE_PREFIXES)
    ]
    description = _description(lines, direct)

    if description is None and not directives:
        return None

    if any(_is_marker(lines[index]) for index in range(label_index + 1, block_end)):
        return None

    insert_after = directives[-1] if directives else label_index
    return SummaryAnchor(
        label=label,
        description=description,
        insert_after=insert_after,
        indent=lines[insert_after][: len(lines[insert_after]) - len(lines[insert_after].lstrip(" \t"))],
        block_end=block_end,
    )


def iter_summary_anchors(text: str) -> Iterator[SummaryAnchor]:
    lines = text.splitlines(keepends=True)
    for start, end in _section_ranges(lines):
        for index in range(start, end):
            anchor = _anchor_for_label(lines, index, end)
            if anchor is not None:
                yield anchor


def inject_summaries(
    text: str,
    translate: Callable[[str, str | None], str],
) -> tuple[str, int]:
    newline = _newline_for(text)
    lines = text.splitlines(keepends=True)
    anchors = sorted(iter_summary_anchors(text), key=lambda item: item.insert_after, reverse=True)

    for anchor in anchors:
        summary = translate(anchor.label, anchor.description).strip()
        if not summary:
            raise ValueError(f"Empty summary for parameter label: {anchor.label}")
        anchor_line = lines[anchor.insert_after]
        if not anchor_line.endswith(("\n", "\r")):
            anchor_line += newline
            lines[anchor.insert_after] = anchor_line
        lines.insert(
            anchor.insert_after + 1,
            f"{anchor.indent}{MARKER_PREFIX}{summary}{MARKER_SUFFIX}{newline}",
        )

    return ("".join(lines), len(anchors))


def strip_summaries(text: str) -> str:
    return "".join(line for line in text.splitlines(keepends=True) if not _is_marker(line))
