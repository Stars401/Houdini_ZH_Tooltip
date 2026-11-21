# WORKLOG

## 2026-11-20

- [x] 拉取 `Stars401/Houdini_ZH_Tooltip`，确认远端为 `origin/main`。
- [x] 核对本机 Houdini 22.0.368 与 MCP 连接；当前场景可查询。
- [x] 对比官方 `nodes.zip` 和现有发布包：官方 5,034 文件，现有 3,127 文件，缺 1,907 文件。
- [x] 定位主要缺口：vop 714、apex 613、dop 150、shop 118、sop 98、obj 46、lop 31、top 26。
- [x] 用户确认采用方案 1：全覆盖、统一术语、网络翻译加人工规则复核。
- [x] 完成设计、测试和生成器；`47 passed`。
- [x] 生成 5,034 文件发布包；58,581 条摘要，结构校验 0 错误。
- [x] 独立验证发布包；缺失 0、额外 0、原文篡改 0、标记损坏 0。证据：`reports/verification.json`。
- [x] 备份并安装到 Houdini 用户偏好目录；安装文件 5,034。
- [x] 备份目录：`C:\Users\29211\Documents\houdini22.0\backups\help_nodes_20261120_232058`。
- [x] 通过 Houdini MCP `HoudiniPathStore` 验证 overlay 读取 POP、Pyro、APEX、LOP/USD、MaterialX 和 DOP 文件。
- [x] 更新版本说明并推送 `origin/main`；发布基线提交 `885c616`。

## 2026-11-21

- [x] 复现用户反馈的 `Start Frame` tooltip 缺失；`manager/dopnet` 与 `obj/dopnet` 均包含正确中文内容。
- [x] 用 `houdinihelp.api.getParmTooltipFromPath()` 验证文件和运行中 Houdini 都返回正确 DOP Network tooltip。
- [x] 根因：Houdini 运行期间热替换 `help/nodes`，UI 帮助缓存保留了安装时的失败状态。
- [x] 清空运行中 Houdini 的 help `PageCache`，验证重新读取后内容正确。
- [x] 安装器增加运行进程检测，Houdini 未关闭时拒绝安装。
- [x] README 明确要求安装前完全关闭 Houdini。
- [x] 回归测试：48 passed。
