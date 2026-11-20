from tools.houdini_help import inject_summaries, strip_summaries


def test_injects_after_id_and_enum():
    source = """@parameters
Density:
    #id: density
    Controls density.

    Low:
        Low density.
"""

    output, count = inject_summaries(
        source,
        lambda label, _description: {
            "Density": "控制密度",
            "Low": "低密度",
        }[label],
    )

    assert count == 2
    assert (
        '【<span style="color: #FFD700; font-weight: bold;">控制密度</span>】'
        in output
    )
    assert (
        '【<span style="color: #FFD700; font-weight: bold;">低密度</span>】'
        in output
    )
    assert strip_summaries(output) == source


def test_injects_after_label_when_id_is_absent():
    source = """@parameters
Size:
    Controls the size.
"""

    output, count = inject_summaries(
        source,
        lambda _label, _description: "控制尺寸",
    )

    assert count == 1
    assert output.splitlines()[2].strip() == (
        '【<span style="color: #FFD700; font-weight: bold;">控制尺寸</span>】'
    )
    assert strip_summaries(output) == source


def test_injects_after_channels_directive():
    source = """@parameters
Start:
    #channels: /start

    Start frame.
"""

    output, count = inject_summaries(
        source,
        lambda _label, _description: "起始帧",
    )

    assert count == 1
    assert output.splitlines()[3].strip() == (
        '【<span style="color: #FFD700; font-weight: bold;">起始帧</span>】'
    )
    assert strip_summaries(output) == source


def test_ignores_notes_and_requires_parameters_section():
    source = """= Node =

NOTE:
    This is not a parameter.

@parameters
TIP:
    This is also not a parameter.

Seed:
    Random seed.
"""

    output, count = inject_summaries(
        source,
        lambda _label, _description: "随机种子",
    )

    assert count == 1
    assert output.count("【<span") == 1
    assert strip_summaries(output) == source


def test_injection_is_idempotent():
    source = """@parameters
Size:
    Controls size.
"""

    once, _ = inject_summaries(source, lambda _label, _description: "控制尺寸")
    twice, count = inject_summaries(
        once,
        lambda _label, _description: "控制尺寸",
    )

    assert twice == once
    assert count == 0


def test_preserves_crlf_and_missing_final_newline():
    source = "@parameters\r\nSeed:\r\n    Random seed."

    output, count = inject_summaries(
        source,
        lambda _label, _description: "随机种子",
    )

    assert count == 1
    assert "\r\n" in output
    assert strip_summaries(output) == source
