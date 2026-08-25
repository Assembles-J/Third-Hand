package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PaperTradingScreen(onOpenDetail: (ResearchTargetDto) -> Unit) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var dashboard by remember { mutableStateOf<PaperTradingDashboardDto?>(null) }
    var positionPresentation by remember { mutableStateOf(PaperPositionPresentation()) }
    var openedPositionTarget by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var refreshing by remember { mutableStateOf(false) }
    var runningNow by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var showAllLogs by remember { mutableStateOf(false) }
    var runs by remember { mutableStateOf<List<SimulationRunDto>>(emptyList()) }
    var showRunChain by remember { mutableStateOf(false) }
    var selectedRunDetailId by remember { mutableStateOf<String?>(null) }
    var runDetail by remember { mutableStateOf<SimulationRunDetailDto?>(null) }
    var runDetailLoading by remember { mutableStateOf(false) }
    var runDetailError by remember { mutableStateOf<String?>(null) }
    var selectedDecisionId by remember { mutableStateOf<String?>(null) }
    var decisionReport by remember { mutableStateOf<DecisionReportDto?>(null) }
    var decisionContext by remember { mutableStateOf<Map<String, Any>>(emptyMap()) }
    var decisionLineage by remember { mutableStateOf<DecisionLineageDto?>(null) }
    var decisionLoading by remember { mutableStateOf(false) }
    var decisionError by remember { mutableStateOf<String?>(null) }

    val positionTarget = openedPositionTarget
    if (positionTarget != null) {
        PositionDetailRoute(
            target = positionTarget,
            onBack = { openedPositionTarget = null },
        )
        return
    }

    fun refresh() {
        if (refreshing) return
        scope.launch {
            refreshing = true
            runCatching { api.paperTradingDashboard() }
                .onSuccess { loaded ->
                    dashboard = loaded
                    positionPresentation = loadPaperPositionPresentation(api, loaded.account.positions)
                    error = null
                }
                .onFailure { error = "账套读取失败" }
            runs = runCatching { api.paperTradingRuns(limit = 20) }.getOrDefault(emptyList())
            refreshing = false
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Scaffold(
        topBar = {
            TradingPageHeader("交易账户", "模拟账套 · 持仓驱动 · 影子交易") {
                IconButton(onClick = ::refresh, enabled = !refreshing) {
                    if (refreshing) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, "刷新", tint = MaterialTheme.colorScheme.primary)
                }
            }
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge)
        ) {
            item {
                AccountEquityCard(dashboard?.account)
            }

            item {
                TradingSection("持仓明细", "Security Positions")
            }

            if (dashboard?.account?.positions.isNullOrEmpty()) {
                item {
                    EmptyStatePlaceholder("当前没有持仓，运行模拟决策以寻找机会")
                }
            } else {
                item {
                    PaperPositionsTable(
                        positions = dashboard!!.account.positions,
                        presentation = positionPresentation,
                        onOpenDetail = { position, name ->
                            openedPositionTarget = ResearchTargetDto(
                                symbol = position.symbol,
                                name = name,
                                status = "paper_position",
                                added_at = position.updated_at,
                            )
                        },
                    )
                }
            }

            item {
                ExecutionControlPanel(
                    running = runningNow,
                    status = dashboard?.status,
                    onRun = {
                        scope.launch {
                            runningNow = true
                            runCatching { api.runPaperTradingNow() }.onSuccess {
                                message = it.message
                                refresh()
                            }
                            runningNow = false
                        }
                    }
                )
            }

            item {
                HistoryLink(
                    runs = runs,
                    onClick = { showRunChain = true }
                )
            }

            item {
                TradingSection("最近成交记录", "Execution Logs")
            }

            val executedLogs = dashboard?.logs.orEmpty().filter { it.status == "executed" }
            if (executedLogs.isEmpty()) {
                item { EmptyStatePlaceholder("暂无执行记录") }
            }

            items(executedLogs.take(5), key = { it.id }) { log ->
                PaperLogRow(log, onOpenDecision = { selectedDecisionId = log.decision_id })
            }

            if (dashboard?.logs.orEmpty().size > 5) {
                item {
                    TextButton(
                        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
                        onClick = { showAllLogs = true }
                    ) {
                        Text("查看完整操作与拦截记录")
                    }
                }
            }
        }
    }

    // Dialogs...
    if (showAllLogs) PaperLogHistoryDialog(dashboard?.logs.orEmpty(), onDismiss = { showAllLogs = false }, onOpenDecision = { selectedDecisionId = it })
    if (showRunChain) PaperRunChainDialog(runs, onDismiss = { showRunChain = false }, onOpenRun = { selectedRunDetailId = it })
    if (selectedRunDetailId != null) PaperRunDetailDialog(runDetail, runDetailLoading, runDetailError, onDismiss = { selectedRunDetailId = null }, onOpenDecision = { selectedDecisionId = it })
    if (selectedDecisionId != null) PaperDecisionAuditDialog(decisionReport, decisionContext, decisionLoading, decisionError, decisionLineage, onDismiss = { selectedDecisionId = null })
}

