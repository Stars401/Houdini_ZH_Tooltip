# Houdini 参数提示中文总结包 / Houdini Chinese Parameter Tooltip Pack

[中文](#中文) | [English](#english)

---

## 中文

### 功能

为 Houdini 22.0 所有节点参数的悬停提示（tooltip）添加一行简短中文总结。

- 📦 覆盖 **3,127 个节点**，共 **39,528 条参数中文总结**
- 🎨 中文总结以金色加粗 `【中文概括】` 格式显示在英文提示开头
- ⚡ 无需运行时代码、无需 API 调用，纯文件替换
- 🔧 不修改 Houdini 原始安装文件
- ✅ 全部 3,127 个文件已通过自动校验，中文总结与参数一一对应

### 效果预览

鼠标悬停任意参数时，tooltip 开头会显示中文总结：

```
【创建有符号距离场(SDF)】
Creates a signed distance field (SDF).
An SDF stores the distance to the surface in each voxel.
...
```

### 安装方法

1. 下载 [Houdini_ZH_Tooltip_Pack.zip](./Houdini_ZH_Tooltip_Pack.zip) 或 clone 本仓库
2. 将 `help` 文件夹复制到你的 Houdini 用户偏好目录：
   - **Windows**: `%USERPROFILE%\Documents\houdini22.0\help\`
   - **Linux**: `~/houdini22.0/help/`
   - **macOS**: `~/Library/Preferences/houdini/22.0/help/`
3. 如果 `help` 文件夹已存在，直接合并覆盖
4. 重启 Houdini

### 卸载方法

删除用户偏好目录下的 `help\nodes\` 文件夹即可恢复原始英文提示。

### 技术原理

Houdini 的参数 tooltip 由 help 系统通过 `bookish.OverlayStore` 加载。用户偏好目录下的 `help/nodes/` 文件会自动覆盖安装目录中 `nodes.zip` 里的同名文件。本包在原始英文提示基础上，在每个参数描述的第一行插入了中文总结。

### 兼容性

- Houdini 22.0.x（22.0.368 测试通过）
- Windows / Linux / macOS
- 不影响 Houdini 任何功能

### 文件结构

```
仓库根目录/
├── README.md                          ← 本文件
├── Houdini_ZH_Tooltip_Pack.zip        ← 压缩分发包 (6.4 MB)
├── LICENSE                            ← MIT 开源协议
├── VERSION.txt                        ← 版本和统计信息
├── help/
│   └── nodes/                         ← 3,127 个 .txt 帮助文件
│       ├── sop/    (946+ files)      ← SOP 节点
│       ├── vop/    (473+ files)      ← VOP 节点
│       ├── dop/    (375+ files)      ← DOP 节点
│       ├── cop/    (357+ files)      ← COP 节点
│       ├── lop/    (166+ files)      ← LOP 节点
│       ├── top/    (117+ files)      ← TOP 节点
│       ├── chop/   (47+ files)       ← CHOP 节点
│       ├── obj/    (38+ files)       ← OBJ 节点
│       ├── out/    (37+ files)       ← OUT 节点
│       ├── shop/   (37+ files)      ← SHOP 节点
│       ├── cop2/   (19+ files)      ← COP2 节点
│       ├── manager/ (6 files)       ← 管理器节点
│       └── ...
```

---

## English

### Features

Adds a concise Chinese summary line to the tooltip of every parameter in Houdini 22.0.

- 📦 Covers **3,127 nodes** with **39,528 Chinese parameter summaries**
- 🎨 Summaries displayed as gold bold text `【Chinese summary】` at the start of each tooltip
- ⚡ No runtime code, no API calls — pure file replacement
- 🔧 Does not modify Houdini's original installation files
- ✅ All 3,127 files verified — Chinese summaries correctly aligned with parameters

### Installation

1. Download [Houdini_ZH_Tooltip_Pack.zip](./Houdini_ZH_Tooltip_Pack.zip) or clone this repo
2. Copy the `help` folder to your Houdini user preferences directory:
   - **Windows**: `%USERPROFILE%\Documents\houdini22.0\help\`
   - **Linux**: `~/houdini22.0/help/`
   - **macOS**: `~/Library/Preferences/houdini/22.0/help/`
3. Merge if `help` folder already exists
4. Restart Houdini

### Uninstall

Delete the `help\nodes\` folder from your user preferences directory.

### How It Works

Houdini's parameter tooltips are loaded from help files via `bookish.OverlayStore`. Files in the user preferences `help/nodes/` directory automatically overlay the `nodes.zip` in the installation directory. This pack inserts a Chinese summary as the first line of each parameter's description block.

### Compatibility

- Houdini 22.0.x (tested on 22.0.368)
- Windows / Linux / macOS
- Does not affect any Houdini functionality

### License

MIT License — Free to use and distribute. Chinese summaries are AI-generated based on parameter labels and English descriptions.
