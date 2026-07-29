package com.thirdhand.app

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

data class AppUpdate(val versionCode: Int, val versionName: String, val apkUrl: String, val changelog: String)

object AppUpdateManager {
    private const val ApkMimeType = "application/vnd.android.package-archive"

    suspend fun check(context: Context): AppUpdate? = withContext(Dispatchers.IO) {
        val response = ApiClient.service(context).appUpdate()
        val update = response.body() ?: return@withContext null
        if (response.isSuccessful && update.version_code > BuildConfig.VERSION_CODE && update.apk_url.startsWith("https://")) {
            AppUpdate(update.version_code, update.version_name, update.apk_url, update.changelog)
        } else null
    }

    /** Returns false when Android needs the user to grant this app install permission first. */
    fun downloadAndInstall(context: Context, update: AppUpdate): Boolean {
        if (!context.packageManager.canRequestPackageInstalls()) {
            val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            return false
        }
        val request = DownloadManager.Request(Uri.parse(update.apkUrl))
            .setTitle("Third-Hand ${update.versionName}")
            .setDescription("正在下载更新")
            .setMimeType(ApkMimeType)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, "third-hand-${update.versionCode}.apk")
        context.getSystemService(DownloadManager::class.java).enqueue(request)
        Toast.makeText(context, "已开始下载，完成后将打开系统安装器", Toast.LENGTH_LONG).show()
        return true
    }

    fun openInstaller(context: Context, uri: Uri) {
        val installIntent = Intent(Intent.ACTION_VIEW)
            .setDataAndType(uri, ApkMimeType)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        try {
            context.startActivity(installIntent)
        } catch (_: Exception) {
            Toast.makeText(context, "无法打开安装器，请在下载完成通知中手动安装", Toast.LENGTH_LONG).show()
        }
    }
}

class AppUpdateDownloadReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != DownloadManager.ACTION_DOWNLOAD_COMPLETE) return
        val id = intent.getLongExtra(DownloadManager.EXTRA_DOWNLOAD_ID, -1L)
        if (id < 0) return
        val manager = context.getSystemService(DownloadManager::class.java)
        val cursor = manager.query(DownloadManager.Query().setFilterById(id)) ?: return
        cursor.use {
            if (!it.moveToFirst() || it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) != DownloadManager.STATUS_SUCCESSFUL) return
        }
        manager.getUriForDownloadedFile(id)?.let { uri -> AppUpdateManager.openInstaller(context, uri) }
    }
}