@Composable
private fun AccountEquityCard(account: PaperTradingAccountDto?) {
    val colors = MaterialTheme.marketColors
    val isPositive = (account?.total_pnl ?: 0.0) >= 0

    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary),
        shape = MaterialTheme.shapes.large
    ) {
        Column(Modifier.padding(AppSpacing.xxLarge)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("账套总权益 (CNY)", style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.7f))
                    Text(
                        "¥${account?.total_equity?.money() ?: "---"}",
                        style = MaterialTheme.typography.displayMedium,
                        fontWeight = FontWeight.ExtraBold,
                        color = Color.White
                    )
                }
                Surface(
                    color = Color.White.copy(alpha = 0.2f),
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        account?.total_return_percent?.let { "${if(it>=0)"+" else ""}${"%.2f".format(it)}%" } ?: "--",
                        Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }
            }

            Spacer(Modifier.height(AppSpacing.xxLarge))

            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                EquityMetric("可用现金", "¥${account?.available_cash?.money() ?: "--"}")
                EquityMetric("持仓市值", "¥${account?.market_value?.money() ?: "--"}")
                EquityMetric("累计盈亏", "¥${account?.total_pnl?.money() ?: "--"}")
            }
        }
    }
}

@Composable
private fun EquityMetric(label: String, value: String) {
    Column {
        Text(label, style = MaterialTheme.typography.labelSmall, color = Color.White.copy(alpha = 0.6f))
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = Color.White)
    }
}

@Composable
private fun ExecutionControlPanel(running: Boolean, status: PaperTradingStatusDto?, onRun: () -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
        shape = MaterialTheme.shapes.medium
    ) {
        Column(Modifier.padding(AppSpacing.large)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Terminal, null, modifier = Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(AppSpacing.medium))
                Text("自动执行引擎", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                if (status?.running == true) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                } else {
                    Text(
                        if (status?.enabled == true) "已开启" else "已暂停",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (status?.enabled == true) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.neutral
                    )
                }
            }

            Spacer(Modifier.height(AppSpacing.medium))

            Button(
                onClick = onRun,
                enabled = !running && status?.running != true,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium
            ) {
                Icon(Icons.Default.PlayArrow, null)
                Spacer(Modifier.width(AppSpacing.small))
                Text(if (running) "正在运行模拟决策..." else "立即运行决策轮换")
            }
        }
    }
}

