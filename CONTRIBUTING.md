# 贡献指南

## 开发与验证

从 `main` 创建短分支。修改工作流时，更新相应的 [reference](references/) 和 [安装清单](assets/install-manifest.json)。契约示例随 Schema 更新。保留现有退出码与产物目录约定，行为变化记录到[更新日志](CHANGELOG.md)。

Windows 下运行以下离线检查。环境要求见[安装说明](README.zh-CN.md)。

```powershell
python scripts/selfcheck.py
python -m unittest discover -s tests -v
```

CI 使用合成数据和本地模拟程序。验证真实服务前，取得图片上传与额度消耗的授权。测试结论按[验证范围](docs/validation-matrix.md)区分离线、真实运行和待验证项。

## 提交 PR

- 说明变更范围、复现方法和验证结果。
- 对会写入文件或消耗额度的操作，覆盖确认缺失、重复执行和已有产物的情况。
- 安装清单只列运行所需的文件。补充文档链接时，确认两端安装包能独立访问对应资源。
- 使用合成输入。将模型、图片、账号资料、日志、签名链接与本机路径留在私有目录。
- 漏洞和敏感证据按[安全说明](SECURITY.md)走私有渠道。

贡献随项目以 [MIT 许可证](LICENSE)发布。请提交你有权按该许可证分发的内容。
