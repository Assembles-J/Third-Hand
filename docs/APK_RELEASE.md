# Third-Hand 生产部署、APK 自动发布与应用内升级

合并到 `main` 后，`Deploy` 工作流始终部署后端，但只在 `android/` 目录发生变化时发布新的移动端版本：

1. 使用固定签名证书构建 release APK；
2. 校验 APK 已签名；
3. 以临时文件名上传到 `/opt/third-hand/releases`；
4. 在服务器原子改名，更新 `.env` 中的版本和 APK 文件名；
5. 重建 API 容器并验证更新接口；
6. 客户端启动时检查新版本，把 APK 保存到公共 `下载/Third-Hand` 目录；
7. 下载后校验大小、SHA-256、包名和签名，再打开 Android 系统安装器；
8. 安装取消或失败后保留下载记录，用户可以从应用内重新打开安装器。

仅修改后端、文档或部署配置时，会保留服务器当前 APK 文件和版本元数据，不会让手机收到无意义的新版本。需要在没有 Android 代码变化时重新发布 APK，可在 GitHub `Actions > Deploy > Run workflow` 中勾选 `release_android`。

Android 不允许普通应用静默安装更新。第一次升级时，用户必须允许 Third-Hand“安装未知应用”，每次安装仍由系统安装器确认。

## 当前生产拓扑

生产域名使用 Cloudflare 代理的 `groupim.cn`。GroupIM 已占用 `/api` 和 `/`，因此 Third-Hand 使用独立路径前缀：

```text
https://groupim.cn/third-hand
```

服务器当前相关容器如下：

| 用途 | 容器名 | 容器端口 |
| --- | --- | --- |
| Third-Hand API | `third-hand-api-1` | `8000` |
| HTTPS 入口 | `nginx` | `80`、`443` |
| GroupIM 后端 | `im-server-cicd` | `8080`、`8088` |

Nginx 与 Third-Hand API 通过外部 Docker 网络 `app_gateway` 通信。Nginx 始终访问稳定别名 `third-hand-api:8000`，不要在 Nginx 配置中使用可能随 Compose 项目变化的容器名 `third-hand-api-1`。

## 一次性签名配置

必须永久保留同一份 keystore。丢失后，已经安装的客户端无法再覆盖升级。

可以在可信 Linux 服务器生成 PKCS12 证书：

```bash
install -d -m 700 /root/third-hand-signing

keytool -genkeypair -v \
  -keystore /root/third-hand-signing/third-hand-release.p12 \
  -storetype PKCS12 \
  -alias third-hand \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10000

chmod 600 /root/third-hand-signing/third-hand-release.p12
```

必须离线备份 `.p12` 和密码。Base64 只是编码，不是加密，也必须保密。

在 GitHub 仓库的 `Settings > Environments > production > Environment secrets` 中配置：

| Secret | 内容 |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | keystore 文件的 Base64 |
| `ANDROID_KEYSTORE_PASSWORD` | keystore 密码 |
| `ANDROID_KEY_ALIAS` | 默认是 `third-hand` |
| `ANDROID_KEY_PASSWORD` | 私钥密码 |
| `APP_PUBLIC_BASE_URL` | `https://groupim.cn/third-hand`，不带结尾 `/` |
| `APP_UPDATE_PUBLIC_BASE_URL` | 可选；推荐 `https://groupim.cn/third-hand/releases`，不带结尾 `/` |
| `SERVER_IP` | 部署服务器地址 |
| `SERVER_USER` | SSH 用户 |
| `SERVER_SSH_KEY` | SSH 私钥 |

`TUSHARE_TOKEN` 与 `DEEPSEEK_API_KEY` 保持现有配置即可。

如果服务器安装了 GitHub CLI，可以避免复制很长的 Base64：

