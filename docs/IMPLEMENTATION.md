# Third-Hand MVP 实现说明

## 已实现

- `GET /health`：服务健康检查。
- `GET /v1/holdings`、`POST /v1/holdings`、`DELETE /v1/holdings/{id}`：持仓的新增、查看、删除。
- `POST /v1/holdings/import`：导入用户自行导出的 CSV；使用标准 CSV 解析器，支持带引号的公司名，并逐行反馈错误。服务不接收交易密码、验证码或 Cookie。
- `GET /v1/feed`：优先按已保存的持仓关联信息卡；也可使用 `?symbols=01810` 指定代码。
- `GET /v1/market/quotes?symbols=01810&symbols=600519`：通过 AKShare 获取 A 股和港股的行情快照，返回数据来源、抓取时间和延时说明。
- Android“识别截图”：采用 ML Kit 中文本地 OCR 提取名称、持仓数量和成本价，截图不上传服务器；因截图通常不含证券代码，必须在预览后人工补全代码才可导入。
- `GET /v1/glossary/{term}`：新手词条卡片。

持仓使用 SQLite 保存，默认文件为 `backend/data/third_hand.db`；Docker 环境使用项目根目录的 `data/` 卷，因此容器重启不会清空持仓。它适合单实例 MVP；生产接入多用户登录后，再评估 PostgreSQL。无论使用何种数据库，都应补充认证、静态加密、备份和删除/导出机制。

行情适配器会将相同市场的全量公开快照缓存 60 秒，避免每次 App 刷新都请求公开网站。港股 `01810`（小米集团-W）走 `stock_hk_spot_em`；A 股走 `stock_zh_a_spot_em`。这是信息展示与提醒用途的公开源快照，绝不能用作下单、止损或任何交易执行依据。

信息流会按持仓调用 AKShare 的公开个股新闻接口，保留原文链接、来源、发布时间和关联代码，并以 5 分钟缓存限制请求频率。新闻源不可用时接口返回 `503`，不会用过时示例消息伪装成实时新闻。原文仍是用户核查事实的依据。

`GET /v1/announcements` 为 A 股持仓获取巨潮资讯公开披露公告，并以“正式公告”单独呈现；默认回看 30 天，可用 `days=1..90` 调整。港股不使用该 A 股公告接口，避免错误标注来源。

所有面向用户的 API 时间字段（例如 `retrieved_at`、`published_at`、`created_at`）均使用北京时间 `Asia/Shanghai`，并携带 `+08:00` 时区偏移，例如 `2026-07-27T13:40:00+08:00`。

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

### Android 实机调试

1. 手机和运行后端的电脑连接同一个 Wi-Fi；不要使用公共网络。
2. 在电脑的 `backend/` 目录运行：

   ```powershell
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

3. 在 Windows 防火墙中仅为当前专用网络允许 TCP 8000 入站；不要对公网开放该端口。
4. 在 App 的“我的”页填写 `http://<电脑局域网IP>:8000/`，例如 `http://192.168.1.10:8000/`，点击“保存地址”和“测试连接”。
5. 测试成功后，在“持仓”页添加持仓，在“今日”页刷新公开行情。

模拟器仍使用默认地址 `http://10.0.2.2:8000/`。开发环境允许 HTTP 明文连接；正式部署必须使用 HTTPS 域名，并移除明文流量配置。

Android 工程提交时应保留 `gradlew`、`gradlew.bat`、`gradle/wrapper/gradle-wrapper.jar`、`gradle/wrapper/gradle-wrapper.properties` 和 `gradle.properties`。不要提交 `local.properties`、`.gradle/` 或 `build/`；它们是机器或构建产物相关文件。

## GitHub Actions

`.github/workflows/ci.yml` 会在推送到 `main` 或创建 PR 时：

1. 安装 Python 3.12，编译并测试后端；
2. 构建后端 Docker 镜像；
3. 安装 JDK 17、Android SDK 和 Gradle，构建 debug APK；
4. 将 APK 作为 CI artifact 保存。

推送前请在 GitHub 仓库的 **Settings → Actions → General** 确认 Actions 已启用。生产部署密钥、数据源 Token 和签名密钥只能放在 GitHub Secrets，绝不能提交到仓库。

## Docker Compose 与部署

在服务器部署目录中创建环境文件，然后启动服务：

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/health
```

Compose 默认只将 API 绑定到 `127.0.0.1:8000`，因此公网无法直接访问。上线时应由已配置 HTTPS 的 Caddy 或 Nginx 反向代理它；不要把开发阶段的 `usesCleartextTraffic` 当作生产方案。

`Deploy` 工作流只允许手动运行，并要求 GitHub Environment `production`。在仓库的 **Settings → Secrets and variables → Actions** 中配置：

- Secrets：`SERVER_IP`、`SERVER_USER`、`SERVER_SSH_KEY`。
- 部署目录固定为 `/opt/third-hand`，无需再配置 `SERVER_PATH`。

部署工作流与现有 Group-IM 项目一样使用 Appleboy 的 SSH/SCP Action，不再要求 `SERVER_KNOWN_HOSTS`。部署用户只应拥有目标部署目录及 Docker Compose 所需的最小权限。
