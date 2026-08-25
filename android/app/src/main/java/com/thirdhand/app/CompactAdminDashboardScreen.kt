package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.lab.LabScreen
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.AppSpacing
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun CompactAdminDashboardScreen() {
    var showLab by remember { mutableStateOf(false) }
    if (showLab) {
        LabScreen(onBack = { showLab = false })
        return
    }

    val context = LocalContext.current
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
    var availableUpdate by remember { mutableStateOf<AppUpdate?>(null) }
    var providerHealth by remember { mutableStateOf<ProviderHealthResponseDto?>(null) }

    fun saveConfig(next: SystemConfigDto, success: String) = scope.launch {
        saving = true; notice = "正在同步配置..."; error = null
        runCatching { api.saveAdminConfig(next) }
            .onSuccess { config = it; intervalInput = (it.paper_trading_interval_seconds / 60).toString(); notice = success }
            .onFailure { error = "配置保存失败" }
        saving = false
    }

    LaunchedEffect(refreshKey) {
        loading = true; error = null
        runCatching { api.adminOverview() }.onSuccess { overview = it }.onFailure { error = "系统服务未响应" }
        runCatching { api.adminConfig() }.onSuccess { config = it; intervalInput = (it.paper_trading_interval_seconds / 60).toString() }
        runCatching { api.availableCash() }.onSuccess { cashInput = "%.2f".format(it.available_cash) }
        runCatching { api.paperTradingAccount() }.onSuccess { netContributionsInput = "%.2f".format(it.net_contributions) }
        runCatching { api.providerHealth() }.onSuccess { providerHealth = it }
        runCatching { AppUpdateManager.check(context) }.onSuccess { update ->
            availableUpdate = update
        }
        loading = false
    }

    Scaffold(
        topBar = {
            TradingPageHeader("系统管理", "后端服务配置、数据同步与内核维护") {
                IconButton(onClick = { refreshKey++ }, enabled = !loading) {
                    if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Default.Refresh, null, tint = MaterialTheme.colorScheme.onPrimary)
                }
            }
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues).background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small)
        ) {
            item {
                LabEntryCard(onOpen = { showLab = true })
            }

            error?.let {
                item {
                    Surface(
                        Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
                        color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.5f),
                        shape = MaterialTheme.shapes.small
                    ) {
                        Text(it, Modifier.padding(AppSpacing.medium), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }

            item { TradingSection("运行监控", "System Overview") }
            item { SystemStatusCard(overview) }

            item { TradingSection("核心参数", "Engine Configuration") }
            item {
                ConfigCard(
                    cashInput = cashInput,
                    onCashChange = { cashInput = it },
                    intervalInput = intervalInput,
                    onIntervalChange = { intervalInput = it },
                    tradingEnabled = config?.paper_trading_enabled ?: false,
                    onTradingToggle = { enabled ->
                        saveConfig((config ?: SystemConfigDto()).copy(paper_trading_enabled = enabled), "自动执行已更新")
                    },
                    onSaveCash = {
                        scope.launch {
                            val cash = cashInput.toDoubleOrNull() ?: return@launch
                            saving = true
                            runCatching { api.saveAvailableCash(AvailableCashInputDto(cash)) }
                                .onSuccess { notice = "可用资金已更新" }
                            saving = false
                        }
                    },
                    onSaveInterval = {
                        val min = intervalInput.toIntOrNull() ?: 10
                        saveConfig((config ?: SystemConfigDto()).copy(paper_trading_interval_seconds = min * 60), "扫描间隔已更新")
                    }
                )
            }

            item { TradingSection("数据网关健康度", "Data Provider Health") }
            item { ProviderHealthCard(providerHealth) }

            item { TradingSection("网络节点", "Service Endpoint") }
            item {
                EndpointCard(
                    endpoint = endpoint,
                    onEndpointChange = { endpoint = it },
                    onSave = {
                        EndpointStore.saveBaseUrl(context, endpoint)
                        refreshKey++
                    }
                )
            }
        }
    }
}

