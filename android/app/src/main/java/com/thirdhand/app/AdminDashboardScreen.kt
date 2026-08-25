package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.AppSpacing

private val ConsoleCanvas = Color(0xFF0F172A)
private val ConsolePanel = Color(0xFF1E293B)
private val ConsoleRaised = Color(0xFF334155)
private val ConsoleMint = Color(0xFF4ADE80)
private val ConsoleTeal = Color(0xFF2DD4BF)
private val ConsoleGold = Color(0xFFFACC15)
private val ConsoleCoral = Color(0xFFFB7185)
private val ConsoleText = Color(0xFFF1F5F9)
private val ConsoleQuiet = Color(0xFF94A3B8)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminDashboardScreen() {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    var refreshIndex by remember { mutableIntStateOf(0) }
    var overview by remember { mutableStateOf<AdminOverviewDto?>(null) }
    var monitoringError by remember { mutableStateOf<String?>(null) }
    var savedMessage by remember { mutableStateOf<String?>(null) }
    var showMaintenanceWarning by remember { mutableStateOf(false) }

    LaunchedEffect(refreshIndex) {
        monitoringError = null
        runCatching { api.adminOverview() }
            .onSuccess { overview = it }
            .onFailure { monitoringError = "连接失败: ${it.message}" }
    }

    Scaffold(
        topBar = {
            TradingPageHeader("系统控制台", "System Monitoring & Infrastructure") {
                IconButton(onClick = { refreshIndex++ }) {
                    Icon(Icons.Default.Refresh, null, tint = MaterialTheme.colorScheme.onPrimary)
                }
            }
        },
        containerColor = ConsoleCanvas
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.large)
        ) {
            if (monitoringError != null) {
                Surface(
                    color = ConsoleCoral.copy(alpha = 0.1f),
                    shape = MaterialTheme.shapes.medium,
                    border = androidx.compose.foundation.BorderStroke(1.dp, ConsoleCoral.copy(alpha = 0.3f))
                ) {
                    Text(
                        monitoringError!!,
                        Modifier.padding(AppSpacing.large),
                        color = ConsoleCoral,
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }

            ConsoleMetricGrid(overview)

            ThroughputPanel(overview)

            AlertPanel(overview)

            CapacityPanel(overview)

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
                Button(
                    onClick = { showMaintenanceWarning = true },
                    modifier = Modifier.weight(1f),
                    colors = ButtonDefaults.buttonColors(containerColor = ConsoleCoral),
                    shape = MaterialTheme.shapes.medium
                ) {
                    Icon(Icons.Default.Warning, null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(AppSpacing.small))
                    Text("进入维护模式")
                }
            }
        }
    }

    if (showMaintenanceWarning) {
        AlertDialog(
            onDismissRequest = { showMaintenanceWarning = false },
            containerColor = ConsolePanel,
            titleContentColor = ConsoleText,
            textContentColor = ConsoleQuiet,
            icon = { Icon(Icons.Default.WarningAmber, null, tint = ConsoleCoral) },
            title = { Text("确认进入维护模式？") },
            text = { Text("进入后系统将暂停所有自动分析和交易链路，仅保留核心心跳。") },
            confirmButton = {
                TextButton(onClick = {
                    showMaintenanceWarning = false
                    savedMessage = "已进入维护模式"
                }) {
                    Text("确认暂停", color = ConsoleCoral, fontWeight = FontWeight.Bold)
                }
            },
            dismissButton = {
                TextButton(onClick = { showMaintenanceWarning = false }) {
                    Text("取消", color = ConsoleText)
                }
            }
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ConsoleMetricGrid(overview: AdminOverviewDto?) {
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium),
        verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)
    ) {
        val itemModifier = Modifier.weight(1f).minWidth(150.dp)
        MetricCell("API 状态", if (overview?.status == "ok") "ACTIVE" else "OFFLINE", "实时后端", ConsoleMint, Icons.Default.Bolt, itemModifier)
        MetricCell("持仓标的", (overview?.holdings_count ?: 0).toString(), "个股总数", ConsoleTeal, Icons.Default.Security, itemModifier)
        MetricCell("待处理草稿", (overview?.pending_draft_count ?: 0).toString(), "人工核验", ConsoleGold, Icons.Default.DynamicFeed, itemModifier)
        MetricCell("行情快照", (overview?.cached_quotes_count ?: 0).toString(), "本地缓存", ConsoleMint, Icons.Default.Storage, itemModifier)
    }
}