```bash
base64 -w 0 /root/third-hand-signing/third-hand-release.p12 \
  | gh secret set ANDROID_KEYSTORE_BASE64 \
      --env production \
      --repo pengpengno/Third-Hand

gh secret set ANDROID_KEYSTORE_PASSWORD --env production --repo pengpengno/Third-Hand
gh secret set ANDROID_KEY_PASSWORD --env production --repo pengpengno/Third-Hand
gh secret set ANDROID_KEY_ALIAS --env production --repo pengpengno/Third-Hand --body "third-hand"
gh secret set APP_PUBLIC_BASE_URL --env production --repo pengpengno/Third-Hand --body "https://groupim.cn/third-hand"
gh variable set APP_UPDATE_PUBLIC_BASE_URL --repo pengpengno/Third-Hand --body "https://groupim.cn/third-hand/releases"

gh secret list --env production --repo pengpengno/Third-Hand
gh variable list --repo pengpengno/Third-Hand
```

密码类命令会交互读取输入，不要把密码写进命令行历史、Git 仓库或聊天记录。

## Docker 共享网络

仓库内的 `docker-compose.yml` 已将 Third-Hand API 固定接入外部网络 `app_gateway`，并提供稳定别名 `third-hand-api`。首次部署前创建网络：

```bash
docker network inspect app_gateway >/dev/null 2>&1 || docker network create app_gateway
```

GroupIM 的 Compose 文件还需要让 Nginx 服务加入该网络，同时保留它原有的默认网络：

```yaml
services:
  nginx:
    networks:
      - default
      - app_gateway

networks:
  app_gateway:
    external: true
    name: app_gateway
```

修改 GroupIM Compose 后重建 Nginx。若暂时还未修改 Compose，可对当前容器临时连接网络：

```bash
docker network connect --alias third-hand-api app_gateway third-hand-api-1
docker network connect app_gateway nginx
docker exec nginx getent hosts third-hand-api
```

如果提示容器已经连接，可跳过对应命令。临时连接在容器被重新创建后会丢失，所以最终必须把网络写入两个项目的 Compose 配置。

Third-Hand 的宿主机端口只绑定 `127.0.0.1:8000`，公网访问统一经过 Nginx 和 Cloudflare。

## Nginx 配置

在 `http {}` 中增加：

```nginx
upstream third_hand_api {
    server third-hand-api:8000;
    keepalive 16;
}
```

在 `server_name groupim.cn;` 的 HTTPS `server {}` 中，并且放在现有 `location /` 前面：

```nginx
location ^~ /third-hand/ {
    proxy_pass http://third_hand_api/;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto https;

    proxy_connect_timeout 30s;
    proxy_send_timeout 120s;
    proxy_read_timeout 120s;

    proxy_buffering off;
    proxy_request_buffering off;
    add_header Cache-Control "no-store" always;
}
```

`proxy_pass` 末尾的 `/` 不能省略，它负责把公网 `/third-hand/v1/...` 转换为 FastAPI 容器内的 `/v1/...`。

检查并平滑加载：

```bash
docker exec nginx nginx -t
docker exec nginx nginx -s reload
```

Cloudflare SSL/TLS 模式使用 `Full (strict)`，并为 URI Path 以 `/third-hand/` 开头的 API 请求设置绕过缓存。更新元数据必须保持最新；版本化 APK 则使用下面的独立静态下载域名。

## 独立 APK 下载域名（推荐）

不要把服务器裸 IP 写入客户端。为 `download.groupim.cn` 添加指向源站 IP 的 DNS 记录，并设置为 **DNS only（灰色云）**，这样下载仍使用稳定 HTTPS 域名，但不经过 Cloudflare 代理。直连源站时必须使用浏览器和 Android 都信任的公网证书（例如 Let's Encrypt）；只供 Cloudflare 回源使用的 Origin Certificate 不适合灰色云直连。

让 GroupIM 的 Nginx 容器只读挂载发布目录：

```yaml
services:
  nginx:
    volumes:
      - /opt/third-hand/releases:/srv/third-hand-releases:ro
```

在 `server_name download.groupim.cn;` 的 HTTPS `server {}` 中加入：

```nginx
location ^~ /third-hand/releases/ {
    alias /srv/third-hand-releases/;
    try_files $uri =404;

    default_type application/vnd.android.package-archive;
    add_header Cache-Control "public, max-age=31536000, immutable" always;
    add_header Accept-Ranges "bytes" always;

    sendfile on;
}
```

