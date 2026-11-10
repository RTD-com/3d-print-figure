# 混元 3D 网页自动化（S6）

自研 CDP 脚本使用 Node.js 22+ 内置 WebSocket、本机 Edge/Chrome 可见窗口及独立 profile。登录由用户完成。脚本面向网页 Normal 生成。页面能力变化时重新核对配置。

发布检查覆盖离线门禁。真实网页的逐槽完成态、配置回读、任务绑定和下载事件需授权后复验。DOM 证据不足时保留阻塞。

## 1. 启动与模式

```powershell
scripts\start_browser.bat
# 或在用户终端中启动可见浏览器
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start_browser.ps1 -Workdir "<工作目录>"
node scripts\hunyuan_web.mjs --mode probe --project "<项目根>" --port 9229
node scripts\hunyuan_web.mjs --mode upload --project "<项目根>" --port 9229 --dry-run
```

| 模式 | 行为 |
|---|---|
| `probe` | 导航创作页，保存 DOM、文本、按钮、输入槽位、额度与截图供校准 |
| `wait-login` | 等待可见窗口登录；不会刷新正在登录的混元页面 |
| `upload` | 读取额度、逐槽上传、配置回读、保存 dry-run 证据；**永不提交** |
| `submit` | 校验固定确认文件、8图哈希、配置和实时额度，再提交并绑定任务、等待、下载 |
| `status` | 只从 `metadata.json` 恢复已保存任务结果页；不导航创作首页 |
| `download` | 恢复已保存任务结果页，核对完成状态，只下载该任务 GLB |

未知 mode 列出以上合法值并退出 2。参数包括 `--project`（必填）、`--port 9229`、`--browser edge|chrome|路径`、`--profile`、`--selectors`、`--timeout-min 30`、`--interval-sec 15`、`--dry-run`、`--confirm-file`、`--out-dir`、`--force`。`--images` 默认指向本项目 `3.图片/v1`。使用其他已批准版本时，对 upload 和 submit 传入同一个 `3.图片/vN` 目录。submit 只接受项目内的实际版本目录，并重新核对八图哈希。

已移除 `--close`、`--confirmed` 与 `--confirm-before-submit`；旧参数退出 2。浏览器保持打开供用户检查，CDP 连接在脚本退出时关闭。

## 2. 确认协议

1. 先执行 upload dry-run，读取 `2.DSH/04-浏览器记录/pending-confirm.json`。
2. DSH 向用户展示8槽证据、额度 DOM 原文、实际版本/面数、网页 Normal 偏差与预计消耗。没有批准就停止。
3. 用户确认后，由编排方将确认记录写入**本项目固定位置** `2.DSH/03-确认/submit-confirmation.json`。脚本不会自行创建授权记录。
4. 明确执行 submit；缺文件、字段、匹配失败或已使用的确认均退出 **10**，在浏览器发现/连接之前阻断可离线发现的错误。

确认文件完整结构如下；`imageSha256` 中8项必须替换成对应实际文件的64位小写 SHA256，顺序见下一节。示例占位值不是有效授权：

```json
{
  "confirmedAt": "<用户确认的ISO8601时间>",
  "project": "<项目根的绝对路径>",
  "imageSha256": ["<top哈希>", "<left45哈希>", "<front哈希>", "<right45哈希>", "<left哈希>", "<right哈希>", "<back哈希>", "<bottom哈希>"],
  "quotaBefore": 4,
  "modelVersion": "3.1",
  "faces": 1500000,
  "generateType": "Normal"
}
```

```powershell
node scripts\hunyuan_web.mjs --mode submit --project "<项目根>" --confirm-file "<项目根>\2.DSH\03-确认\submit-confirmation.json" --port 9229
```

`project` 必须匹配当前项目；确认文件不可通过符号链接逃逸；时间必须可解析且不得是未来时间；额度必须是正整数；8图哈希在提交前再次计算；版本/面数必须与 DOM 回读一致。submit 加 `--dry-run` 仍须合法确认，但不创建消耗回执、不点击提交。

提交点击之前用排他创建的 `submit-used-<确认摘要>.json` 记录已尝试的提交。重排确认 JSON 的字段不会生成新授权。再次提交需有晚于先前尝试的用户确认。超时或脚本中断后只用 status/download 恢复；不得自动重新提交。若点击未发生但回执已写入，也必须先检查任务状态，由用户作出新的明确确认。

## 3. 八槽上传与文件约束

| 索引 | 槽位 | 文件 |
|---|---|---|
| 0 | top / 上传顶图 | `01_top.png` |
| 1 | left45 / 角色左前45° | `02_left45.png` |
| 2 | front / 正图（必填） | `03_front.png` |
| 3 | right45 / 角色右前45° | `04_right45.png` |
| 4 | left / 角色左侧 | `05_left.png` |
| 5 | right / 角色右侧 | `06_right.png` |
| 6 | back / 背图 | `07_back.png` |
| 7 | bottom / 底图 | `08_bottom.png` |