@Composable
private fun HistoryLink(runs: List<SimulationRunDto>, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.xxLarge)
            .clickable(onClick = onClick),
        color = MaterialTheme.colorScheme.surface,
        border = androidx.compose.foundation.BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant),
        shape = MaterialTheme.shapes.medium
    ) {
        Row(Modifier.padding(AppSpacing.large), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("执行链路记录", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                Text(
                    "最近完成：${runs.firstOrNull()?.started_at?.let { paperBeijingTimestamp(it) } ?: "从未运行"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

@Composable
private fun EmptyStatePlaceholder(msg: String) {
    Box(Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), contentAlignment = Alignment.Center) {
        Text(msg, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

@Composable private fun PaperLogRow(log: PaperTradingLogDto, onOpenDecision: () -> Unit) {
    val isBuy = log.side == "BUY"
    val color = if (isBuy) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall

    Column(Modifier.fillMaxWidth().clickable(enabled = log.decision_id != null, onClick = onOpenDecision).padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Surface(
                color = color.copy(alpha = 0.1f),
                shape = RoundedCornerShape(4.dp)
            ) {
                Text(
                    if (isBuy) "B 买入" else "S 卖出",
                    Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = color
                )
            }
            Spacer(Modifier.width(AppSpacing.medium))
            Text(
                log.name.ifBlank { log.symbol },
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Bold
            )
            Spacer(Modifier.weight(1f))
            Text("¥${log.price.money()}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(4.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "${log.symbol} · ${paperBeijingTimestamp(log.executed_at)} · ${log.quantity.toInt()} 股",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.weight(1f))
            Text("分析记录", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
        }
        Spacer(Modifier.height(AppSpacing.medium))
        TradingRowDivider()
    }
}

// Keep existing helper functions...
private fun Double.money() = "%.2f".format(Locale.US, this)
private fun paperBeijingTimestamp(value: String): String = runCatching { OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8)).format(DateTimeFormatter.ofPattern("MM-dd HH:mm")) }.getOrElse { value.replace('T', ' ').substringBefore("+").substringBefore("Z") }

// Keep existing Dialog implementations...
@Composable private fun PaperLogHistoryDialog(logs: List<PaperTradingLogDto>, onDismiss: () -> Unit, onOpenDecision: (String?) -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("完整操作记录") },
    text = { LazyColumn { items(logs, key = { it.id }) { log -> PaperLogRow(log, onOpenDecision = { onOpenDecision(log.decision_id) }) } } },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)
@Composable private fun PaperRunChainDialog(runs: List<SimulationRunDto>, onDismiss: () -> Unit, onOpenRun: (String) -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("执行链路记录") },
    text = {
        if (runs.isEmpty()) Text("还没有执行记录。")
        else LazyColumn { items(runs, key = { it.run_id }) { run -> PaperRunRow(run, onClick = { onOpenRun(run.run_id) }) } }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)
@Composable private fun PaperRunRow(run: SimulationRunDto, onClick: () -> Unit) {
    val statusColor = when (run.status) { "completed" -> Color(0xFF2E7D32); "failed" -> Color(0xFFC62828); else -> MaterialTheme.colorScheme.onSurfaceVariant }
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("${paperBeijingTimestamp(run.started_at)} · ${if (run.trigger == "manual") "手动" else "自动"}", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.weight(1f))
            Text(if (run.status == "completed") "完成" else "失败", color = statusColor, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.outlineVariant)
        }
    }
}
@Composable private fun PaperRunDetailDialog(run: SimulationRunDetailDto?, loading: Boolean, error: String?, onDismiss: () -> Unit, onOpenDecision: (String?) -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("链路详情") },
    text = {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            run?.let { data ->
                item { Text(data.message, style = MaterialTheme.typography.bodySmall) }
                data.symbols.forEach { symbol ->
                    item {
                         Row(Modifier.fillMaxWidth().clickable { onOpenDecision(symbol.detail["decision_id"] as? String) }.padding(vertical = 4.dp)) {
                             Text(symbol.symbol, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                             Text(symbol.terminal_state, style = MaterialTheme.typography.labelSmall)
                         }
                    }
                }
            }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)
@Composable fun PaperDecisionAuditDialog(report: DecisionReportDto?, context: Map<String, Any>, loading: Boolean, error: String?, lineage: DecisionLineageDto? = null, onDismiss: () -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("操作分析记录") },
    text = {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            report?.let { it ->
                item { Text("${it.symbol} · ${it.action}", fontWeight = FontWeight.Bold) }
                item { Text(it.summary, style = MaterialTheme.typography.bodySmall) }
                it.evidence.forEach { ev -> item { Text("${ev.title}: ${ev.description}", style = MaterialTheme.typography.labelSmall) } }
            }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)
