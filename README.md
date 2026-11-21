# Houdini 参数提示中文总结包

## 中文

### 功能

为 Houdini 22.0.368 的全部官方节点帮助文件添加参数、输入、输出和局部变量中文摘要。

- 覆盖 **5,034 个官方帮助文件**
- 插入 **58,581 条中文摘要**
- 其中 **58,470 条包含中文文本**
- 其余 **111 条**保留 `SOP`、`SDF`、`VDB`、`USD`、`BSDF` 和单字母变量等技术记号
- 覆盖 APEX、POP、Pyro、DOP、Stage/LOP、USD、MaterialX、VOP、COP、TOP 等内部节点
- 不修改 Houdini 安装目录
- 不包含运行时插件或后台进程

### 效果

参数提示开头会显示金色中文摘要，原文继续保留：

```text
【用于源设置的体积】
Provides the sources for the Pyro simulation. This should be a set of named volumes.
```

### 安装

手动安装：

1. 完全关闭 Houdini
2. 解压 `Houdini_ZH_Tooltip_Pack.zip`
3. 将压缩包内的 `help` 目录合并到用户偏好目录
   - Windows: `%USERPROFILE%\Documents\houdini22.0\`
   - Linux: `~/houdini22.0/`
   - macOS: `~/Library/Preferences/houdini/22.0/`
4. 重新启动 Houdini

Windows 推荐使用带备份和回滚的安装脚本：

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/install_pack.ps1 `
  -PackZip Houdini_ZH_Tooltip_Pack.zip `
  -DestinationRoot "$env:USERPROFILE\Documents\houdini22.0"
```

脚本会先把现有 `help\nodes` 移动到带时间戳的 `backups` 目录，再安装并校验 5,034 个文件。
脚本检测到 Houdini 正在运行时会直接拒绝安装，避免帮助缓存保留“找不到帮助”的旧状态。

### 卸载与恢复

- 没有备份时：删除用户偏好目录中的 `help\nodes`
- 使用安装脚本时：把 `backups\help_nodes_<时间戳>` 移回 `help\nodes`

### 校验结果

发布包已按 Houdini 22.0.368 官方 `help/nodes.zip` 全量验证：

- 文件集合：5,034/5,034
- 缺失文件：0
- 多余文件：0
- 原文被篡改文件：0
- 损坏摘要标记文件：0
- 摘要总数：58,581

详细报告见 `reports/verification.json`。

### 技术原理

Houdini 通过 help overlay 先查找用户偏好目录，再回退到安装目录的 `nodes.zip`。本包只覆盖用户目录中的同名帮助文件，并在参数块中插入独立的中文摘要行。

`tools/verify_pack.py` 会移除摘要行并与官方英文帮助逐字比较，确保除新增摘要外没有改动原文。

### 覆盖目录

```text
vop        1212
sop        1203
apex        613
dop         592
cop         375
lop         198
shop        162
top         158
cop2        150
chop        137
obj          98
out          57
其他         79
```

### 可复现构建

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -v

python -m tools.build_pack `
  --source "C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help\nodes.zip" `
  --legacy Houdini_ZH_Tooltip_Pack.zip `
  --output build\Houdini_ZH_Tooltip_Pack.zip `
  --cache data\translation_cache.json `
  --report reports\verification.json
```

生成器优先复用旧包翻译，再按英文描述上下文补译，最后使用 `data/glossary_zh.json` 统一 Houdini 术语。

### 兼容性

- Houdini 22.0.x
- 已在 Houdini 22.0.368 验证
- Windows / Linux / macOS

### 许可

MIT License。中文摘要由旧翻译、上下文翻译和人工术语表共同生成。

---

## English

### Features

Adds Chinese summaries to parameter, input, output, and local-variable tooltips across all Houdini 22.0.368 node help files.

- **5,034** official help files covered
- **58,581** summary lines inserted
- **58,470** summaries contain Chinese text
- The remaining **111** entries intentionally preserve technical tokens such as `SOP`, `SDF`, `VDB`, `USD`, `BSDF`, and single-letter variables
- Includes APEX, POP, Pyro, DOP, Stage/LOP, USD, MaterialX, VOP, COP, and TOP content
- Does not modify the Houdini installation
- No runtime plugin or background process

### Installation

1. Close Houdini completely
2. Extract `Houdini_ZH_Tooltip_Pack.zip`
3. Merge its `help` directory into your Houdini user preferences directory
4. Start Houdini again

On Windows, use the safe installer:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File tools/install_pack.ps1 `
  -PackZip Houdini_ZH_Tooltip_Pack.zip `
  -DestinationRoot "$env:USERPROFILE\Documents\houdini22.0"
```

The installer moves the current `help\nodes` directory into a timestamped backup before copying the new pack.

### Verification

- File set: 5,034/5,034
- Missing files: 0
- Extra files: 0
- Source-text changes after stripping summaries: 0
- Invalid summary markers: 0
- Total summaries: 58,581

See `reports/verification.json` for the machine-readable report.

### Reproducible Build

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -v
python -m tools.build_pack --source "<official nodes.zip>" --legacy Houdini_ZH_Tooltip_Pack.zip --output build\Houdini_ZH_Tooltip_Pack.zip --cache data\translation_cache.json
```

### License

MIT License. Chinese summaries are assembled from legacy translations, context-aware translations, and a curated Houdini glossary.
