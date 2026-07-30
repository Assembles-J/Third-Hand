# APK 自动发布与应用内升级

合并到 `main` 后，`Deploy` 工作流会自动：

1. 使用固定签名证书构建 release APK；
2. 校验 APK 已签名；
3. 以临时文件名上传到 `/opt/third-hand/releases`；
4. 在服务器原子改名，更新 `.env` 中的版本和 APK 文件名；
5. 重建 API 容器并验证更新接口；
6. 客户端启动时检查新版本，下载后校验大小与 SHA-256，再打开 Android 系统安装器。

Android 不允许普通应用静默安装更新。第一次升级时，用户必须允许 Third-Hand“安装未知应用”，每次安装仍由系统安装器确认。

## 一次性签名配置

必须永久保留同一份 keystore。丢失后，已经安装的客户端无法再覆盖升级。

在可信电脑生成证书：

```powershell
keytool -genkeypair -v `
  -keystore third-hand-release.jks `
  -alias third-hand `
  -keyalg RSA -keysize 4096 -validity 10000

[Convert]::ToBase64String(
  [IO.File]::ReadAllBytes((Resolve-Path .\third-hand-release.jks))
) | Set-Clipboard
```

在 GitHub 仓库的 `Settings > Secrets and variables > Actions` 中配置：

| Secret | 内容 |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | keystore 文件的 Base64 |
| `ANDROID_KEYSTORE_PASSWORD` | keystore 密码 |
| `ANDROID_KEY_ALIAS` | 默认是 `third-hand` |
| `ANDROID_KEY_PASSWORD` | 私钥密码 |
| `APP_PUBLIC_BASE_URL` | 手机可访问的 HTTPS API 根地址，不带结尾 `/` |
| `SERVER_IP` | 部署服务器地址 |
| `SERVER_USER` | SSH 用户 |
| `SERVER_SSH_KEY` | SSH 私钥 |

`TUSHARE_TOKEN` 与 `DEEPSEEK_API_KEY` 保持现有配置即可。

## 首次切换正式签名

如果手机当前安装的是 Android Studio 或 CI 临时生成的 debug APK，它与正式 keystore 的签名不同，系统会提示“软件包与现有应用冲突”。第一次需要：

1. 确认后端持仓数据已备份；当前持仓在服务器 SQLite，不会随手机卸载删除。
2. 卸载手机上的 debug 版。
3. 从 GitHub Actions 的 `third-hand-<版本>` artifact 或服务器 APK 地址安装一次正式版。
4. 以后所有版本都能在应用内覆盖升级。

## 验证发布

```powershell
curl https://你的API域名/v1/app-update
curl -I https://你的API域名/v1/app-update/apk
```

元数据应包含递增的 `version_code`、版本名、`sha256` 与 `size_bytes`。APK 下载必须经 HTTPS。