@Composable
private fun LabEntryCard(onOpen: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary),
        shape = MaterialTheme.shapes.large
    ) {
        Row(Modifier.padding(AppSpacing.xxLarge), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("策略实验室", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = Color.White)
                Text("沙盒评估与回测归因系统", style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.7f))
            }
            Button(
                onClick = onOpen,
                colors = ButtonDefaults.buttonColors(containerColor = Color.White, contentColor = MaterialTheme.colorScheme.primary),
                shape = MaterialTheme.shapes.medium
            ) {
                Text("进入实验室", fontWeight = FontWeight.Bold)
            }
        }
    }
}

@Composable
private fun SystemStatusCard(overview: AdminOverviewDto?) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
            StatusLine("服务核心状态", if (overview?.status == "ok") "运行中" else "离线", isActive = overview?.status == "ok")
            TradingRowDivider()
            StatusLine("行情缓存容量", "${overview?.cached_quotes_count ?: 0} 标的 / ${overview?.market_history_count ?: 0} K线")
            StatusLine("资讯索引条数", "${overview?.cached_content_count ?: 0} 条")
            StatusLine("最近心跳时间", overview?.latest_market_at?.take(16)?.replace('T', ' ') ?: "---")
        }
    }
}

@Composable
private fun ConfigCard(
    cashInput: String,
    onCashChange: (String) -> Unit,
    intervalInput: String,
    onIntervalChange: (String) -> Unit,
    tradingEnabled: Boolean,
    onTradingToggle: (Boolean) -> Unit,
    onSaveCash: () -> Unit,
    onSaveInterval: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("自动决策引擎", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                    Text("开启后将按周期自动运行轮换决策", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(checked = tradingEnabled, onCheckedChange = onTradingToggle)
            }

            OutlinedTextField(
                value = intervalInput,
                onValueChange = onIntervalChange,
                label = { Text("扫描间隔 (分钟)") },
                modifier = Modifier.fillMaxWidth(),
                trailingIcon = { TextButton(onClick = onSaveInterval) { Text("保存") } },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                shape = MaterialTheme.shapes.medium
            )

            HorizontalDivider(modifier = Modifier.padding(vertical = AppSpacing.small), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))

            OutlinedTextField(
                value = cashInput,
                onValueChange = onCashChange,
                label = { Text("账户可用资金 (CNY)") },
                modifier = Modifier.fillMaxWidth(),
                trailingIcon = { TextButton(onClick = onSaveCash) { Text("更新") } },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                shape = MaterialTheme.shapes.medium
            )
        }
    }
}

@Composable
private fun ProviderHealthCard(health: ProviderHealthResponseDto?) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(AppSpacing.large)) {
            if (health == null || health.providers.isEmpty()) {
                Text("暂无数据源统计", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                health.providers.forEachIndexed { index, provider ->
                    ProviderStatusRow(provider)
                    if (index < health.providers.lastIndex) {
                        HorizontalDivider(Modifier.padding(vertical = AppSpacing.medium), thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f))
                    }
                }
            }
        }
    }
}

@Composable
private fun ProviderStatusRow(provider: ProviderHealthDto) {
    val isBroken = provider.circuit_state == "open"
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(provider.provider, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
            Text("成功率: ${(provider.total_success.toFloat() / provider.total_attempts.coerceAtLeast(1) * 100).toInt()}%", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Surface(
            color = (if (isBroken) MaterialTheme.colorScheme.error else Color(0xFF2E7D32)).copy(alpha = 0.1f),
            shape = CircleShape
        ) {
            Text(
                if (isBroken) "已熔断" else "健康",
                Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
                color = if (isBroken) MaterialTheme.colorScheme.error else Color(0xFF2E7D32)
            )
        }
    }
}

@Composable
private fun EndpointCard(endpoint: String, onEndpointChange: (String) -> Unit, onSave: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f)),
        shape = MaterialTheme.shapes.large
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
            OutlinedTextField(
                value = endpoint,
                onValueChange = onEndpointChange,
                label = { Text("API 端点地址") },
                modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("http://ip:port/") },
                shape = MaterialTheme.shapes.medium
            )
            Button(onClick = onSave, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium) {
                Text("保存并应用端点")
            }
        }
    }
}

@Composable
private fun StatusLine(label: String, value: String, isActive: Boolean = false) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            value,
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Bold,
            color = if (isActive) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
        )
    }
}
