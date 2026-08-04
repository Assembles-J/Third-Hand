package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudSync
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Button
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val CompactCanvas = Color(0xFF111614)
private val CompactPanel = Color(0xFF171E1B)
private val CompactMint = Color(0xFF9EFFBF)
private val CompactTeal = Color(0xFF4ED6C2)
private val CompactGold = Color(0xFFF4D35E)
private val CompactCoral = Color(0xFFFF8C69)
private val CompactText = Color(0xFFE7EEE9)
private val CompactQuiet = Color(0xFF9DA9A3)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CompactAdminDashboardScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    var refreshKey by remember { mutableIntStateOf(0) }
    var overview by remember { mutableStateOf<AdminOverviewDto?>(null) }
    var config by remember { mutableStateOf<SystemConfigDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var savingConfig by remember { mutableStateOf(false) }
    var baseUrl by remember { mutableStateOf(EndpointStore.baseUrl(context)) }
    var connectionStatus by remember { mutableStateOf<String?>(null) }
    var updateStatus by remember { mutableStateOf<String?>(null) }
    var checkingUpdate by remember { mutableStateOf(false) }
    var availableUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var updateProgress by remember { mutableStateOf<UpdateDownloadProgress?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(refreshKey) {
        error = null
        runCatching { api.adminOverview() }
            .onSuccess { overview = it }
            .onFailure { error = "无法读取系统状态，请检查服务连接。" }
        runCatching { api.adminConfig() }.onSuccess { config = it }
    }
    LaunchedEffect(availableUpdate) {
        val update = availableUpdate ?: return@LaunchedEffect
        while (true) {
            val current = AppUpdateManager.refreshDownloadState(context)
            updateProgress = current
            if (current?.state?.isActive != true) {
                updateStatus = when {
                    AppUpdateManager.hasCompletedDownload(context, update) ->
                        "更新包已准备好，点击“下载或安装更新”前往系统安装"
                    current?.state == UpdateDownloadState.FAILED -> current.message
                    else -> updateStatus
                }
                break
            }
            delay(500)
        }
    }
    Column(
        Modifier.fillMaxWidth().background(CompactCanvas).verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("系统管理", color = CompactText, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text("数据状态与安全配置", color = CompactQuiet, style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace)
            }
            IconButton(onClick = { refreshKey += 1 }) { Icon(Icons.Filled.Refresh, "刷新系统状态", tint = CompactMint) }
        }
        error?.let { CompactConsoleCard { Text(it, color = CompactCoral, style = MaterialTheme.typography.bodySmall) } }
        CompactMetricGrid(overview)
        MarketRefreshCard(overview)
        PendingReviewCard(overview)
        ApplicationDataGrid(overview)
        CompactConsoleCard {
            Text("服务与 APK 下载地址", color = CompactText, fontWeight = FontWeight.Bold)
            Text("应用更新和 APK 下载均通过此服务地址的 /v1/app-update 获取。", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
            OutlinedTextField(
                value = baseUrl,
                onValueChange = { baseUrl = it },
                label = { Text("服务地址，例如 http://192.168.1.10:8000/", color = Color.White) },
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                singleLine = true,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = CompactText,
                    unfocusedTextColor = CompactText,
                    focusedLabelColor = CompactMint,
                    unfocusedLabelColor = CompactQuiet,
                    focusedBorderColor = CompactMint,
                    unfocusedBorderColor = CompactQuiet,
                    cursorColor = CompactMint,
                    focusedContainerColor = CompactPanel,
                    unfocusedContainerColor = CompactPanel,
                ),
            )
            TextButton(onClick = {
                EndpointStore.saveBaseUrl(context, baseUrl)
                scope.launch {
                    connectionStatus = runCatching { ApiClient.service(context).health().status }
                        .fold({ if (it == "ok") "连接成功" else "服务返回：$it" }, { "连接失败：${it.message ?: "请检查地址和网络"}" })
                }
            }) { Text("保存并测试连接", color = CompactMint) }
            connectionStatus?.let { Text(it, color = if (it == "连接成功") CompactMint else CompactCoral, style = MaterialTheme.typography.labelSmall) }
        }
        CompactConsoleCard {
            Text("应用更新", color = CompactText, fontWeight = FontWeight.Bold)
            Text("当前版本 v${BuildConfig.VERSION_NAME}。更新包由系统服务下发并校验签名。", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
            TextButton(enabled = !checkingUpdate, onClick = {
                scope.launch {
                    checkingUpdate = true
                    updateStatus = runCatching { AppUpdateManager.check(context) }.fold(
                        onSuccess = { update ->
                            availableUpdate = update
                            updateProgress = update?.let { AppUpdateManager.refreshDownloadState(context) }
                            if (update == null) "已是最新版本" else "发现 ${update.versionName}，准备下载"
                        },
                        onFailure = { "检查更新失败：${it.message ?: "请检查服务地址和网络"}" },
                    )
                    availableUpdate?.let { update ->
                        updateStatus = when (AppUpdateManager.downloadAndInstall(context, update)) {
                            UpdateLaunchResult.DOWNLOAD_STARTED -> "正在下载 ${update.versionName}；进度会在这里实时更新"
                            UpdateLaunchResult.INSTALLER_OPENED -> "已进入系统安装页；安装完成后点击“打开”即可直接进入新版"
                            UpdateLaunchResult.NEED_INSTALL_PERMISSION -> "请允许安装未知应用后重试"
                            UpdateLaunchResult.NEED_STORAGE_PERMISSION -> "请允许保存安装包后重试"
                            UpdateLaunchResult.SIGNATURE_MISMATCH -> AppUpdateManager.completedUpdateMessage(context)
                            UpdateLaunchResult.DOWNLOAD_UNAVAILABLE -> "APK 下载地址不可用，请检查发布配置"
                        }
                    }
                    checkingUpdate = false
                }
            }) { Text(if (checkingUpdate) "正在检查…" else if (availableUpdate != null) "下载或安装更新" else "检查更新", color = CompactMint) }
            updateProgress?.let { progress -> CompactUpdateDownloadProgress(progress) }
            updateStatus?.let { Text(it, color = if (it.contains("失败") || it.contains("不可用")) CompactCoral else CompactTeal, style = MaterialTheme.typography.labelSmall) }
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            CompactConsoleCard(Modifier.weight(1f).widthIn(min = 150.dp)) {
                Text("资源容量", color = CompactText, fontWeight = FontWeight.Bold)
                Text("SQLite ${compactBytes((overview?.database_bytes ?: 0).toLong())}", color = CompactTeal, style = MaterialTheme.typography.labelMedium)
                Text("内容 ${overview?.cached_content_count ?: 0} 条", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
            }
            CompactConsoleCard(Modifier.weight(1f).widthIn(min = 150.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Settings, null, tint = CompactMint)
                    Text(" 系统配置", color = CompactText, fontWeight = FontWeight.Bold)
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("提示应用更新", color = CompactText, style = MaterialTheme.typography.bodySmall)
                        Text("关闭后服务端不再下发新版本", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
                    }
                    Switch(
                        checked = config?.update_check_enabled ?: false,
                        enabled = config != null && !savingConfig,
                        onCheckedChange = { enabled -> scope.launch {
                            savingConfig = true
                            runCatching { api.saveAdminConfig(SystemConfigDto(enabled)) }
                                .onSuccess { config = it }
                                .onFailure { error = "保存系统配置失败：${it.message ?: "请稍后重试"}" }
                            savingConfig = false
                        } },
                    )
                }
                Text("Debug 包始终不会提示安装正式版。", color = CompactTeal, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun CompactUpdateDownloadProgress(progress: UpdateDownloadProgress) {
    val percentage = progress.fraction?.let { " ${(it * 100).toInt()}%" }.orEmpty()
    val size = if (progress.totalBytes > 0) {
        " · ${compactBytes(progress.downloadedBytes)} / ${compactBytes(progress.totalBytes)}"
    } else ""
    Text("${progress.message}$percentage$size", color = CompactText, style = MaterialTheme.typography.labelSmall)
    if (progress.fraction != null) {
        LinearProgressIndicator(
            progress = { progress.fraction },
            modifier = Modifier.fillMaxWidth(),
            color = CompactMint,
            trackColor = CompactPanel,
        )
    } else if (progress.state.isActive) {
        LinearProgressIndicator(
            modifier = Modifier.fillMaxWidth(),
            color = CompactMint,
            trackColor = CompactPanel,
        )
    }
}

@Composable
private fun MarketRefreshCard(overview: AdminOverviewDto?) = CompactConsoleCard {
    Text("行情定时任务", color = CompactText, fontWeight = FontWeight.Bold)
    val running = overview?.market_worker_running == true
    Text(
        if (running) "运行中 · 每 ${overview?.market_refresh_interval_seconds ?: "—"} 秒拉取并入库"
        else "未运行 · 请检查 MARKET_REFRESH_ENABLED",
        color = if (running) CompactMint else CompactCoral,
        style = MaterialTheme.typography.bodySmall,
    )
    Text("最新入库：${overview?.latest_market_at ?: "暂无"}", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
    Text("最新快照 ${overview?.cached_quotes_count ?: 0} 条 · 历史快照 ${overview?.market_history_count ?: 0} 条", color = CompactTeal, style = MaterialTheme.typography.labelSmall)
    overview?.market_last_error?.let { Text("最近失败：$it", color = CompactCoral, style = MaterialTheme.typography.labelSmall) }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CompactMetricGrid(overview: AdminOverviewDto?) = FlowRow(
    horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp),
) {
    CompactMetric("API", if (overview?.status == "ok") "在线" else "—", "服务状态", CompactMint, Modifier.weight(1f))
    CompactMetric("待核验", "${overview?.pending_draft_count ?: 0}", "持仓草稿", CompactGold, Modifier.weight(1f))
    CompactMetric("持仓", "${overview?.holdings_count ?: 0}", "已入库", CompactMint, Modifier.weight(1f))
    CompactMetric("行情", "${overview?.cached_quotes_count ?: 0}", "缓存快照", CompactTeal, Modifier.weight(1f))
}

@Composable
private fun PendingReviewCard(overview: AdminOverviewDto?) = CompactConsoleCard {
    val pending = overview?.pending_draft_count ?: 0
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Filled.WarningAmber, null, tint = if (pending > 0) CompactGold else CompactMint)
        Column(Modifier.weight(1f).padding(start = 10.dp)) {
            Text(if (pending > 0) "$pending 条持仓草稿待核验" else "没有待核验项目", color = CompactText, fontWeight = FontWeight.SemiBold)
            Text("补全证券代码后即可确认入库。", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
        }
        TextButton(onClick = {}) { Text("查看", color = CompactMint) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ApplicationDataGrid(overview: AdminOverviewDto?) = CompactConsoleCard {
    Text("应用数据状态", color = CompactText, fontWeight = FontWeight.Bold)
    Text("数量与最新缓存状态", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 10.dp)) {
        CompactMetric("持仓", "${overview?.holdings_count ?: 0}", "已入库", CompactMint, Modifier.weight(1f), Icons.Filled.Security)
        CompactMetric("行情", "${overview?.cached_quotes_count ?: 0}", "本地快照", CompactTeal, Modifier.weight(1f), Icons.Filled.Memory)
        CompactMetric("草稿", "${overview?.draft_count ?: 0}", "${overview?.pending_draft_count ?: 0} 待处理", CompactGold, Modifier.weight(1f), Icons.Filled.CloudSync)
        CompactMetric("内容", "${overview?.cached_content_count ?: 0}", "已缓存", CompactMint, Modifier.weight(1f))
    }
}

@Composable
private fun CompactMetric(label: String, value: String, hint: String, accent: Color, modifier: Modifier, icon: androidx.compose.ui.graphics.vector.ImageVector? = null) = CompactConsoleCard(modifier.widthIn(min = 140.dp)) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        icon?.let { Icon(it, null, tint = accent) }
        Text(label, color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
    }
    Text(value, color = CompactText, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
    Text(hint, color = accent, style = MaterialTheme.typography.labelSmall)
}

@Composable
private fun CompactConsoleCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) = Card(
    modifier = modifier,
    colors = CardDefaults.cardColors(containerColor = CompactPanel),
    shape = MaterialTheme.shapes.extraSmall,
) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { content() } }

private fun compactBytes(bytes: Long): String = when {
    bytes >= 1_048_576 -> "%.1f MB".format(bytes / 1_048_576.0)
    bytes >= 1_024 -> "%.1f KB".format(bytes / 1_024.0)
    else -> "$bytes B"
}
