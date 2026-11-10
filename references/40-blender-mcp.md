# Blender + mcp-for-blender 操作手册（S7–S10）

## 0. 前置与资源定位

- `skillRoot` 为当前安装包根；`projectRoot` 为手办项目根。脚本从 `skillRoot/scripts` 解析，产物只写 `1.Codex`、`4.模型文件`、`5.打印`。
- 通过 `<BlenderExe>`、`BLENDER_EXE` 或 PATH 定位 Blender；MCP 模式需用户启动 Blender 与插件，端口默认9876，并用 `get_addon_status` 确认。
- MCP 工具包括 `execute_blender_code`、`look`、`get_scene_info`。离线仓库检查不调用这些工具。


## 1. 导入和八视角渲染（S7）

使用 [blender_render_views.py](../scripts/blender_render_views.py)：导入GLB，目标高度缩放、XY居中、底面Z=0，输出新版本 `.blend`、`scene-info.json` 和 `renders/`。默认禁止覆盖；重做应选新版本目录，只有显式 `--force` 可覆盖。

```powershell
& "<BlenderExe>" --background --python "<skillRoot>/scripts/blender_render_views.py" -- --glb "<input.glb>" --out-dir "<projectRoot>/4.模型文件/4.1初版" --height-mm "<目标高度mm>" --res 1600
```

GLB没有可靠的角色朝向元数据。必须确认正面为-Y、角色左为+X、上为+Z；未确认时 `orientation=unknown`，不能仅凭居中缩放放过G7。体积与比例量测规则只引用 [10 §2.5](10-eight-view-prompts.md)。

## 2. 相机与画面坐标

权威纯数学实现为 [camera_math.py](../scripts/lib/camera_math.py)，两Blender脚本共用；非对称点集离线测试验证投影。下表相对模型中心，全部正交；侧面/45°不增加无依据俯角。

| 视角 | 相机方向 | 画面右 | 画面上 |
|---|---|---|---|
| top | (0,0,+1) | +X | +Y |
| left45 | (+1,-1,0) | +X +Y | +Z |
| front | (0,-1,0) | +X | +Z |
| right45 | (-1,-1,0) | +X -Y | +Z |
| left | (+1,0,0) | +Y | +Z |
| right | (-1,0,0) | -Y | +Z |
| back | (0,+1,0) | -X | +Z |
| bottom | (0,0,-1) | +X | -Y |

front画面左是角色右，back反向；顶底的画面上方向不同。左右槽位仍需真实网页逐槽核对，不能把front口头换算套到所有视角。

共同渲染设置从 `bpy.types.RenderSettings.bl_rna` 实际engine枚举选 `BLENDER_EEVEE` 或 `BLENDER_EEVEE_NEXT`；无可用值明确失败。默认Workbench，透明背景、统一尺度、1600×1600；灯光/色彩须真实渲染复核。拼图使用 [build_contact_sheet.py](../scripts/build_contact_sheet.py)，固定预期8图，排除输出自身。

## 3. 修复（S8/S9）

使用 [blender_repair_export.py](../scripts/blender_repair_export.py) 的 `--stage repair`：

```powershell
& "<BlenderExe>" --background --python "<skillRoot>/scripts/blender_repair_export.py" -- --stage repair --blend "<input.blend>" --out-dir "<projectRoot>/4.模型文件/4.2表面修复版" --res 1600
```

repair只保存新版本 `.blend`、`.glb`、重渲染与 `repair-report.json`/修复说明，不接受 `--stl`，不写 `5.打印`。默认防覆盖；实际mesh对象引用传给渲染，不依赖figure名称。

允许：局部凸起/凹陷/缺失、填孔、重复顶点/孤立点清理、法线一致及基础水密。漂浮块、对称小修须对照需求卡和issue，不删除配件或消除非对称姿态。禁止第一遍穿模/布尔/重拓扑/改比例/换姿态。最多3轮，每轮新建 `4.N…`，重新双审并让用户验收。

报告记录before/after、实际changes、当前issues和逐项检查；已知限制来自本次结果，未量测项写unknown。`watertight` 与 `shapeAccepted` 独立，水密改善不能宣称保形或用户满意。

## 4. 最终导出（S10）

```powershell
& "<BlenderExe>" --background --python "<skillRoot>/scripts/blender_repair_export.py" -- --stage export --blend "<final.blend>" --out-dir "<new-export-report-dir>" --stl "<projectRoot>/5.打印/<name>_final.stl" --height-mm "<目标高度mm>" --min-wall-mm "<最小壁厚mm>" --confirm-gate G9 --confirmation-file "<G9-confirmation.json>" --checks-file "<print-measurements.json>"
```

确认记录至少含 `confirmedAt`、`gate: "G9"`、`shapeAccepted: true`、`blendSha256`，匹配最终blend；执行侧不得代用户补造。逐项检查水密、自交、退化面、重复顶点、法线、体积、bbox、薄壁，输出 `pass|fail|unknown`；任一fail或关键unknown以 **exit 14** 停止，不产生final STL。

自交与薄壁默认记为 `unknown`。用 `--checks-file` 提供绑定最终 Blend 的实测记录。最终二进制 STL 以毫米为单位，详见[打印检查](60-printing.md)。

## 5. 减面与回滚

保形减面需授权与前后对照，记录保留比例；禁止导出时静默改造型。细节丢失应**提高ratio、减小减面幅度，并从原版本重做**。不能继续破坏已减面结果来恢复细节。旧版本与审核证据保留，恢复也另存新版本。

## 局部修复复核

- 保留输入模型。在新文件或后台进程中处理，避免清空用户正在编辑的场景。
- 先用同视角材质图和纯色图定位缺陷。若纯色图没有相同起伏，单独检查颜色贴图、烘焙阴影和法线贴图。
- 只在问题区域调整几何，保护相邻配件、接缝和 UV。二次修补按当前版本重新圈定选区，检查过渡边缘有无新凹痕。
- 用相同光照的修前、修后近景和斜侧视角对比。高密模型要记录检查范围及超出预算的检查，并把这些结果标为 `unknown`。
- 对最终 GLB 或 STL 做一次重导入，核对尺寸、组件和拓扑。活动结构另行检查全行程、偏摆与公差下的干涉，并单独记录实体试装状态。
