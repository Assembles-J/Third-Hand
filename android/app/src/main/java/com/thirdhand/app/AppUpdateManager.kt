package com.thirdhand.app

import android.Manifest
import android.app.Activity
import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
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

enum class UpdateLaunchResult {
    DOWNLOAD_STARTED,
    INSTALLER_OPENED,
    NEED_INSTALL_PERMISSION,
    NEED_STORAGE_PERMISSION,
    SIGNATURE_MISMATCH,
    DOWNLOAD_UNAVAILABLE,
}

enum class UpdateDownloadState(val label: String, val isActive: Boolean) {
    PENDING("等待下载", true),
    DOWNLOADING("正在下载", true),
    PAUSED("下载已暂停，等待网络恢复", true),
    VERIFYING("下载完成，正在校验安装包", false),
    FAILED("下载失败，请重新检查更新", false),
}

data class UpdateDownloadProgress(
    val state: UpdateDownloadState,
    val downloadedBytes: Long,
    val totalBytes: Long,
) {
    val fraction: Float? = totalBytes.takeIf { it > 0 }
        ?.let { (downloadedBytes.toDouble() / it).coerceIn(0.0, 1.0).toFloat() }
}

private data class CompletedDownload(
    val id: Long,
    val uri: Uri,
    val signatureMatches: Boolean,
    val filename: String,
)

object AppUpdateManager {
    private const val ApkMimeType = "application/vnd.android.package-archive"
    private const val Preferences = "third_hand_update"
    private const val DownloadId = "download_id"
    private const val CompletedDownloadId = "completed_download_id"
    private const val ExpectedSha256 = "expected_sha256"
    private const val ExpectedSize = "expected_size"
    private const val ExpectedVersionCode = "expected_version_code"
    private const val ExpectedVersionName = "expected_version_name"
    private const val DownloadFilename = "download_filename"
    private const val SignatureMatches = "signature_matches"
    private const val DownloadDirectory = "Third-Hand"
    private const val StoragePermissionRequest = 9042

