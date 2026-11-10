# 安全与隐私

## 报告漏洞

当前维护版本为 v1.0.0。请通过 [GitHub 私有漏洞报告](https://github.com/RTD-com/3d-print-figure/security/advisories/new)提供版本、最小复现、影响范围与脱敏证据。将账号信息、凭据、签名链接、用户图像及受影响项目留在私有环境。

## 运行边界

- 在专用浏览器配置中由用户登录混元。调试端口仅供本机使用，完成后关闭专用窗口。
- 图片上传前确认目标服务和授权范围。提交生成前核对逐槽图片哈希、实际配置、实时额度和一次性确认记录。
- 中断后依据原任务 ID 查询或下载。提交已尝试或结果不明时，先核对任务状态。
- 将下载签名链接视同临时凭据。项目、浏览器配置、DOM、截图、运行日志与交付清单均按私有资料处理。
- 从可信 Git 检出安装，核对安装包清单中的版本、提交和文件哈希。
- 在独立 Blender 会话中打开来源可信的模型文件。最终 STL 以用户确认的 Blender 文件与可靠打印检查为准。

## 发布检查

只跟踪公开源码、文档及合成示例。提交前运行离线自检并审查差异。公开既有私有仓库前，还需清查历史提交、分支、标签、PR、发布附件及 Actions 日志。处理历史泄露时请遵循 [GitHub 清理指引](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)。