文件名带版本号，因此长期缓存不会把新版本误认为旧版本；Nginx 静态文件也原生支持 `Content-Length` 和 Range 断点续传。随后设置 Repository variable：

```text
APP_UPDATE_PUBLIC_BASE_URL=https://groupim.cn/third-hand/releases
```

如果该变量留空，后端会自动回退到原来的
`https://groupim.cn/third-hand/v1/app-update/apk`，旧客户端和现有部署不会中断。回退接口同样为版本化内容返回长期缓存头，但由于主域名的 API 路径通常绕过 Cloudflare 缓存，性能仍不如 Nginx 静态直连。

## 部署前检查

```bash
docker network inspect app_gateway
docker exec nginx getent hosts third-hand-api
curl -fsS http://127.0.0.1:8000/health
curl -fsS https://groupim.cn/third-hand/health
curl -I https://groupim.cn/third-hand/releases/third-hand-<version>.apk
```

健康接口预期返回：

```json
{"status":"ok"}
```

## 首次切换正式签名

如果手机当前安装的是 Android Studio 或 CI 临时生成的 debug APK，它与正式 keystore 的签名不同，系统会提示“软件包与现有应用冲突”。第一次需要：

1. 确认后端持仓数据已备份；当前持仓在服务器 SQLite，不会随手机卸载删除。
2. 先把正式 APK 下载到手机公共 `下载/Third-Hand` 目录；不要保存在应用专属的 `Android/data/com.thirdhand.app` 目录，因为卸载时该目录可能被删除。
3. 卸载手机上的 debug 版。
4. 从系统文件管理器的 `下载/Third-Hand` 目录安装一次正式版。
5. 以后所有版本都能在应用内覆盖升级。

新版客户端会在下载完成后预检签名。发现 debug 与正式签名不一致时，不再打开必然失败的覆盖安装，而是保留 APK 并明确提示上述迁移步骤。Android 不允许应用在卸载自身后继续执行代码，因此首次签名迁移无法做到完全无人值守。

## 验证发布

```bash
curl -i https://groupim.cn/third-hand/v1/app-update
```

正式 APK 尚未发布时，该接口返回 `204 No Content` 是正常的。发布完成后应返回 `200`，元数据包含递增的 `version_code`、版本名、`sha256`、`size_bytes` 和 HTTPS `apk_url`。

下载校验（先从更新元数据读取实际 `apk_url`）：

```bash
APK_URL="$(curl -fsS https://groupim.cn/third-hand/v1/app-update | python3 -c 'import json,sys; print(json.load(sys.stdin)["apk_url"])')"
curl -fL "$APK_URL" -o /tmp/third-hand-release.apk

sha256sum /tmp/third-hand-release.apk
```

下载文件的 SHA-256 必须与更新元数据中的 `sha256` 相同。

## 发布与故障排查

合并到 `main` 后，在 GitHub `Actions > Deploy` 查看：

1. release APK 构建与 `apksigner verify` 成功；
2. 文件上传到 `/opt/third-hand/releases`；
3. `third-hand-api-1` 健康；
4. `/v1/app-update` 返回新版本元数据。

服务器侧排查：

```bash
cd /opt/third-hand
docker compose ps
docker compose logs --tail=200 api
docker logs --tail=200 nginx
curl -fsS http://127.0.0.1:8000/health
curl -i https://groupim.cn/third-hand/v1/app-update
```

如果 Nginx 返回 `502 Bad Gateway`，优先检查：

```bash
docker exec nginx getent hosts third-hand-api
docker network inspect app_gateway
```

如果更新接口返回 `204`，检查 `/opt/third-hand/.env` 中的 `APP_PUBLIC_BASE_URL`、`APP_UPDATE_APK_FILE`、`APP_UPDATE_VERSION_CODE`，以及 `/opt/third-hand/releases` 中是否存在对应 APK。检查时不要输出密码或 API Token。