[选择器配置](../assets/templates/hunyuan-selectors.json) 的 `upload.fileInputSelector`、`expectedInputs`、`accept`、`maxBytes`、`minEdge`、`slotContainerSelector` 均被脚本消费。固定8张 PNG；当前限制 ≤10 MiB、每边 ≥128px。此处检查 PNG 签名、IHDR尺寸与文件大小；完整图片解码、方形同尺寸与 alpha/白底门由 `validate_views.py` 在前一阶段完成。

上传前必须恰好8个输入且标签符合表格。每槽设置文件后，等待同一槽的文件名/缩略图解码完成/无“上传中”或进度指示/无错误同时成立，再处理下一槽，最后再次核对全部8槽。DOM 清空文件名或槽位容器无法唯一定位时退出16，须校准可读的文件名属性；不能靠全页 img 总数绕过。dry-run 证据记录每槽，不再以历史 `thumbs=9` 解释成8/8。

## 4. 配置与额度

版本和面数点击后，通过 `settings.selectedSelector` 读取实际选中 DOM 文本；无法唯一解析或与确认不一致退出 **13**。metadata 记录实际 `modelVersion`、`faces` 及原始选中文本。网页没有类型选项，所以 `generateType` 实测值记录为 `unknown`，`webCapability` 单独记录历史网页 Normal 能力说明；禁止把该说明伪装成 DOM 实测值。

额度由 `quota.badgeSelector` 读取：多个徽章必须给出同一纯整数字符串，无法解析为非负整数即 `unknown`。页面文本/徽章原文保存在日志、quota记录和提交 metadata；点击前重新读取。小于1或未知退出 **12**；有效但与 `quotaBefore` 不同退出 **10**。本脚本不把国际站积分表当作当前计价依据；真实成本与额度口径仍须由页面和用户确认。

## 5. 任务绑定、下载与版本

点击前先保存 `submittedAt` 和 submission-attempted metadata；随后必须获得相对于点击前不同的 taskId 及含该 ID 的结果页 URL，保存到 `4.模型文件/4.1初版/metadata.json`。60秒内不能建立绑定即退出 **11**，保留证据，绝不自动新开任务。

status/download 必须从同一 metadata 恢复 `{taskId,resultPageUrl,submittedAt}`，缺失退出11。启动浏览器或恢复页时也直接使用该结果页，不先导航创作首页。每次完成态读取和下载前核对当前页任务身份；仅绑定页的“生成成功/已完成”视为完成，“下载”字样本身不代表生成成功。

首选资源下载只接受该结果页 ResourceTiming 中时间不早于本次提交的唯一 GLB 资源。脚本只直接请求混元或腾讯云 COS 的 HTTPS 地址，其他资源使用绑定结果页的下载按钮。兜底 UI 下载只接受点击之后该页 frame 的 `Browser.downloadWillBegin` GUID，等待对应 completed 事件并核对新文件时间与大小；不采用旧目录最大文件、不把 zip 当 GLB。

下载后验证：文件 >1 MiB、magic=`glTF`、GLB版本2、声明长度等于实际长度；计算完整 SHA256并写 metadata。metadata 只保存资源 origin/path，不保存签名查询参数，不输出签名 URL。profile、metadata和 URL 记录不得提交或打包。

默认产物 `4.模型文件/4.1初版/初版.glb` 已存在时退出 **17**。请选择新版本 `--out-dir "<项目根>\4.模型文件\4.2初版"`；只有显式 `--force` 才能覆盖。`--force` 不允许重用已经消耗的同一确认。

## 6. 退出码与故障处理

| 码 | 含义与处理 |
|---|---|
| 0 | 当前请求成功；upload/dry-run成功不表示已提交 |
| 2 | 参数/未知 mode/已移除参数，先修命令 |
| 10 | 确认缺失、不匹配、已消耗，必须重新核实并获得明确确认 |
| 11 | 任务身份/结果页上下文缺失或不匹配，保留证据，禁止新开任务 |
| 12 | 提交前额度不足1或无法读取，用户决定下一步 |
| 13 | 配置回读、生成失败/超时、GLB下载/内容校验失败；禁止自动重试提交 |
| 14 | CDP浏览器未就绪，按用户权限环境启动可见浏览器 |
| 15 | 需要用户登录或登录等待超时 |
| 16 | 图片约束、槽位身份/上传完成态失败；probe后修选择器 |
| 17 | 目标产物已存在，选择新版本或明确 --force |
| 20 | 其它脚本/IO错误，保留现场后排错 |

用户拒绝登录或网页不可自动化时，人工上传/生成/下载并提供 GLB 路径，记 `manualFallback=true` 后从 S7 继续。失败不能推定已有确认覆盖新任务的额度消耗。
