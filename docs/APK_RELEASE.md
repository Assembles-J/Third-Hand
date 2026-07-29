# APK 发布与应用内更新

本项目由 FastAPI 提供 APK 下载，APK 不进入 Git 仓库，也不打进 Docker 镜像。生产环境必须通过 HTTPS 反向代理公开 API。

## 首次配置

在服务器项目目录创建 `releases` 目录，并在 `.env` 中配置：

```env
APP_PUBLIC_BASE_URL=https://api.example.com
APP_UPDATE_APK_FILE=third-hand-0.2.0.apk
APP_UPDATE_VERSION_CODE=2
APP_UPDATE_VERSION_NAME=0.2.0
APP_UPDATE_CHANGELOG=新增应用内更新功能。
```

`APP_PUBLIC_BASE_URL` 是用户手机实际访问的 HTTPS API 根地址，不能带结尾的 `/`。将反向代理配置为把 `/` 转发到该容器的 8000 端口。

启动服务：

```powershell
docker compose up -d --build
```

验证元数据与下载接口：

```powershell
curl https://api.example.com/v1/app-update
curl -I https://api.example.com/v1/app-update/apk
```

## 发布新版本

1. 将 Android `versionCode` 增加到一个更大的整数，并更新 `versionName`。
2. 使用**同一个 keystore**签名生成 release APK。
3. 先上传为临时名，确认完整后再在服务器上原子改名，避免客户端下载到半个文件。

```powershell
scp app-release.apk deploy@your-server:/opt/third-hand/releases/third-hand-0.2.0.apk.part
ssh deploy@your-server "mv /opt/third-hand/releases/third-hand-0.2.0.apk.part /opt/third-hand/releases/third-hand-0.2.0.apk"
```

4. 修改服务器 `.env` 中的 `APP_UPDATE_APK_FILE`、`APP_UPDATE_VERSION_CODE`、`APP_UPDATE_VERSION_NAME` 与更新说明，然后重建 API 容器配置：

```powershell
docker compose up -d --force-recreate api
```

旧版客户端进入“我的”页会检查 `/v1/app-update`；如果版本号更高，就从 `/v1/app-update/apk` 下载并调用系统安装器。用户首次安装更新时需要允许该应用安装未知来源应用，并在系统安装器中确认。
