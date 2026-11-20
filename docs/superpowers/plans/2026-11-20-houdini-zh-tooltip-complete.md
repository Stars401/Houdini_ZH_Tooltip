# Houdini 中文参数提示全量补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Houdini 22.0.368 的全部 5,034 个节点帮助文件生成完整中文参数摘要，验证、安装并推送发布包。

**Architecture:** 从官方 `nodes.zip` 重建内容；解析帮助 DSL 后只插入独立摘要行。旧包用于翻译记忆，网络翻译补齐缺失标签并写入可恢复缓存。构建和验证分离，安装前自动备份。

**Tech Stack:** Python 3.13+、pytest、zipfile、pathlib、PowerShell、Houdini 22 Python API、Git。

## Global Constraints

- 源版本固定为 Houdini `22.0.368`。
- 官方节点帮助文件总数固定为 `5,034`。
- 不修改 Houdini 安装目录。
- 所有最终文件使用 UTF-8。
- 摘要格式固定为 `【<span style="color: #FFD700; font-weight: bold;">中文</span>】`。
- 任何构建或校验失败都不得覆盖当前发布包或用户帮助目录。
- 网络失败最多重试一次。
- 每个任务完成测试后单独提交。

---

### Task 1: 帮助 DSL 摘要解析与注入

**Files:**
- Create: `tools/__init__.py`
- Create: `tools/houdini_help.py`
- Create: `tests/test_houdini_help.py`

**Interfaces:**
- Produces: `inject_summaries(text: str, translate: Callable[[str, str | None], str]) -> tuple[str, int]`
- Produces: `strip_summaries(text: str) -> str`
- Produces: `iter_summary_anchors(text: str) -> Iterator[SummaryAnchor]`

- [ ] **Step 1: Write failing tests for label, `#id`, enum, preservation, and idempotence**

```python
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
        lambda label, desc: {"Density": "控制密度", "Low": "低密度"}[label],
    )
    assert count == 2
    assert "【<span style=\"color: #FFD700; font-weight: bold;\">控制密度</span>】" in output
    assert "【<span style=\"color: #FFD700; font-weight: bold;\">低密度</span>】" in output
    assert strip_summaries(output) == source


def test_injection_is_idempotent():
    source = "@parameters\nSize:\n    Controls size.\n"
    once, _ = inject_summaries(source, lambda label, desc: "控制尺寸")
    twice, count = inject_summaries(once, lambda label, desc: "控制尺寸")
    assert twice == once
    assert count == 0
```

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/test_houdini_help.py -v`

Expected: import failure because `tools.houdini_help` does not exist.

- [ ] **Step 3: Implement the minimal parser and injector**

Implement indentation-aware block detection, a marker regex shared by inject/strip, skip `NOTE`/`TIP`, and preserve all non-marker lines exactly.

- [ ] **Step 4: Run parser tests and the full test suite**

Run: `python -m pytest -v`

Expected: all parser tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tools/__init__.py tools/houdini_help.py tests/test_houdini_help.py
git commit -m "feat: parse and inject Houdini help summaries"
```

### Task 2: 翻译记忆与术语校正

**Files:**
- Create: `tools/translation_memory.py`
- Create: `data/glossary_zh.json`
- Create: `tests/test_translation_memory.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: summary marker format from Task 1.
- Produces: `TranslationMemory.load(path: Path) -> TranslationMemory`
- Produces: `TranslationMemory.translate(label: str, description: str | None) -> tuple[str, str]`
- Produces: `TranslationMemory.save(path: Path) -> None`

- [ ] **Step 1: Write failing tests**

```python
def test_glossary_overrides_machine_value(tmp_path):
    memory = TranslationMemory(glossary={"Density Scale": "密度缩放"})
    assert memory.translate("Density Scale", None)[0] == "密度缩放"


def test_cache_round_trip(tmp_path):
    path = tmp_path / "translations.json"
    memory = TranslationMemory()
    memory.add("Seed", "随机种子", source="manual")
    memory.save(path)
    assert TranslationMemory.load(path).translate("Seed", None)[0] == "随机种子"
