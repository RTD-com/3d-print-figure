---
name: 3d-print-blender
description: 接收 3D 打印手办的 DSH 阶段交接，执行提示词与图片审核、八视角生成、GLB 导入渲染、局部修复与经确认的 STL 导出。
---

# 3D 打印手办执行

> 版本 1.0.0。先读[交接契约](references/20-codex-handoff.md)和项目的 `2.DSH/project.json`。按交接中的 `skillRoot` 解析资源，按 `projectRoot` 写入产物。DSH 负责用户决策和确认记录。

## 阶段

| 阶段 | 执行与输出 |
| --- | --- |
| S3/S5 提示词与图片审核 | 对指定输入独立审核，按[审核规范](references/50-review-rubric.md)写 JSON 到 `1.Codex`。 |
| S4 生成八图 | 按[八视角规范](references/10-eight-view-prompts.md)先核对正侧体块，再生成其余视角。只写授权的 `3.图片/vN` 与 `1.Codex`，恢复时核对哈希。 |
| S7 导入和渲染 | 在专用 Blender 场景或独立后台进程中导入 GLB，核对朝向、毫米高度、居中及落地。保存新版本 Blend、网格统计、八视角与接触表。 |
| S8/S9 修复 | 依据问题清单做局部修补。用同视角纯色与材质渲染区分网格和贴图问题，保护邻近细节和 UV。另存 Blend、GLB、渲染和报告。 |
| S10 导出 | 核对最终 Blend 的 G9 用户授权及打印检查。使用[导出步骤](references/60-printing.md)，检查失败或缺失时返回报告。 |

## Blender 检查

- 通过 `<BlenderExe>`、`BLENDER_EXE` 或 PATH 定位。用 MCP 时先探测连接状态，共享会话需用户同意后才重启。
- 修复只写 `1.Codex` 与 `4.模型文件`，以新版本交付并对照复核。具体命令与[局部修复复核](references/40-blender-mcp.md#局部修复复核)见 Blender 指引。
- 分别记录造型与打印检查。自交、薄壁证据须绑定最终 Blend。最终 STL 写 `5.打印`，并核对重导入尺寸和网格。

## 返回结果

使用[结果契约](assets/templates/codex-result.schema.json)写明阶段、状态、产物路径、字节数、哈希、检查项和问题。未实测项记 `unknown`。将阶段进度与下步写入 `progress.json`，由 DSH 向用户汇报。
