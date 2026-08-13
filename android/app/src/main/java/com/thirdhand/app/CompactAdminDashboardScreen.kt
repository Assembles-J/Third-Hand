package com.thirdhand.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun CompactAdminDashboardScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var refreshKey by remember { mutableIntStateOf(0) }
    var overview by remember { mutableStateOf<AdminOverviewDto?>(null) }
    var config by remember { mutableStateOf<SystemConfigDto?>(null) }
    var cashInput by remember { mutableStateOf("") }
    var netContributionsInput by remember { mutableStateOf("") }
    var intervalInput by remember { mutableStateOf("10") }
    var endpoint by remember { mutableStateOf(EndpointStore.baseUrl(context)) }
    var loading by remember { mutableStateOf(true) }
    var saving by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var checkingUpdate by remember { mutableStateOf(false) }
    var availableUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var updateProgress by remember { mutableStateOf<UpdateDownloadProgress?>(null) }
    var updateStatus by remember { mutableStateOf<String?>(null) }
    fun saveConfig(next: SystemConfigDto, success: String) = scope.launch {
        saving = true; notice = "正在保存到服务端…"; error = null
        runCatching { api.saveAdminConfig(next) }
            .onSuccess { config = it; intervalInput = (it.paper_trading_interval_seconds / 60).toString(); notice = success }
            .onFailure { error = "保存失败：${it.message ?: "请检查服务连接"}" }
        saving = false
    }
    LaunchedEffect(refreshKey) {
        loading = true; error = null
        runCatching { api.adminOverview() }.onSuccess { overview = it }.onFailure { error = "无法读取系统状态：${it.message ?: "请检查服务连接"}" }
        runCatching { api.adminConfig() }.onSuccess { config = it; intervalInput = (it.paper_trading_interval_seconds / 60).toString() }
        runCatching { api.availableCash() }.onSuccess { cashInput = "%.2f".format(it.available_cash) }
        runCatching { api.paperTradingAccount() }.onSuccess { netContributionsInput = "%.2f".format(it.net_contributions) }
        loading = false
    }
    LaunchedEffect(availableUpdate) {
        val update = availableUpdate ?: return@LaunchedEffect
        while (true) {
            val progress = AppUpdateManager.refreshDownloadState(context)
            updateProgress = progress
            if (progress?.state?.isActive != true) {
                if (AppUpdateManager.hasCompletedDownload(context, update)) updateStatus = "更新包已下载完成，可安装。"
                else if (progress?.state == UpdateDownloadState.FAILED) updateStatus = progress.message
                break
            }
            delay(500)
        }
    }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 28.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        item { TradingPageHeader("管理", "服务连接、数据状态与模拟盘设置") { IconButton(onClick = { refreshKey++ }, enabled = !loading) { if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Icon(Icons.Filled.Refresh, "刷新管理状态") } } }
        error?.let { item { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 8.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
        notice?.let { item { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 8.dp), color = MaterialTheme.colorScheme.tertiary, style = MaterialTheme.typography.bodySmall) } }
        if (saving) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        item { TradingSection("运行概况", "数据直接来自本机服务") }
        item {
            Card(Modifier.padding(horizontal = 20.dp).fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    AdminLine("服务", if (overview?.status == "ok") "在线" else "未连接")
                    TradingRowDivider()
                    AdminLine("行情缓存", "${overview?.cached_quotes_count ?: 0} 只股票 · ${overview?.market_history_count ?: 0} 条历史快照")
                    AdminLine("新闻与公告", "${overview?.cached_content_count ?: 0} 条已保存内容")
                    AdminLine("数据更新时间", overview?.latest_market_at?.replace('T', ' ')?.substringBefore("+") ?: "暂无")
                }
            }
        }
        item { TradingSection("模拟账套", "可用资金由数据库统一保存；买入扣款，卖出回流") }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(value = cashInput, onValueChange = { cashInput = it }, modifier = Modifier.fillMaxWidth(), label = { Text("可用资金（元）") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), singleLine = true)
                Button(modifier = Modifier.fillMaxWidth(), enabled = !saving, onClick = {
                    val cash = cashInput.toDoubleOrNull()
                    if (cash == null || cash < 0) { error = "请输入不小于 0 的可用资金"; return@Button }
                    scope.launch {
                        saving = true; notice = "正在保存可用资金…"; error = null
                        runCatching { api.saveAvailableCash(AvailableCashInputDto(cash)) }
                            .onSuccess { cashInput = "%.2f".format(it.available_cash); notice = "可用资金已保存，模拟盘会立即读取新余额" }
                            .onFailure { error = "保存失败：${it.message ?: "请检查服务连接"}" }
                        saving = false
                    }
                }) { Text("保存可用资金") }
                OutlinedTextField(
                    value = netContributionsInput,
                    onValueChange = { netContributionsInput = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("累计净入金（收益计算基准）") },
                    supportingText = { Text("历史曾直接录入资金时，在此填写真实累计投入金额；不会改变当前可用资金或持仓。") },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                    singleLine = true,
                )
                TextButton(enabled = !saving, onClick = {
                    val amount = netContributionsInput.toDoubleOrNull()
                    if (amount == null || amount < 0) { error = "请输入不小于 0 的累计净入金"; return@TextButton }
                    scope.launch {
                        saving = true; notice = "正在校准收益基准…"; error = null
                        runCatching { api.reconcilePaperTradingContributions(PaperTradingCapitalReconciliationDto(amount)) }
                            .onSuccess { netContributionsInput = "%.2f".format(it.net_contributions); notice = "收益基准已校准；累计收益已剔除净入金。" }
                            .onFailure { error = "校准失败：${it.message ?: "请检查服务连接"}" }
                        saving = false
                    }
                }) { Text("校准累计净入金") }
            }
        }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("自动执行", fontWeight = FontWeight.SemiBold)
                        Text("开盘时间内按固定间隔分析市场并记入模拟账套。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(checked = config?.paper_trading_enabled == true, enabled = !saving, onCheckedChange = { enabled -> saveConfig((config ?: SystemConfigDto()).copy(paper_trading_enabled = enabled), if (enabled) "自动执行已开启" else "自动执行已关闭") })
                }
                OutlinedTextField(value = intervalInput, onValueChange = { intervalInput = it.filter(Char::isDigit) }, modifier = Modifier.fillMaxWidth(), label = { Text("执行间隔（分钟，至少 5 分钟）") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), singleLine = true)
                TextButton(enabled = !saving, onClick = {
                    val minutes = intervalInput.toIntOrNull()
                    if (minutes == null || minutes < 5) error = "执行间隔至少为 5 分钟" else saveConfig((config ?: SystemConfigDto()).copy(paper_trading_interval_seconds = minutes * 60), "执行间隔已保存：每 $minutes 分钟检查一次")
                }) { Text("保存执行间隔") }
            }
        }
        item { TradingSection("服务地址", "修改后保存并检查连接") }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(value = endpoint, onValueChange = { endpoint = it }, modifier = Modifier.fillMaxWidth(), label = { Text("服务地址") }, supportingText = { Text("例如 http://192.168.1.10:8000/") }, singleLine = true)
                Button(modifier = Modifier.fillMaxWidth(), enabled = !saving, onClick = {
                    EndpointStore.saveBaseUrl(context, endpoint)
                    scope.launch {
                        saving = true; notice = "正在检查连接…"
                        runCatching { ApiClient.service(context).health() }.onSuccess { notice = if (it.status == "ok") "服务连接成功" else "服务已响应：${it.status}" }.onFailure { error = "连接失败：${it.message ?: "请检查地址和网络"}" }
                        saving = false
                    }
                }) { Text("保存并检查连接") }
            }
        }
        item { TradingSection("应用更新", "当前版本 v${BuildConfig.VERSION_NAME}；更新包会校验签名后交给系统安装") }
        item {
            Column(Modifier.padding(horizontal = 20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("检查应用更新", fontWeight = FontWeight.SemiBold)
                        Text("关闭后不会自动检查新版本，但仍可在需要时手动检查。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(
                        checked = config?.update_check_enabled ?: true,
                        enabled = !saving,
                        onCheckedChange = { enabled -> saveConfig((config ?: SystemConfigDto()).copy(update_check_enabled = enabled), if (enabled) "已开启应用更新检查" else "已关闭应用更新检查") },
                    )
                }
                Button(modifier = Modifier.fillMaxWidth(), enabled = !checkingUpdate, onClick = {
                    scope.launch {
                        checkingUpdate = true; updateStatus = "正在检查更新…"
                        val update = runCatching { AppUpdateManager.check(context) }.getOrElse { error = "检查更新失败：${it.message ?: "请检查服务地址和网络"}"; null }
                        availableUpdate = update
                        updateProgress = update?.let { AppUpdateManager.refreshDownloadState(context) }
                        updateStatus = when {
                            update == null && error == null -> "当前已是最新版本，或正在使用 Debug 包。"
                            update != null -> "发现 v${update.versionName}，可下载并安装。"
                            else -> updateStatus
                        }
                        checkingUpdate = false
                    }
                }) { Text(if (checkingUpdate) "正在检查更新" else if (availableUpdate != null) "检查到新版本" else "检查更新") }
                availableUpdate?.let { update ->
                    Button(modifier = Modifier.fillMaxWidth(), onClick = {
                        updateStatus = when (AppUpdateManager.downloadAndInstall(context, update)) {
                            UpdateLaunchResult.DOWNLOAD_STARTED -> "正在下载 v${update.versionName}…"
                            UpdateLaunchResult.INSTALLER_OPENED -> "已打开系统安装页。"
                            UpdateLaunchResult.NEED_INSTALL_PERMISSION -> "请允许本应用安装未知来源应用后重试。"
                            UpdateLaunchResult.NEED_STORAGE_PERMISSION -> "请允许保存安装包后重试。"
                            UpdateLaunchResult.SIGNATURE_MISMATCH -> AppUpdateManager.completedUpdateMessage(context) ?: "安装包签名校验失败。"
                            UpdateLaunchResult.DOWNLOAD_UNAVAILABLE -> "APK 下载地址不可用，请检查发布配置。"
                        }
                    }) { Text(if (AppUpdateManager.hasCompletedDownload(context, update)) "安装更新" else "下载或安装更新") }
                }
                updateProgress?.let { progress ->
                    progress.fraction?.let { LinearProgressIndicator(progress = { it }, modifier = Modifier.fillMaxWidth()) }
                    Text("${progress.message}${progress.fraction?.let { " ${(it * 100).toInt()}%" }.orEmpty()}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                updateStatus?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = if (it.contains("失败") || it.contains("不可用")) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
    }
}

@Composable private fun AdminLine(label: String, value: String) = Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Top) {
    Text(label, Modifier.weight(0.32f), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(value, Modifier.weight(0.68f), style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
}
