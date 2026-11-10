# DSH ↔ Codex 交接契约（S3/S4/S5/S7/S8/S9/S10）

## 0. 模型与职责

在关键审核、生成和验收中沿用用户选定且环境支持的模型。用交接和项目记录保存实际模型。若未指定模型或推理强度，省略对应参数，使用 CLI 配置。

DSH负责用户确认与状态机；Codex只执行当前stage。S3/S5审核，S4生成，S7–S10为Blender；不能因发现描述只提Blender而丢失前段职责。

## 1. 调用与恢复

使用 [codex_run.ps1](../scripts/codex_run.ps1)，资源相对 `skillRoot`，产物相对 `projectRoot`。安装与selfcheck命令仅在源码仓库运行，安装包不承担自我重装。

```powershell
& "<skillRoot>/scripts/codex_run.ps1" -Workdir "<projectRoot>" -PromptFile "<prompt.md>" -OutFile "<last-message.md>" -Images "<required-image.png>" -TimeoutSec 600
```

独立进程运行，超时退出 124 并尝试清理进程树。清理失败时记录到对应的 launcher-error 日志。保留每attempt的stdout/stderr/last message及 `attempts[]`。统一成功条件：退出码0且本次last message存在且非空；最终退出码与summary.ok一致。列出的 `-Images` 任一缺失立即列出路径，不能静默丢图。

超时建议：S3/S5 600s，S4单图300s，S7 900s，S8/S9 1200s，S10 600s。默认最多3次尝试，只对启动即失败/模型列表刷新超时等**尚未执行任务且没有产物变化**的错误自动重试；任务已开始、超时或非零任务结果不得整任务重跑。恢复前校验已有产物sha256，锁定完成项，只补缺失。

## 2. 交接与结果契约

- 交接：[handoff.schema.json](../assets/templates/handoff.schema.json)，[完整示例](../assets/templates/examples/handoff.example.json)。含S5，明确projectRoot、skillRoot、输入哈希、指令文件、结果schema和超时。
- 结果：[codex-result.schema.json](../assets/templates/codex-result.schema.json)，[完整示例](../assets/templates/examples/codex-result.example.json)。stage为S3/S4/S5/S7/S8/S9/S10；status为ok/failed/blocked/partial；artifacts每项含path、sha256、bytes，另有checks、issues、notes。
- DSH必须核对文件存在、大小、sha256与门；不能信任自然语言“完成”。没有真实验证的check标unknown。

## 3. S3 提示词独立审核

**复用 [review.schema.json](../assets/templates/review.schema.json)**：每视角一份，target指向该视角；scores平铺为0–5数值，不返回嵌套scores。八份均通过才锁定。完整可校验示例见 [review.example.json](../assets/templates/examples/review.example.json)。

```json
{
  "reviewer": "codex",
  "target": "02-八视角提示词.v1.json#03_front",
  "stage": "S3",
  "verdict": "pass",
  "scores": {"identity": 5, "view": 5, "leftRight": 5, "volume": 4, "occlusion": 4, "completeness": 5, "background": 5, "executability": 5},
  "issues": [],
  "requiredChanges": [],
  "notes": "仅结构示例，不代表真实审核"
}
```

审核身份、相机/左右、遮挡、完整度、材质、背景、可执行性，并按 [10 §2.5](10-eight-view-prompts.md) 审核体积与正侧策略。不达标提出具体改动，禁止压缩六块prompt。

## 4. 阶段指令模板

### S4 八图生成

用途product-mockup，单张单一视角，禁止拼图。完整注入该视角六块prompt；体积段唯一来源为 [10 §2.5](10-eight-view-prompts.md)，交接构建时注入全文，规范间不复制。正侧先行、锁定后出其余视角；保留非对称姿态，失败校验已有文件后只补缺失。默认真alpha、1:1、同尺寸；Q15白底分支显式 `--alpha-mode white` 并记录。每图落盘后更新progress、路径、哈希。

### S5 图片审核

DSH与Codex独立使用review schema，明确 `stage: "S5"`；附同一批输入与校验报告，核对mode、视角、左右、体积、遮挡、一致性。用户确认八图后才准备混元额度确认。

### S7 导入与渲染

读GLB与project.json；只规范单位/尺度/落地/居中，**确认真实朝向后**按共用相机渲染8图；新版本保存blend与scene-info，不改造型。不能确认朝向则unknown，交DSH处理。

### S8/S9 修复

读renders、原图、issues；只做授权局部修复及基础水密，禁止布尔/重拓扑/改比例。`--stage repair`只输出新版本、重渲染、repair-report，不导出final；报告分开shapeAccepted与watertight。

### S10 导出

提供绑定最终blend哈希的用户G9记录，并显式 `--stage export --confirm-gate G9`。逐项打印检查；任何fail或关键unknown返回14，保留报告不产final。详见 [40](40-blender-mcp.md) 和 [60](60-printing.md)。

## 5. 失败、日志与长任务

启动类失败才自动尝试≤3次；任务失败/非JSON/缺文件留日志交DSH判断恢复点。Blender MCP断连可重连一次，额度/登录停下找用户，不重试消耗。日志与最后消息写 `1.Codex/03-会话日志`，记录耗时、模型、attempts及已有产物清单。

**DSH是唯一对用户播报方**，Codex写progress.json（阶段、完成数、产物、日志尾部、下一步、预计剩余）供DSH读。预计或实际后台>30分钟，从上次成功送达起每30分钟播报；重试/恢复不重置，以用户收到为准，完成后补最终播报并取消计时。前台连续任务不强制。可靠送达待长任务实测，不以日志mtime代送达。