    suspend fun check(context: Context): AppUpdate? = withContext(Dispatchers.IO) {
        // Debug builds are deliberately signed and versioned separately from
        // production releases; they must never receive a production APK prompt.
        if (BuildConfig.DEBUG) return@withContext null
        cleanupInstalledUpdate(context)
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

    fun completedUpdateMessage(context: Context): String? {
        val completed = completedDownload(context) ?: return null
        return if (completed.signatureMatches) {
            "安装包已下载到“下载/$DownloadDirectory/${completed.filename}”。点击“继续安装”可重新打开系统安装器。"
        } else {
            "检测到当前应用与正式版签名不同。安装包已保留在“下载/$DownloadDirectory/${completed.filename}”。请先卸载当前旧版，再从该目录安装正式版；以后即可直接覆盖升级。"
        }
    }

    fun hasCompletedDownload(context: Context): Boolean = completedDownload(context) != null

    /** Returns the system download's latest byte counts so Compose can show in-app progress. */
    fun downloadProgress(context: Context): UpdateDownloadProgress? {
        if (completedDownload(context) != null) return null
        val id = preferences(context).getLong(DownloadId, -1L)
        if (id < 0) return null
        val manager = context.getSystemService(DownloadManager::class.java)
        val cursor = manager.query(DownloadManager.Query().setFilterById(id)) ?: return null
        cursor.use {
            if (!it.moveToFirst()) return null
            val state = when (it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))) {
                DownloadManager.STATUS_PENDING -> UpdateDownloadState.PENDING
                DownloadManager.STATUS_RUNNING -> UpdateDownloadState.DOWNLOADING
                DownloadManager.STATUS_PAUSED -> UpdateDownloadState.PAUSED
                DownloadManager.STATUS_SUCCESSFUL -> UpdateDownloadState.VERIFYING
                else -> UpdateDownloadState.FAILED
            }
            return UpdateDownloadProgress(
                state = state,
                downloadedBytes = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)).coerceAtLeast(0L),
                totalBytes = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES)).coerceAtLeast(0L),
            )
        }
    }

    /** Starts a download or reopens a verified download. Android still requires user confirmation. */
    fun downloadAndInstall(context: Context, update: AppUpdate): UpdateLaunchResult {
        completedDownload(context)?.let { completed ->
            if (!completed.signatureMatches) {
                Toast.makeText(context, completedUpdateMessage(context), Toast.LENGTH_LONG).show()
                openDownloads(context)
                return UpdateLaunchResult.SIGNATURE_MISMATCH
            }
            if (!context.packageManager.canRequestPackageInstalls()) {
                requestInstallPermission(context)
                return UpdateLaunchResult.NEED_INSTALL_PERMISSION
            }
            return if (openInstaller(context, completed.uri)) {
                UpdateLaunchResult.INSTALLER_OPENED
            } else {
                UpdateLaunchResult.DOWNLOAD_UNAVAILABLE
            }
        }

        if (!context.packageManager.canRequestPackageInstalls()) {
            requestInstallPermission(context)
            return UpdateLaunchResult.NEED_INSTALL_PERMISSION
        }
        if (
            Build.VERSION.SDK_INT <= Build.VERSION_CODES.P &&
            context.checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED
        ) {
            (context as? Activity)?.requestPermissions(
                arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE),
                StoragePermissionRequest,
            )
            return UpdateLaunchResult.NEED_STORAGE_PERMISSION
        }

        val manager = context.getSystemService(DownloadManager::class.java)
        clearPreviousDownload(context, manager)
        val filename = "third-hand-${update.versionCode}.apk"
        val destination = File(
            Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS),
            "$DownloadDirectory/$filename",
        )
        destination.parentFile?.mkdirs()
        destination.delete()
        val request = DownloadManager.Request(Uri.parse(update.apkUrl))
            .setTitle("Third-Hand ${update.versionName}")
            .setDescription("正在下载更新，完成后将打开系统安装器")
            .setMimeType(ApkMimeType)
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "$DownloadDirectory/$filename")
        val downloadId = manager.enqueue(request)
        preferences(context).edit()
            .putLong(DownloadId, downloadId)
            .putLong(CompletedDownloadId, -1L)
            .putString(ExpectedSha256, update.sha256)
            .putLong(ExpectedSize, update.sizeBytes)
            .putInt(ExpectedVersionCode, update.versionCode)
            .putString(ExpectedVersionName, update.versionName)
            .putString(DownloadFilename, filename)
            .remove(SignatureMatches)
            .apply()
        Toast.makeText(
            context,
            "正在下载到“下载/$DownloadDirectory/$filename”，完成后将自动打开安装器",
            Toast.LENGTH_LONG,
        ).show()
        return UpdateLaunchResult.DOWNLOAD_STARTED
    }

    fun matchesPendingDownload(context: Context, id: Long): Boolean =
        preferences(context).getLong(DownloadId, -1L) == id

    fun verifyDownloadedApk(context: Context, uri: Uri, reportedSize: Long): Boolean {
        val preferences = preferences(context)
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

    fun signaturesMatchInstalledApp(context: Context, uri: Uri): Boolean {
        val temporaryApk = File(context.cacheDir, "third-hand-signature-check.apk")
        return try {
            context.contentResolver.openInputStream(uri)?.use { input ->
                temporaryApk.outputStream().use { output -> input.copyTo(output) }
            } ?: return false
            val packageManager = context.packageManager
            val archive = packageInfoFromArchive(packageManager, temporaryApk) ?: return false
            if (archive.packageName != context.packageName) return false
            val installed = packageInfoForInstalledApp(packageManager, context.packageName)
            val archiveSigners = signerCertificates(archive, archive = true)
            val installedSigners = signerCertificates(installed, archive = false)
            archiveSigners.isNotEmpty() && archiveSigners.any { candidate ->
                installedSigners.any { installedCertificate -> candidate.contentEquals(installedCertificate) }
            }
        } catch (_: Exception) {
            false
        } finally {
            temporaryApk.delete()
        }
    }

    fun markDownloadCompleted(context: Context, id: Long, signatureMatches: Boolean) {
        preferences(context).edit()
            .putLong(CompletedDownloadId, id)
            .putBoolean(SignatureMatches, signatureMatches)
            .apply()
    }

    fun clearFailedDownload(context: Context, id: Long) {
        context.getSystemService(DownloadManager::class.java).remove(id)
        preferences(context).edit().clear().apply()
    }

    fun openInstaller(context: Context, uri: Uri): Boolean {
        val installIntent = Intent(Intent.ACTION_INSTALL_PACKAGE)
            .setData(uri)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        return try {
            context.startActivity(installIntent)
            true
        } catch (_: Exception) {
            Toast.makeText(
                context,
                "无法打开安装器。安装包仍保留在“下载/$DownloadDirectory”，可手动点击安装。",
                Toast.LENGTH_LONG,
            ).show()
            false
        }
    }

    private fun requestInstallPermission(context: Context) {
        val intent = Intent(
            Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
            Uri.parse("package:${context.packageName}"),
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    private fun openDownloads(context: Context) {
        try {
            context.startActivity(
                Intent(DownloadManager.ACTION_VIEW_DOWNLOADS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            )
        } catch (_: Exception) {
            Toast.makeText(context, "请打开系统文件管理器中的“下载/$DownloadDirectory”目录", Toast.LENGTH_LONG).show()
        }
    }

    private fun completedDownload(context: Context): CompletedDownload? {
        val preferences = preferences(context)
        val id = preferences.getLong(CompletedDownloadId, -1L)
        if (id < 0 || !preferences.contains(SignatureMatches)) return null
        val manager = context.getSystemService(DownloadManager::class.java)
        val cursor = manager.query(DownloadManager.Query().setFilterById(id)) ?: return null
        cursor.use {
            if (!it.moveToFirst()) return null
            if (it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) != DownloadManager.STATUS_SUCCESSFUL) return null
        }
        val uri = manager.getUriForDownloadedFile(id) ?: return null
        return CompletedDownload(
            id = id,
            uri = uri,
            signatureMatches = preferences.getBoolean(SignatureMatches, false),
            filename = preferences.getString(DownloadFilename, "third-hand.apk").orEmpty(),
        )
    }

    private fun cleanupInstalledUpdate(context: Context) {
        val preferences = preferences(context)
        val expectedVersionCode = preferences.getInt(ExpectedVersionCode, -1)
        if (expectedVersionCode <= 0 || BuildConfig.VERSION_CODE < expectedVersionCode) return
        val manager = context.getSystemService(DownloadManager::class.java)
        val ids = setOf(
            preferences.getLong(DownloadId, -1L),
            preferences.getLong(CompletedDownloadId, -1L),
        ).filter { it >= 0 }.toLongArray()
        if (ids.isNotEmpty()) manager.remove(*ids)
        preferences.edit().clear().apply()
    }

    private fun clearPreviousDownload(context: Context, manager: DownloadManager) {
        val preferences = preferences(context)
        val ids = setOf(
            preferences.getLong(DownloadId, -1L),
            preferences.getLong(CompletedDownloadId, -1L),
        ).filter { it >= 0 }.toLongArray()
        if (ids.isNotEmpty()) manager.remove(*ids)
        preferences.edit().clear().apply()
    }

    private fun preferences(context: Context) =
        context.getSharedPreferences(Preferences, Context.MODE_PRIVATE)

    @Suppress("DEPRECATION")
    private fun packageInfoFromArchive(packageManager: PackageManager, apk: File): PackageInfo? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            packageManager.getPackageArchiveInfo(
                apk.absolutePath,
                PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()),
            )
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            packageManager.getPackageArchiveInfo(apk.absolutePath, PackageManager.GET_SIGNING_CERTIFICATES)
        } else {
            packageManager.getPackageArchiveInfo(apk.absolutePath, PackageManager.GET_SIGNATURES)
        }

    @Suppress("DEPRECATION")
    private fun packageInfoForInstalledApp(packageManager: PackageManager, packageName: String): PackageInfo =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            packageManager.getPackageInfo(
                packageName,
                PackageManager.PackageInfoFlags.of(PackageManager.GET_SIGNING_CERTIFICATES.toLong()),
            )
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES)
        } else {
            packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNATURES)
        }

    @Suppress("DEPRECATION")
    private fun signerCertificates(packageInfo: PackageInfo, archive: Boolean): List<ByteArray> {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val signingInfo = packageInfo.signingInfo ?: return emptyList()
            val signatures = if (archive || signingInfo.hasMultipleSigners()) {
                signingInfo.apkContentsSigners
            } else {
                signingInfo.signingCertificateHistory
            }
            signatures.map { it.toByteArray() }
        } else {
            packageInfo.signatures.orEmpty().map { it.toByteArray() }
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
            if (
                !it.moveToFirst() ||
                it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) != DownloadManager.STATUS_SUCCESSFUL
            ) {
                AppUpdateManager.clearFailedDownload(context, id)
                return
            }
            totalSize = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
        }
        val uri = manager.getUriForDownloadedFile(id) ?: return
        if (!AppUpdateManager.verifyDownloadedApk(context, uri, totalSize)) {
            AppUpdateManager.clearFailedDownload(context, id)
            withContext(Dispatchers.Main) {
                Toast.makeText(context, "更新包校验失败，文件已删除并阻止安装", Toast.LENGTH_LONG).show()
            }
            return
        }

        val signatureMatches = AppUpdateManager.signaturesMatchInstalledApp(context, uri)
        AppUpdateManager.markDownloadCompleted(context, id, signatureMatches)
        withContext(Dispatchers.Main) {
            if (signatureMatches) {
                AppUpdateManager.openInstaller(context, uri)
            } else {
                Toast.makeText(
                    context,
                    AppUpdateManager.completedUpdateMessage(context),
                    Toast.LENGTH_LONG,
                ).show()
            }
        }
    }
}
