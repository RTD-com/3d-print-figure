# 3D 打印手办

从参考图出发，生成八视角、构建 GLB，在 Blender 中按版本审查和修复。用户确认造型且打印检查通过后，导出 STL。

[English](README.md) · [更新日志](CHANGELOG.md) · [许可证](LICENSE)

| 技能 | 职责 | 项目级安装位置 |
| --- | --- | --- |
| [3d-print-figure](SKILL.md) | DSH 编排需求、审核、混元生成和用户确认。 | `.dsh/skills/3d-print-figure/` |
| [3d-print-blender](codex-skill/SKILL.md) | Codex 审查提示词和图片、生成视角、执行 Blender 阶段。 | `.agents/skills/3d-print-blender/` |

## 安装 v1.0.0

准备 Windows 10 或 11、Windows PowerShell 5.1、Git、Python 与 Pillow，以及 Node.js 22 或更新版本。全流程还需要支持 Agent Skills 的 DSH、带图像生成能力的 Codex CLI、Blender 5.x、Edge 或 Chrome，以及混元 3D 网页账号。Blender 可在独立后台进程运行，也可连接已配置的 Blender MCP。

```powershell
git clone --branch v1.0.0 --single-branch https://github.com/RTD-com/3d-print-figure.git
Set-Location 3d-print-figure
$workdir = "<你的工作目录>"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install.ps1 -ProjectRoot $workdir
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/preflight.ps1 -Workdir $workdir
```

从 Git 检出目录运行安装命令。脚本按清单生成两个独立安装包，记录源提交与文件哈希。已有安装时，使用 `-Update` 显式升级。若希望安装到用户目录，改用 `-Scope user`，随后在两端确认技能可加载。

## 开始一个项目

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/init_project.ps1 -Workdir $workdir -Name "示例手办" -ImagePath "<参考图路径>"
```

在工作目录打开 DSH，指定 `3d-print-figure` 和新建项目。各阶段输入、产物和恢复规则见[工作流](references/00-workflow.md)。

1. 确认需求卡、参考图和目标尺寸。
2. 审查八张正交视角图。先校对正视与侧视的体积和比例，再补齐其余视角。
3. 核对混元的上传预览，单独确认生成额度。已有 GLB 或采用手动生成时，从 [Blender 阶段](references/40-blender-mcp.md)继续。
4. 查看初版与每轮修复的对比图。导出授权绑定最终 Blender 文件的哈希。
5. 检查 STL 和[打印报告](references/60-printing.md)。自交与最小壁厚需要实测证据。

项目建在工作目录下的 `手办/`。将项目和浏览器诊断记录留在私有目录。取得授权后才向 Codex 或混元发送参考图。日志、签名链接和浏览器配置的处理方式见[安全说明](SECURITY.md)。

## 验证范围

[验证范围](docs/validation-matrix.md)区分了离线检查与仍需实测的网页生成、Blender 全链路、切片和实物打印。v1.0.0 是两项技能与配套工具的首次公开版本。

参与维护请读[贡献指南](CONTRIBUTING.md)。源码和技能说明采用 [MIT 许可证](LICENSE)。