```

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/test_translation_memory.py -v`

Expected: import failure because `TranslationMemory` does not exist.

- [ ] **Step 3: Implement load/save, glossary priority, and cache source tracking**

Use schema `{ "entries": { "label:seed": {"value": "...", "source": "..."}}, "version": 1 }`. Normalize lookup keys with Unicode NFKC and lowercase.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_translation_memory.py -v`

Expected: all translation memory tests pass.

- [ ] **Step 5: Commit**

```powershell
git add .gitignore tools/translation_memory.py data/glossary_zh.json tests/test_translation_memory.py
git commit -m "feat: add translation memory and Houdini glossary"
```

### Task 3: 旧包学习与网络翻译缓存

**Files:**
- Create: `tools/translate_missing.py`
- Create: `tests/test_translate_missing.py`
- Modify: `tools/translation_memory.py`

**Interfaces:**
- Produces: `learn_legacy_pack(pack: Path, memory: TranslationMemory) -> int`
- Produces: `translate_missing_labels(labels: Iterable[str], memory: TranslationMemory, batch_size: int = 60) -> TranslationStats`

- [ ] **Step 1: Write failing tests with a fake translator**

```python
def test_learning_preserves_old_summary(tmp_path):
    memory = TranslationMemory()
    count = learn_legacy_pack(FIXTURE_PACK, memory, translator=lambda values: values)
    assert count > 0
    assert memory.translate("Seed", None)[0]


def test_network_batches_cache_partial_progress():
    calls = []
    memory = TranslationMemory()
    stats = translate_missing_labels(
        ["Alpha", "Beta"],
        memory,
        batch_size=1,
        translator=lambda values: calls.append(values) or [f"译:{v}" for v in values],
    )
    assert len(calls) == 2
    assert stats.translated == 2
```

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/test_translate_missing.py -v`

Expected: import failure because the module does not exist.

- [ ] **Step 3: Implement old-pack learning, batching, one retry, and resumable cache**

Never spin indefinitely. A missing batch result raises `TranslationError` after one retry; the caller records the failure and uses the local fallback.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_translate_missing.py -v`

Expected: all learning and batching tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tools/translate_missing.py tools/translation_memory.py tests/test_translate_missing.py
git commit -m "feat: learn legacy translations and batch missing labels"
```

### Task 4: 全量构建和发布包校验

**Files:**
- Create: `tools/build_pack.py`
- Create: `tools/verify_pack.py`
- Create: `tests/test_build_and_verify.py`

**Interfaces:**
- Consumes: `inject_summaries` from Task 1 and `TranslationMemory` from Task 2.
- Produces: `build_pack(source_zip: Path, legacy_zip: Path, output_zip: Path, work_dir: Path) -> BuildStats`
- Produces: `verify_pack(source_zip: Path, output_zip: Path) -> VerificationReport`

- [ ] **Step 1: Write failing fixture integration test**

```python
def test_build_then_verify(tmp_path):
    stats = build_pack(FIXTURE_SOURCE_ZIP, FIXTURE_LEGACY_ZIP, tmp_path / "out.zip", tmp_path / "work")
    report = verify_pack(FIXTURE_SOURCE_ZIP, tmp_path / "out.zip")
    assert stats.files == 2
    assert report.ok
    assert report.missing_files == 0
    assert report.altered_source_files == 0
```

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/test_build_and_verify.py -v`

Expected: import failure because build and verify modules do not exist.

- [ ] **Step 3: Implement atomic build and verification**

Build into a temporary sibling, validate, then replace the destination ZIP. Check path sets, marker integrity, source equality after stripping, and `zipfile.testzip()`.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest -v`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tools/build_pack.py tools/verify_pack.py tests/test_build_and_verify.py
git commit -m "feat: build and verify complete Houdini help pack"
```

### Task 5: 生成真实发布包并人工抽查

**Files:**
- Modify: `Houdini_ZH_Tooltip_Pack.zip`
- Create: `data/translation_cache.json`
- Create: `reports/verification.json`

**Interfaces:**
- Consumes: all generator modules.
- Produces: verified 5,034-file release ZIP.

- [ ] **Step 1: Run the real build**

Run:

```powershell
python tools/build_pack.py `
  --source "C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help\nodes.zip" `
  --legacy "Houdini_ZH_Tooltip_Pack.zip" `
  --output "Houdini_ZH_Tooltip_Pack.zip" `
  --cache "data/translation_cache.json" `
  --report "reports/verification.json"
```

