# Houdini 中文参数提示全量补全设计

## 目标

为 Houdini 22.0.368 官方帮助库中的全部 5,034 个节点帮助文件补全中文参数摘要，修复现有 3,127 个已覆盖文件中的遗漏，安装到本机 Houdini 用户偏好目录，并推送更新后的发布包到 GitHub。

## 数据来源

- 官方英文帮助：`C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help\nodes.zip`
- 既有中文包：仓库根目录 `Houdini_ZH_Tooltip_Pack.zip`
- Houdini 用户目录：`C:\Users\29211\Documents\houdini22.0\help\nodes`
- SideFX 官方节点文档用于术语核对：`https://www.sidefx.com/docs/houdini/nodes/index.html`

## 覆盖定义

1. 输出必须包含官方 `nodes.zip` 中的所有普通文件，路径集合完全一致。
2. `@parameters` 区域内的每个参数和枚举选项必须恰有一个中文摘要。
3. 已有翻译优先复用；新翻译使用统一技术词汇表校正。
4. 移除所有中文摘要行后，文件内容必须与官方英文帮助逐字一致。
5. 不修改 Houdini 安装目录，只覆盖用户偏好目录中的帮助文件。

## 架构

### `tools/houdini_help.py`

负责解析帮助 DSL、定位参数块、提取已有摘要、注入摘要。该模块不访问网络，也不写磁盘，便于单元测试。

主要接口：

```python
def inject_summaries(text: str, translate: Callable[[str, str | None], str]) -> tuple[str, int]
def strip_summaries(text: str) -> str
def iter_summary_anchors(text: str) -> Iterator[SummaryAnchor]
```

### `tools/translation_memory.py`

负责从旧发布包学习“英文标签/描述到中文摘要”的映射，加载术语表，保护代码标记，调用网络翻译并缓存结果。

主要接口：

```python
class TranslationMemory:
    def translate(self, label: str, description: str | None) -> tuple[str, str]
    def save(self, path: Path) -> None
    @classmethod
    def load(cls, path: Path) -> "TranslationMemory"
```

缓存键和来源分开保存，避免把网络结果误认为人工术语。网络请求失败最多重试一次，再使用已有短语规则生成非空摘要并记录待复核项。

### `tools/build_pack.py`

负责读取官方 `nodes.zip`，逐文件注入摘要，写入暂存目录，并与旧包、术语表合并翻译记忆。构建失败时不覆盖发布包。

主要接口：

```python
def build_pack(source_zip: Path, legacy_zip: Path, output_zip: Path, work_dir: Path) -> BuildStats
```

### `tools/verify_pack.py`

独立验证发布包：

- 路径集合与官方 `nodes.zip` 一致。
- 每个文件移除摘要后与原文件 md5 一致。
- 摘要标记成对、非空、无重复。
- `@parameters` 参数锚点覆盖率为 100%。
- ZIP 可完整读取，无损坏条目。

### `tools/install_pack.ps1`

安装前把现有用户帮助目录移动到带时间戳的备份目录，再复制新文件。复制后再次运行结构校验；失败时恢复备份。

## 翻译策略

- 优先使用旧包中同标签、同描述的既有中文。
- 缺失标签按批发送到网络翻译服务，批次之间保存缓存，支持断点续跑。
- 对 Houdini 专有名词应用固定术语表，例如 `SOP`、`DOP`、`LOP`、`VOP`、`POP`、`RBD`、`FLIP`、`VDB`、`USD`、`MaterialX`、`APEX`、`KineFX`、`PDG`。
- 纯变量名、通道名、表达式和代码片段不强行汉化，摘要保留原始标记并补充用途。
- 旧翻译与自动翻译冲突时，人工术语表优先，其次是旧包，最后是网络结果。

## 错误处理

- 官方 ZIP 或旧包缺失时终止，不生成半成品。
- 单个文件解析异常时记录相对路径并继续统计，最终有异常则阻止发布。
- 网络翻译批次失败最多重试一次；仍失败时使用本地回退并列入复核报告。
- 安装校验失败时自动恢复备份。
- 推送前必须完成测试、包校验和安装校验。

## 测试

- 解析器覆盖标签、`#id`、`#channels`、枚举选项、重复执行、代码标记。
- 翻译记忆覆盖旧包学习、缓存恢复、术语优先和网络失败回退。
- 构建器覆盖官方文件缺失、路径差异、UTF-8 BOM 和空文件。
- 验证器覆盖摘要缺失、摘要重复、标记损坏和正文篡改。
- 集成测试用小型 fixture 构建 ZIP，再执行完整校验。
- 最终对 5,034 个真实文件执行全量构建和 Houdini overlay 读取验证。

## 交付

- 更新后的 `Houdini_ZH_Tooltip_Pack.zip`
- 更新后的 `README.md`、`VERSION.txt`
- 可复现生成器、测试和翻译缓存
- 安装前备份路径
- 校验报告
- GitHub `origin/main` 推送结果
