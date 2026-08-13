package com.thirdhand.app

import android.app.DownloadManager
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.FileProvider
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
    VERIFYING("下载完成，正在校验安装包", true),
    FAILED("下载失败，请重新检查更新", false),
}

data class UpdateDownloadProgress(
    val state: UpdateDownloadState,
    val downloadedBytes: Long,
    val totalBytes: Long,
    val reasonCode: Int = 0,
    val message: String = state.label,
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
    private const val DownloadFilePath = "download_file_path"
    private const val SignatureMatches = "signature_matches"
    private const val AutomaticDownloadEnabled = "automatic_download_enabled"
    private const val DownloadDirectory = "Third-Hand/updates"

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
            AppUpdate(update.version_code, update.version_name, update.apk_url, update.changelog, update.sha256, update.size_bytes).also {
                reconcileStoredUpdate(context, it)
            }
        } else null
    }

    fun completedUpdateMessage(context: Context): String? {
        val completed = completedDownload(context) ?: return null
        return if (completed.signatureMatches) {
            "新版本已下载到应用专属更新目录。点击“安装更新”即可打开系统安装器。"
        } else {
            "检测到当前应用与安装包签名不同，无法直接覆盖安装。"
        }
    }

    fun hasCompletedDownload(context: Context): Boolean = completedDownload(context) != null

    fun hasCompletedDownload(context: Context, update: AppUpdate): Boolean =
        storedUpdateMatches(context, update) && completedDownload(context) != null

    fun hasActiveDownload(context: Context, update: AppUpdate): Boolean =
        storedUpdateMatches(context, update) && downloadProgress(context)?.state?.isActive == true

    fun automaticDownloadEnabled(context: Context): Boolean =
        preferences(context).getBoolean(AutomaticDownloadEnabled, true)

    fun setAutomaticDownloadEnabled(context: Context, enabled: Boolean) {
        preferences(context).edit().putBoolean(AutomaticDownloadEnabled, enabled).apply()
    }

    /** Enqueues once when the current connection is Wi-Fi; the task survives UI dismissal. */
    fun downloadAutomaticallyOnWifi(context: Context, update: AppUpdate): UpdateLaunchResult? {
        if (!automaticDownloadEnabled(context) || !isOnWifi(context) || hasCompletedDownload(context, update)) return null
        val existing = downloadProgress(context)
        if (storedUpdateMatches(context, update) && existing?.state?.isActive == true) return null
        return startDownload(context, update, wifiOnly = true)
    }

    /** Returns the system download's latest byte counts so Compose can show in-app progress. */
    fun downloadProgress(context: Context): UpdateDownloadProgress? {
        if (completedDownload(context) != null) return null
        val id = preferences(context).getLong(DownloadId, -1L)
        if (id < 0) return null
        val manager = context.getSystemService(DownloadManager::class.java)
        val cursor = manager.query(DownloadManager.Query().setFilterById(id)) ?: return null
        cursor.use {
            if (!it.moveToFirst()) return null
            val status = it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
            val reason = it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
            val state = when (status) {
                DownloadManager.STATUS_PENDING -> UpdateDownloadState.PENDING
                DownloadManager.STATUS_RUNNING -> UpdateDownloadState.DOWNLOADING
                DownloadManager.STATUS_PAUSED -> UpdateDownloadState.PAUSED
                DownloadManager.STATUS_SUCCESSFUL -> UpdateDownloadState.VERIFYING
                else -> UpdateDownloadState.FAILED
            }
            val message = if (status == DownloadManager.STATUS_PAUSED) {
                when (reason) {
                    DownloadManager.PAUSED_QUEUED_FOR_WIFI -> "等待可用的 Wi‑Fi 网络"
                    DownloadManager.PAUSED_WAITING_FOR_NETWORK -> "网络暂时不可用，等待恢复"
                    DownloadManager.PAUSED_WAITING_TO_RETRY -> "下载暂时中断，系统即将重试"
                    else -> state.label
                }
            } else state.label
            return UpdateDownloadProgress(
                state = state,
                downloadedBytes = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)).coerceAtLeast(0L),
                totalBytes = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES)).coerceAtLeast(0L),
                reasonCode = reason,
                message = message,
            )
        }
    }

    /**
     * Reconciles DownloadManager with app-owned verification state.
     *
     * Some OEMs delay or drop ACTION_DOWNLOAD_COMPLETE until the system
     * notification is opened. Polling must therefore be able to finish SHA-256
     * and signature verification without relying on that broadcast.
     */
    suspend fun refreshDownloadState(context: Context): UpdateDownloadProgress? = withContext(Dispatchers.IO) {
        val progress = downloadProgress(context)
        if (progress?.state != UpdateDownloadState.VERIFYING) return@withContext progress
        val id = preferences(context).getLong(DownloadId, -1L)
        val verified = id >= 0 && finalizeSuccessfulDownload(context, id)
        if (verified) downloadProgress(context) else progress.copy(
            state = UpdateDownloadState.FAILED,
            message = "安装包校验失败，请重新下载",
        )
    }

    /** Starts a manual download or opens an already verified installer. Android still requires user confirmation. */
    fun downloadAndInstall(context: Context, update: AppUpdate): UpdateLaunchResult {
        if (hasCompletedDownload(context, update)) return installDownloadedUpdate(context)
        if (hasActiveDownload(context, update)) return UpdateLaunchResult.DOWNLOAD_STARTED
        return startDownload(context, update, wifiOnly = false)
    }

    fun installDownloadedUpdate(context: Context): UpdateLaunchResult {
        val completed = completedDownload(context) ?: return UpdateLaunchResult.DOWNLOAD_UNAVAILABLE
        if (!completed.signatureMatches) {
            Toast.makeText(context, completedUpdateMessage(context), Toast.LENGTH_LONG).show()
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

    private fun startDownload(context: Context, update: AppUpdate, wifiOnly: Boolean): UpdateLaunchResult {
        val manager = context.getSystemService(DownloadManager::class.java)
        clearPreviousDownload(context, manager)
        val filename = "third-hand-${update.versionName}-${update.versionCode}.apk"
        val destination = updateFile(context, filename)
        destination.parentFile?.mkdirs()
        destination.delete()
        val request = DownloadManager.Request(Uri.parse(update.apkUrl))
            .setTitle("Third-Hand ${update.versionName}")
            .setDescription("正在下载更新，完成后可在管理页面安装")
            .setMimeType(ApkMimeType)
            // isOnWifi() gates automatic enqueueing. Avoid OEM-specific post-enqueue
            // Wi-Fi constraints that can leave a valid task permanently paused.
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // DownloadManager is a MediaProvider client on modern Android.
            // Several OEM providers reject Android/data private destinations.
            request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, "$DownloadDirectory/$filename")
        } else {
            request.setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, "updates/$filename")
        }
        val downloadId = runCatching { manager.enqueue(request) }.getOrElse {
            Toast.makeText(context, "无法创建下载任务：${it.message ?: "请检查存储空间和下载地址"}", Toast.LENGTH_LONG).show()
            return UpdateLaunchResult.DOWNLOAD_UNAVAILABLE
        }
        preferences(context).edit()
            .putLong(DownloadId, downloadId)
            .putLong(CompletedDownloadId, -1L)
            .putString(ExpectedSha256, update.sha256)
            .putLong(ExpectedSize, update.sizeBytes)
            .putInt(ExpectedVersionCode, update.versionCode)
            .putString(ExpectedVersionName, update.versionName)
            .putString(DownloadFilename, filename)
            .putString(DownloadFilePath, destination.absolutePath)
            .remove(SignatureMatches)
            .apply()
        Toast.makeText(
            context,
            if (wifiOnly) "已在 Wi‑Fi 下开始后台下载，完成后可在管理页面安装" else "已开始后台下载，完成后可在管理页面安装",
            Toast.LENGTH_LONG,
        ).show()
        return UpdateLaunchResult.DOWNLOAD_STARTED
    }

    private fun isOnWifi(context: Context): Boolean {
        val manager = context.getSystemService(ConnectivityManager::class.java)
        val network = manager.activeNetwork ?: return false
        return manager.getNetworkCapabilities(network)?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true
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
        storedUpdateFile(context)?.delete()
        clearDownloadPreferences(context)
    }

    suspend fun finalizeSuccessfulDownload(context: Context, id: Long): Boolean = withContext(Dispatchers.IO) {
        if (!matchesPendingDownload(context, id)) return@withContext false
        if (preferences(context).getLong(CompletedDownloadId, -1L) == id && completedDownload(context) != null) {
            return@withContext true
        }
        val manager = context.getSystemService(DownloadManager::class.java)
        val cursor = manager.query(DownloadManager.Query().setFilterById(id)) ?: return@withContext false
        var totalSize = -1L
        cursor.use {
            if (!it.moveToFirst()) return@withContext false
            if (it.getInt(it.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)) != DownloadManager.STATUS_SUCCESSFUL) {
                return@withContext false
            }
            totalSize = it.getLong(it.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
        }
        val file = storedUpdateFile(context)
        if (file == null || !file.isFile) return@withContext false
        val uri = runCatching { FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file) }.getOrNull()
            ?: return@withContext false
        if (!verifyDownloadedApk(context, uri, totalSize)) {
            clearFailedDownload(context, id)
            return@withContext false
        }
        markDownloadCompleted(context, id, signaturesMatchInstalledApp(context, uri))
        true
    }

    fun openInstaller(context: Context, uri: Uri): Boolean {
        val installIntent = Intent(Intent.ACTION_INSTALL_PACKAGE).apply {
            data = uri
            clipData = ClipData.newRawUri("update_apk", uri)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        return try {
            context.startActivity(installIntent)
            true
        } catch (_: Exception) {
            Toast.makeText(
                context,
                "无法打开安装器。安装包仍保留在“下载/Third-Hand/updates”，可手动点击安装。",
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
        runCatching { context.startActivity(intent) }.onFailure {
            Toast.makeText(context, "无法打开安装权限设置，请在系统设置中允许本应用安装未知来源应用。", Toast.LENGTH_LONG).show()
        }
    }

    private fun completedDownload(context: Context): CompletedDownload? {
        val preferences = preferences(context)
        val id = preferences.getLong(CompletedDownloadId, -1L)
        if (id < 0 || !preferences.contains(SignatureMatches)) return null
        val file = storedUpdateFile(context) ?: return null
        val expectedSize = preferences.getLong(ExpectedSize, -1L)
        if (!file.isFile || expectedSize <= 0 || file.length() != expectedSize) return null
        val uri = runCatching { FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file) }.getOrNull()
            ?: return null
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
        storedUpdateFile(context)?.delete()
        clearDownloadPreferences(context)
    }

    private fun reconcileStoredUpdate(context: Context, update: AppUpdate) {
        val manager = context.getSystemService(DownloadManager::class.java)
        if (preferences(context).contains(ExpectedVersionCode) && !storedUpdateMatches(context, update)) {
            clearPreviousDownload(context, manager)
        }
        val expectedName = "third-hand-${update.versionName}-${update.versionCode}.apk"
        updateDirectory(context).listFiles()
            ?.filter { it.isFile && it.name != expectedName }
            ?.forEach { it.delete() }
    }

    private fun storedUpdateMatches(context: Context, update: AppUpdate): Boolean {
        val preferences = preferences(context)
        val expectedFile = updateFile(context, "third-hand-${update.versionName}-${update.versionCode}.apk")
        return preferences.getInt(ExpectedVersionCode, -1) == update.versionCode &&
            preferences.getString(ExpectedVersionName, null) == update.versionName &&
            preferences.getString(ExpectedSha256, null) == update.sha256 &&
            preferences.getLong(ExpectedSize, -1L) == update.sizeBytes &&
            preferences.getString(DownloadFilePath, null) == expectedFile.absolutePath
    }

    @Suppress("DEPRECATION")
    private fun updateDirectory(context: Context): File =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS), DownloadDirectory)
        } else {
            File(requireNotNull(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)), "updates")
        }.also { it.mkdirs() }

    private fun updateFile(context: Context, filename: String): File = File(updateDirectory(context), filename)

    private fun storedUpdateFile(context: Context): File? {
        val storedPath = preferences(context).getString(DownloadFilePath, null) ?: return null
        val file = File(storedPath)
        return try {
            file.canonicalFile.takeIf { candidate ->
                candidate.toPath().startsWith(updateDirectory(context).canonicalFile.toPath())
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun clearPreviousDownload(context: Context, manager: DownloadManager) {
        val preferences = preferences(context)
        val ids = setOf(
            preferences.getLong(DownloadId, -1L),
            preferences.getLong(CompletedDownloadId, -1L),
        ).filter { it >= 0 }.toLongArray()
        if (ids.isNotEmpty()) manager.remove(*ids)
        storedUpdateFile(context)?.delete()
        clearDownloadPreferences(context)
    }

    private fun clearDownloadPreferences(context: Context) {
        preferences(context).edit()
            .remove(DownloadId)
            .remove(CompletedDownloadId)
            .remove(ExpectedSha256)
            .remove(ExpectedSize)
            .remove(ExpectedVersionCode)
            .remove(ExpectedVersionName)
            .remove(DownloadFilename)
            .remove(DownloadFilePath)
            .remove(SignatureMatches)
            .apply()
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
        val progress = AppUpdateManager.downloadProgress(context)
        if (progress?.state == UpdateDownloadState.FAILED) {
            AppUpdateManager.clearFailedDownload(context, id)
            return
        }
        if (progress?.state == UpdateDownloadState.VERIFYING && !AppUpdateManager.finalizeSuccessfulDownload(context, id)) {
            withContext(Dispatchers.Main) {
                Toast.makeText(context, "更新包校验失败，文件已删除并阻止安装", Toast.LENGTH_LONG).show()
            }
        }
    }
}