Expected: `5034/5034` source files present, zero altered source files.

- [ ] **Step 2: Inspect representative categories**

Check one file from each of SOP, DOP, POP, Pyro, LOP, USD MaterialX, APEX, VOP, COP and TOP. Each must show a gold Chinese summary before the original English description.

- [ ] **Step 3: Run full verification a second time**

Run: `python tools/verify_pack.py --source "<official nodes.zip>" --pack "Houdini_ZH_Tooltip_Pack.zip"`

Expected: exit code 0 and zero errors.

- [ ] **Step 4: Commit generated release artifacts**

```powershell
git add Houdini_ZH_Tooltip_Pack.zip data/translation_cache.json reports/verification.json
git commit -m "feat: release complete Houdini 22 Chinese tooltip pack"
```

### Task 6: 安装到 Houdini 用户目录

**Files:**
- Create: `tools/install_pack.ps1`
- Create: `tests/test_install_script.py`

**Interfaces:**
- Consumes: verified release ZIP.
- Produces: installed files plus timestamped backup path.

- [ ] **Step 1: Write failing install-script contract test**

```python
def test_install_script_mentions_backup_and_restore():
    text = Path("tools/install_pack.ps1").read_text(encoding="utf-8")
    assert "backup" in text.lower()
    assert "Restore-Item" in text
```

- [ ] **Step 2: Run and confirm RED**

Run: `python -m pytest tests/test_install_script.py -v`

Expected: file-not-found failure.

- [ ] **Step 3: Implement backup, copy, verify, and rollback**

Use one PowerShell shell end-to-end. Resolve and print source/target absolute paths before recursive copy or move. Never touch the installation directory.

- [ ] **Step 4: Install and verify**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/install_pack.ps1 `
  -PackZip "Houdini_ZH_Tooltip_Pack.zip" `
  -DestinationRoot "C:\Users\29211\Documents\houdini22.0"
```

Expected: `5034` files installed and backup path reported.

- [ ] **Step 5: Verify through Houdini MCP**

Use `code.execute_python` only for read-only `bookish.OverlayStore` checks. Confirm at least one POP, Pyro, LOP, and MaterialX parameter help includes the Chinese summary.

- [ ] **Step 6: Commit**

```powershell
git add tools/install_pack.ps1 tests/test_install_script.py
git commit -m "feat: safely install pack into Houdini user prefs"
```

### Task 7: 文档、版本与远端推送

**Files:**
- Modify: `README.md`
- Modify: `VERSION.txt`
- Modify: `简介.txt`
- Modify: `WORKLOG.md`

**Interfaces:**
- Consumes: final verification report.
- Produces: release notes and GitHub push.

- [ ] **Step 1: Update statistics and coverage**

Record `5,034` files, actual summary count, categories, installation backup path, and verification result. Replace outdated `3,127` claims.

- [ ] **Step 2: Run final checks**

Run:

```powershell
python -m pytest -v
python tools/verify_pack.py --source "<official nodes.zip>" --pack "Houdini_ZH_Tooltip_Pack.zip"
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 3: Commit release documentation**

```powershell
git add README.md VERSION.txt 简介.txt WORKLOG.md
git commit -m "docs: update full coverage statistics"
```

- [ ] **Step 4: Push**

Run:

```powershell
git push origin main
```

Expected: remote `main` advances to the final local commit.

- [ ] **Step 5: Verify remote**

Run: `git ls-remote origin refs/heads/main`

Expected: hash equals `git rev-parse HEAD`.
