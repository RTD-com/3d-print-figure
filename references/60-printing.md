# 打印检查与 STL 导出（S10）

> 默认规格（Q11）：树脂打印、目标高度 15 cm、最小壁厚 ≥1.0 mm、单件、不抽壳、不自动分件。
> 用户有其它要求（尺寸/材料/分件/抽壳）→ 导出前必须问。

## 1. 导出前检查（全过才导出）

使用 [blender_repair_export.py](../scripts/blender_repair_export.py) 的 `--stage export --confirm-gate G9 --confirmation-file <记录>`；repair阶段不导出STL。G9记录包含confirmedAt、gate=G9、shapeAccepted=true和最终blendSha256。造型门shapeAccepted与水密门watertight分开。以下项目逐项输出pass|fail|unknown；任一fail或关键unknown不导出final STL（exit14）。不能用示例的绿色对勾冒充实测。
| 检查 | 工具/方法 | 合格 |
|---|---|---|
| 水密 | 3D Print Toolbox `Check All` / bpy 自检 | 边界边 0、非流形 0 |
| 自交 | 3D Print Toolbox Intersections | 0；可靠测量缺失时unknown并阻断 |
| 退化面 | `mesh.validate()` / 面积≈0 | 0 |
| 重复顶点 | `remove_doubles` | 已合并 |
| 法线 | 实际绕向/体积方向校验；不能只凭运行修复算子 | 有证据朝外；无法证明则unknown |
| 体积 | `bmesh.calc_volume` / 3D Print Toolbox | > 0 |
| 包围盒 | bbox | 高 = 150 ±0.5 mm；宽/厚合理 |
| 姿态 | 检查 | 底面 Z=0；重心投影在支撑范围内 |
| 壁厚 | 3D Print Toolbox Thickness（若可用） | ≥1.0 mm |
| 面数 | 统计 | 记录；必要时减面 |

## 2. 减面（Q13）
- 先导出高面数备份到 `4.9归档`（可选），再减面。
- 方式优先级：Decimate(Collapse, ratio 0.6–0.2) → Planar → Remesh（保形差，慎用）。
- 目标：常见切片软件能打开、细节仍可辨；一般 30–80 万三角面内。
- 记录：减面前后面数、ratio、文件大小、视觉对比图（渲染 8 视角各一张）。

## 3. 导出

通过本页第 1 节的检查后，使用 [Blender 导出命令](40-blender-mcp.md#4-最终导出s10)。自交和薄壁默认是 `unknown`。用 `--checks-file <测量记录.json>` 提供实测时，顶层 `blendSha256` 须绑定最终 blend。

- `checks.selfIntersection` 与 `checks.thinWalls` 各包含 `method`、`measured`、`threshold`、`unit` 及 `evidence`。
- `evidence` 包含实测文件的 `path` 与 `sha256`。相对路径以测量记录所在目录为基准。
- 自交以 `count` 计量，测量值和阈值均为 0。薄壁以 `mm` 计量，测量值须达到阈值，阈值须达到本次打印要求。
- 检查缺失或失败时，交付检查报告并保留 STL 导出门。

## 4. 打印说明模板
```markdown
# 打印说明
- 项目：<名称>｜版本：<版本目录>｜日期：<日期>
- 文件：<项目名>_final.stl（sha256: ...）
- 尺寸：高 150 mm × 宽 ... × 厚 ...
- 面数：...（减面比例 ...）
- 检查：水密 <pass/fail/unknown>；非流形 <实测>；自交 <实测或unknown>；壁厚 <实测或unknown>
- 建议：树脂；层高 0.05 mm；需支撑（是/否）；建议朝向：...
- 已知限制：...
```

## 5. 分件与抽壳（默认不做）
- 触发条件：用户要求；或模型某方向尺寸超出打印机成型空间；或 hollow 需求。
- 分件：按部件切分（`bpy.ops.mesh.bisect`/boolean），加定位榫；分件清单写 `5.打印/分件清单.json`。
- 抽壳：Solidify 厚度 ≥1.5 mm（树脂），打排液孔 ≥2 mm；抽壳后必须重新水密检查。
- 任何分件/抽壳都必须先问用户，并单独做打印检查。

## 6. 失败处理
| 问题 | 方案 |
|---|---|
| STL 切片器打不开/卡死 | 减面；检查是否有超大坐标/NaN；拆件 |
| 非水密修不好 | 报告位置（截图+坐标）；用户决定加厚/简化 |
| 薄壁/断件 | 加厚或加支撑结构；先给用户看渲染 |
| 尺寸偏差 | 重新按 bbox 缩放；确认导出时 global_scale=1.0 |

本版不凭静态统计宣称可靠自交/薄壁通过；缺少与最终blend绑定的实际测量证据时必须停止，后续由真实Blender/Toolbox/切片验证补足。
