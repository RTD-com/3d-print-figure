# 审核规范（S5/S8/S9）

## 0. 原则
- 每个对象至少两份独立审核：DSH 与 Codex；结论必须落到结构 JSON，不接受纯自然语言“看起来不错”。
- 严重度：`blocker`（必须修，门不过）/ `major`（应修，可带条件通过）/ `minor`（记录，不阻塞）。
- 冲突：一致项自动执行；分歧项按 blocker > major > minor 排序，blocker 交用户裁决；用户不在则暂停。
- **质量门与打印门分离**：`shapeAccepted`（造型/体积/非对称/用户验收）与 `watertight`（水密/尺寸/STL）分别记录；水密通过不等于造型通过。

## 1. 八视角图片（S5）
每张 0–5 分，≥4 且无 blocker 才通过。

| 维度 | 合格标准 | 方法 |
|---|---|---|
| identity | 与母版同一角色（脸/眼/发型/肤色/头身比） | 并排目检 + Codex 复核 |
| view | 角度/投影与视角表一致；八图统一正交 |
| leftRight | 按每视角映射（front 画面左=角色右；back 画面右=角色右；侧视近侧=对应侧）；不是一刀切 |
| asymmetry | 举手/叉腰等非对称姿态保留，不强求左右对称 |
| occlusion | 近/远侧遮挡与物理一致 | 对照「本视角」段 |
| completeness | 无缺失/多余部件、无第二角色 | 逐项清点 |
| material | 材质/配色与需求卡一致（hex） | 目检 + 色值 |
| **volume** | **3D 手办体积感：前后径/侧壁厚度/圆润度达标；无纸片感/扁平剪影；2D 角色也应按圆滚体块呈现** | 侧视/45°/顶底对照 |
| **topBottomOrtho** | **顶/底图必须正交平行投影，无透视收缩；鞋底/轮廓平行** | 对照几何常识 |
| background | 默认transparent真alpha；Q15显式white白底；均无文字/边框 | PIL alpha 统计 + 目检 |
| size | 8 张同分辨率、主体占比接近 | 脚本 |

程序校验：`validate_views.py`（8/8、尺寸一致、透明像素占比、PNG CRC、sha256）→ `校验报告.json`。

## 2. 3D 模型（S8/S9）
对照 8 张渲染 vs 8 张原视角图 + 需求卡。

| 维度 | 合格标准 |
|---|---|
| silhouette | 正/侧/背/顶/底轮廓与图片一致 |
| completeness | 无漂浮碎块、无大孔洞、无缺失配件；凸起/凹陷异常已修 |
| leftRight | 配件位置/数量正确，无镜像 |
| proportion | 头身比/宽厚比与需求卡一致；**按 [10 §2.5](10-eight-view-prompts.md) 从模型分部 bbox 量测 D/W 并记录** |
| surface | 无非预期破面、法线问题、z-fighting |
| volume | 3D 打印手办应有的圆滚体积；不能是扁平立牌/纸片；侧面有真实厚度 |
| shapeAccepted | 用户/DSH/Codex 对造型与体积的独立验收，不得用 printability 代替 |
| printability | 可水密化、薄壁可控、包围盒正确 |

## 3. STL（S10）
| 检查 | 标准 |
|---|---|
| watertight | 边界边=0；非流形边=0 |
| selfIntersect | 0且有可靠测量；未测为unknown，阻断导出 |
| units/scale | mm；高度 150 ±0.5 mm |
| pose | 底面 Z=0、重心稳定、朝向合理 |
| wall | ≥1.0 mm（树脂） |
| faces | 记录；减面比例记录 |

## 4. 审核 JSON 结构

```json
{
  "reviewer": "codex",
  "target": "3.图片/v1/03_front.png",
  "stage": "S5",
  "verdict": "fail",
  "scores": {"identity":4,"view":5,"leftRight":3,"volume":4,"topBottomOrtho":4,"occlusion":4,"completeness":4,"material":4,"background":5,"size":5},
  "issues": [
    {"id":"I-001","severity":"blocker","location":"角色右胸翻襟","problem":"画面左右反了",
     "expected":"翻襟应在画面左侧","evidence":"01_top 与 03_front 对比","suggestedFix":"..."}
  ],
  "requiredChanges": ["..."],
  "notes": "..."
}
```

## 5. 审核流程
1. DSH 先出 `image-review-dsh.json` / `model-review-dsh.json`。
2. Codex 附相同输入出 `*-codex.json`（同一 schema）。
3. DSH 聚合：
   - 双方都 pass → 门通过；
   - 有 blocker → 修复/重生成后复审（≤2 轮图片 / ≤3 轮模型）；
   - 仅 major → 记录并继续（用户可见摘要）；
   - 分歧 → 用户裁决（附双方证据）。
4. 输出 `2.DSH/05-决策记录/review-merged-<stage>.json`。

## 6. 用户确认摘要模板（确认点②③）
```
【项目】<名称>｜【阶段】8 图 / 初版模型
【结果】通过 x/8；blocker 0；major n；minor m
【需你看】contact-sheet.png + 关键视角 03/05/07/08
【已知取舍】...
【下一步】准备混元额度确认（以页面本次实测口径为准）/ 进入 STL 导出
【请回复】「可以继续」或「问题：部位+视角+期望」
```

## 7. 复审触发条件
- 图片：任一 blocker；或 identity/leftRight ≤3；或透明/尺寸校验失败。
- 模型：任一 blocker；或完整度/轮廓明显退化；或用户提出具体问题。
- STL：水密/尺寸/壁厚任一失败；或减面后细节丢失超出用户接受范围。

S3逐视角审核也复用 [review.schema.json](../assets/templates/review.schema.json)，scores为平铺数值，完整示例见 [review.example.json](../assets/templates/examples/review.example.json)。水密与shapeAccepted分开，unknown不视为pass。
