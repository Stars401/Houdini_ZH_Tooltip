from pathlib import Path


def test_install_script_mentions_backup_copy_and_restore():
    text = Path("tools/install_pack.ps1").read_text(encoding="utf-8")

    assert "backup" in text.lower()
    assert "Copy-Item" in text
    assert "Restore" in text
    assert "help\\nodes" in text.lower()


def test_install_script_blocks_hot_replacement_while_houdini_runs():
    text = Path("tools/install_pack.ps1").read_text(encoding="utf-8")

    assert "Assert-HoudiniNotRunning" in text
    assert "Get-Process" in text
    assert "Close all Houdini" in text