@Composable
private fun MetricCell(label: String, value: String, hint: String, accent: Color, icon: ImageVector, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        color = ConsolePanel,
        shape = MaterialTheme.shapes.medium
    ) {
        Column(Modifier.padding(AppSpacing.large)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, null, tint = accent, modifier = Modifier.size(14.dp))
                Spacer(Modifier.width(AppSpacing.small))
                Text(label, color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
            }
            Spacer(Modifier.height(AppSpacing.medium))
            Text(value, color = ConsoleText, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.headlineSmall)
            Text(hint, color = accent.copy(alpha = 0.7f), style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace)
        }
    }
}

@Composable
private fun ThroughputPanel(overview: AdminOverviewDto?) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = ConsolePanel,
        shape = MaterialTheme.shapes.large
    ) {
        Column(Modifier.padding(AppSpacing.xxLarge)) {
            Text("后端组件链路状态", color = ConsoleText, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(AppSpacing.large))

            Row(
                Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(AppSpacing.xxLarge),
                verticalAlignment = Alignment.CenterVertically
            ) {
                listOf("Gateway", "Engine", "Database", "Cache", "LLM").forEach { name ->
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Box(Modifier.size(40.dp).clip(CircleShape).background(ConsoleRaised), contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.Dns, null, tint = ConsoleMint, modifier = Modifier.size(20.dp))
                        }
                        Spacer(Modifier.height(AppSpacing.small))
                        Text(name, color = ConsoleText, style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace)
                    }
                }
            }

            Spacer(Modifier.height(AppSpacing.xxLarge))
            Text("系统在线时长: ${overview?.uptime_seconds ?: 0}s", color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
private fun AlertPanel(overview: AdminOverviewDto?) {
    val pending = overview?.pending_draft_count ?: 0
    if (pending == 0) return

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = ConsoleGold.copy(alpha = 0.1f),
        shape = MaterialTheme.shapes.medium,
        border = androidx.compose.foundation.BorderStroke(1.dp, ConsoleGold.copy(alpha = 0.2f))
    ) {
        Row(Modifier.padding(AppSpacing.large), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.ErrorOutline, null, tint = ConsoleGold)
            Spacer(Modifier.width(AppSpacing.medium))
            Column(Modifier.weight(1f)) {
                Text("存在 $pending 条待处理草稿", color = ConsoleText, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodySmall)
                Text("需要手动确认证券代码后方可入库分析", color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun CapacityPanel(overview: AdminOverviewDto?) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = ConsolePanel,
        shape = MaterialTheme.shapes.large
    ) {
        Column(Modifier.padding(AppSpacing.xxLarge)) {
            Text("存储资源占用", color = ConsoleText, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(AppSpacing.large))

            CapacityBar("SQLite Database", overview?.database_bytes?.toLong() ?: 0L, 100 * 1024 * 1024L, ConsoleTeal)
            Spacer(Modifier.height(AppSpacing.medium))
            CapacityBar("Market History", overview?.market_history_count?.toLong() ?: 0L, 50000L, ConsoleMint)
        }
    }
}

@Composable
private fun CapacityBar(label: String, current: Long, total: Long, color: Color) {
    val progress = if(total > 0) current.toFloat() / total else 0f
    Column {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(label, color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
            Text("${(progress * 100).toInt()}%", color = ConsoleText, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(4.dp))
        LinearProgressIndicator(
            progress = { progress },
            modifier = Modifier.fillMaxWidth().height(4.dp).clip(CircleShape),
            color = color,
            trackColor = ConsoleRaised
        )
    }
}

private fun Modifier.minWidth(dp: androidx.compose.ui.unit.Dp) = this.widthIn(min = dp)
