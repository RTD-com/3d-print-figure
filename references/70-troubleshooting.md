# 排错手册

## Codex / codex exec
| 现象 | 处理 |
|---|---|
| `codex` 不是命令 | 用 `Get-Command codex` 核对命令是否在 PATH |
| MCP blender 未列/未启用 | `codex mcp list` 检查连接配置和 Blender 中的 MCP 插件状态 |
| 超时 | 缩小任务（按视角/按步骤拆分）；按阶段调整 `-TimeoutSec`；查 JSONL 日志最后事件 |
| 非零退出但无输出 | 看 stderr 与 `--output-last-message` 文件；检查安全策略/沙箱 |
| 返回非 JSON | 加 `--output-schema`；prompt 明确「只输出 JSON」 |

## image_gen
| 现象 | 处理 |
|---|---|
| 生成失败/拒绝 | 改 prompt 措辞；减少冲突约束；重试 ≤3 |
| 透明背景变白底 | 明确 `genuinely transparent alpha, no background`；用 edit 修 alpha；仍失败显式 `--alpha-mode white` 走白底校验（Q15），报告标mode |
| 尺寸不一致 | 统一在 prompt 写目标尺寸；生成后用 `validate_views.py` 检查；不一致的用 edit 重做 |
| 视角漂移 | 用母版作 `Input image 1`；edit 指令写 `change only camera, keep identity` |
| 左右镜像 | 按 [相机坐标表](40-blender-mcp.md) 写每视角映射，仅front画面左=角色右；edit 时列出不动项 |

## 混元网页 / CDP
| 现象 | 处理 |
|---|---|
| CDP 连不上 | 确认专用 Edge 窗口的本机调试端口和脚本一致，关闭本项目的旧窗口后重试 |
| 未登录 | 在可见窗口登录；脚本退出码 15；不要自动关闭窗口 |
| 找不到上传控件 | `--mode probe` 抓 DOM/inputs；更新 `hunyuan-selectors.json` |
| 8 槽位顺序错 | 逐槽核对缩略图；重传；不要提交 |
| 额度不足 | 用户决定；退出码 12 |
| 生成超时 | 复用metadata中的taskId与结果页查状态；不得重新提交消耗；缺上下文exit11 |
| 下载无文件 | 检查下载目录；用页面下载按钮重试；手动下载给路径 |
| 页面改版 | probe + 更新选择器；脚本与文档同步；短期手动兜底 |

## Blender / MCP
| 现象 | 处理 |
|---|---|
| 9876 不通 | Blender 打开 → 侧栏 MCP for Blender → Start MCP Server |
| addon 未装 | 安装到 Blender 用户脚本目录下的 `addons\blender_mcp.py`（`<Blender用户目录>\<版本>\...`，勿放进发行包）；重装用 `uvx mcp-for-blender install-addon`（需 uv）或手动 Install |
| 导入失败 | 检查 GLB 完整性（magic/大小）；重新下载 |
| 渲染黑图 | 相机朝向/灯光/film_transparent/view_transform |
| 5.2 算子名变化 | `bpy.ops.wm.stl_export` 优先，失败 fallback `export_mesh.stl`；用 `dir(bpy.ops)` 查 |
| 减面后破面 | 提高ratio、减小减面幅度，并从原版本重新对照；先检查重复顶点/孔洞 |
| 内存不足 | 先保存打开的场景；在专用会话中降低渲染分辨率或做经确认的保形减面 |

## 文件/目录
| 现象 | 处理 |
|---|---|
| 版本覆盖 | 禁止；新建 `4.N`；从 `4.9归档` 恢复 |
| 路径含中文 | 全程 UTF-8；PowerShell 用 `-LiteralPath`；Python 用 `Path` |
| 磁盘不足 | 预检 ≥5 GB；大文件（GLB/STL）及时归档 |
| sha256 不一致 | 重新复制；不要信任旧 manifest |

## 交互
| 现象 | 处理 |
|---|---|
| 用户拒绝登录/额度 | 转手动兜底；记录 `manualFallback=true` |
| 用户验收意见模糊 | 要求「部位 + 视角 + 期望」；给接触表/渲染图让用户圈选 |
| 用户长时间不回复 | 暂停在确认点，不自动继续消耗 |

确认文件错误exit10、任务上下文exit11、额度未知/不足exit12、配置/生成/GLB错误exit13、CDP失败exit14、未登录exit15、逐槽未完成exit16、产物已存在exit17；参数错误exit2。详见 [混元手册](30-hunyuan-web.md)。Blender export的exit14表示质量门未通过，两脚本退出码命名空间独立。
