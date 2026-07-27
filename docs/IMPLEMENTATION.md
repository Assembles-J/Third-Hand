# Third-Hand MVP 实现说明

## 已实现

- `GET /health`：服务健康检查。
- `GET /v1/holdings`、`POST /v1/holdings`、`DELETE /v1/holdings/{id}`：持仓的新增、查看、删除。
- `POST /v1/holdings/import`：导入用户自行导出的 CSV；使用标准 CSV 解析器，支持带引号的公司名，并逐行反馈错误。服务不接收交易密码、验证码或 Cookie。
- `GET /v1/feed`：优先按已保存的持仓关联信息卡；也可使用 `?symbols=01810` 指定代码。
- `GET /v1/glossary/{term}`：新手词条卡片。

持仓目前仅放在进程内存中，因此重启服务会清空数据。这是为了让 MVP 先验证信息关联体验；生产接入前应补充登录认证、PostgreSQL、静态加密、备份和删除/导出机制。

## 本地运行

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --reload
```

打开 `http://127.0.0.1:8000/docs` 可直接试用接口。

## GitHub Actions

`.github/workflows/ci.yml` 会在推送到 `main` 或创建 PR 时：

1. 安装 Python 3.12，编译并测试后端；
2. 构建后端 Docker 镜像；
3. 安装 JDK 17、Android SDK 和 Gradle，构建 debug APK；
4. 将 APK 作为 CI artifact 保存。

推送前请在 GitHub 仓库的 **Settings → Actions → General** 确认 Actions 已启用。生产部署密钥、数据源 Token 和签名密钥只能放在 GitHub Secrets，绝不能提交到仓库。
