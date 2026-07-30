package com.thirdhand.app

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.security.MessageDigest

data class AppUpdate(
    val versionCode: Int,
    val versionName: String,
    val apkUrl: String,
    val changelog: String,
    val sha256: String,
    val sizeBytes: Long,
)

object AppUpdateManager {
    private const val ApkMimeType = "application/vnd.android.package-archive"
    private const val Preferences = "third_hand_update"
    private const val DownloadId = "download_id"
    private const val ExpectedSha256 = "expected_sha256"
    private const val ExpectedSize = "expected_size"

    suspend fun check(context: Context): AppUpdate? = withContext(Dispatchers.IO) {
        val response = ApiClient.service(context).appUpdate()
        val update = response.body() ?: return@withContext null
        if (
            response.isSuccessful &&
            update.version_code > BuildConfig.VERSION_CODE &&
            update.apk_url.startsWith("https://") &&
            update.sha256.matches(Regex("^[a-f0-9]{64}$")) &&
            update.size_bytes > 0
        ) {
            AppUpdate(update.version_code, update.version_name, update.apk_url, update.changelog, update.sha256, update.size_bytes)
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
        val filename = "third-hand-${update.versionCode}.apk"
        File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), filename).delete()
        val request = DownloadManager.Request(Uri.parse(update.apkUrl))
            .setTitle("Third-Hand ${update.versionName}")
            .setDescription("正在下载更新")
            .setMimeType(ApkMimeType)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, filename)
        val downloadId = context.getSystemService(DownloadManager::class.java).enqueue(request)
        context.getSharedPreferences(Preferences, Context.MODE_PRIVATE).edit()
            .putLong(DownloadId, downloadId)
            .putString(ExpectedSha256, update.sha256)
            .putLong(ExpectedSize, update.sizeBytes)
            .apply()
        Toast.makeText(context, "已开始下载，完成后将打开系统安装器", Toast.LENGTH_LONG).show()
        return true
    }

    fun matchesPendingDownload(context: Context, id: Long): Boolean =
        context.getSharedPreferences(Preferences, Context.MODE_PRIVATE).getLong(DownloadId, -1L) == id

    fun verifyDownloadedApk(context: Context, uri: Uri, reportedSize: Long): Boolean {
        val preferences = context.getSharedPreferences(Preferences, Context.MODE_PRIVATE)
        val expectedSize = preferences.getLong(ExpectedSize, -1L)
        val expectedSha256 = preferences.getString(ExpectedSha256, "").orEmpty()
        if (expectedSize <= 0 || (reportedSize > 0 && reportedSize != expectedSize) || expectedSha256.length != 64) return false
        val digest = MessageDigest.getInstance("SHA-256")
        var actualSize = 0L
        context.contentResolver.openInputStream(uri)?.use { stream ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val count = stream.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
                actualSize += count
            }
        } ?: return false
        val actualSha256 = digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
        return actualSize == expectedSize && actualSha256 == expectedSha256
    }

    fun clearPendingDownload(context: Context) {
        context.getSharedPreferences(Preferences, Context.MODE_PRIVATE).edit().clear().apply()
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
        if (id < 0 || !AppUpdateManager.matchesPendingDownload(context, id)) return
        val pendingResult = goAsync()
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            try {
                handleCompletedDownload(context, id)
            } finally {
                pendingResult.finish()
            }
        }
    }

    private suspend fun handleCompletedDownload(context: Context, id: Long) {
        val manager = context.getSystemService(DownloadManager::class.java)
        val cursor = manager.query(DownloadManager.Query().setFilterById(id)) ?: return
        var totalSize = -1L
        cursor.use {
            if (!it.moveToFirst() || it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) != DownloadManager.STATUS_SUCCESSFUL) {
                AppUpdateManager.clearPendingDownload(context)
                return
            }
            totalSize = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
        }
        val uri = manager.getUriForDownloadedFile(id) ?: return
        if (!AppUpdateManager.verifyDownloadedApk(context, uri, totalSize)) {
            AppUpdateManager.clearPendingDownload(context)
            withContext(Dispatchers.Main) {
                Toast.makeText(context, "更新包校验失败，已阻止安装", Toast.LENGTH_LONG).show()
            }
            return
        }
        AppUpdateManager.clearPendingDownload(context)
        withContext(Dispatchers.Main) {
            AppUpdateManager.openInstaller(context, uri)
        }
    }
}
