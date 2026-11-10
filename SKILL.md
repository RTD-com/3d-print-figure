---
name: 3d-print-figure
description: 用户提供角色或手办参考图并要求生成可 3D 打印的模型或 STL 时使用。通过 DSH 编排需求、八视角、混元 3D、Blender 修复和打印验收。
---

# 3D 打印手办编排

> 版本 1.0.0。用 `skillRoot` 定位随包脚本和契约，用 `projectRoot` 定位用户项目。按当前阶段读取[工作流](references/00-workflow.md)。

## 执行要求

- 先确认用户同意将指定图片交给 Codex 和混元处理。已知 IP 需说明用途和使用范围。
- 需求卡、八图、初版模型与最终 STL 由用户验收。混元提交另需单次额度确认，导出另需绑定最终 Blend 的 G9 记录。
- 角色左右以角色自身为准。生成八个正交视角前，按[八视角规范](references/10-eight-view-prompts.md)编写完整提示词，先用正侧图锁定立体感。
- 用本机 Edge 或 Chrome 专用配置执行混元步骤。用户负责登录。先 dry-run 回读八槽、配置和余额，获准后才提交。网页或账号不可用时由用户提供 GLB，记录 `manualFallback=true`。
- 默认 150 mm 高、树脂、最小壁厚 1.0 mm。修复最多三轮，每轮另存，第一轮限局部缺陷及基础水密。拓扑大改、分件或抽壳先确认范围。
- 交接使用用户环境可用并已选定的模型。关键审核和验收出现模型不可用或证据缺失时，报告阻塞并保留待复核状态。
- 按阶段更新 `2.DSH/project.json`。恢复时核对文件哈希并只补缺失。长任务的汇报以[工作流](references/00-workflow.md#恢复与排错)为准。

## 阶段入口

| 阶段 | 使用资源 |
| --- | --- |
| S0 预检与初始化 | `scripts/preflight.ps1`、`scripts/init_project.ps1` |
| S1–S5 需求、提示词、八图与审核 | [八视角规范](references/10-eight-view-prompts.md)、[Codex 交接](references/20-codex-handoff.md)、[审核规范](references/50-review-rubric.md) |
| S6 混元 GLB | [网页与确认协议](references/30-hunyuan-web.md) |
| S7–S9 导入、修复、验收 | [Blender 操作](references/40-blender-mcp.md)、[审核规范](references/50-review-rubric.md) |
| S10–S11 导出与交付 | [打印检查](references/60-printing.md)、`scripts/package_artifacts.py` |

发生异常时按[排错说明](references/70-troubleshooting.md)保留现场。额度、任务身份或打印证据不明确时暂停对应步骤。
