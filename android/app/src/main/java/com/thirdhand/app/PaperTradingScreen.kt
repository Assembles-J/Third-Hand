package com.thirdhand.app

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Analytics
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Science
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.lab.LabScreen
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import com.thirdhand.app.ui.theme.marketColors
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
    val snackbarHostState = remember { SnackbarHostState() }
    var dashboard by remember { mutableStateOf<PaperTradingDashboardDto?>(null) }
    var positionPresentation by remember { mutableStateOf(PaperPositionPresentation()) }
    var openedPositionTarget by remember { mutableStateOf<ResearchTargetDto?>(null) }
    var refreshing by remember { mutableStateOf(false) }
    var runningNow by remember { mutableStateOf(false) }
    var changingTradingEnabled by remember { mutableStateOf(false) }
    var operationMessage by remember { mutableStateOf<String?>(null) }
    var errorMessage by remember { mutableStateOf<String?>(null) }
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
    var labOpen by remember { mutableStateOf(false) }

    val positionTarget = openedPositionTarget
    if (positionTarget != null) {
        PositionDetailRoute(
            target = positionTarget,
            onBack = { openedPositionTarget = null },
        )
        return
    }

    if (labOpen) {
        LabScreen(onBack = { labOpen = false })
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
                    errorMessage = null
                }
                .onFailure { errorMessage = "模拟账户暂时无法同步，请稍后重试" }
            runs = runCatching { api.paperTradingRuns(limit = 20) }.getOrDefault(emptyList())
            refreshing = false
        }
    }

    LaunchedEffect(Unit) { refresh() }

    LaunchedEffect(selectedRunDetailId) {
        val runId = selectedRunDetailId
        runDetail = null
        runDetailError = null
        if (runId == null) {
            runDetailLoading = false
            return@LaunchedEffect
        }
        runDetailLoading = true
        runCatching { api.paperTradingRunDetail(runId) }
            .onSuccess { runDetail = it }
            .onFailure { runDetailError = "无法读取本次执行链路，请稍后重试" }
        runDetailLoading = false
    }

    LaunchedEffect(selectedDecisionId) {
        val decisionId = selectedDecisionId
        decisionReport = null
        decisionContext = emptyMap()
        decisionLineage = null
        decisionError = null
        if (decisionId == null) {
            decisionLoading = false
            return@LaunchedEffect
        }
        decisionLoading = true
        runCatching { api.paperTradingDecisionAudit(decisionId) }
            .onSuccess { audit ->
                decisionReport = audit.report
                decisionContext = audit.context
            }
            .onFailure { decisionError = "无法读取本次决策复核记录，请稍后重试" }
        decisionLineage = runCatching { api.decisionLineage(decisionId) }.getOrNull()
        decisionLoading = false
    }

    Scaffold(
        topBar = {
            StrategyPageHeader(
                refreshing = refreshing,
                onRefresh = ::refresh,
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    ) { paddingValues ->
        StrategyExecutionContent(
            dashboard = dashboard,
            positionPresentation = positionPresentation,
            runs = runs,
            refreshing = refreshing,
            running = runningNow,
            changingEnabled = changingTradingEnabled,
            errorMessage = errorMessage,
            operationMessage = operationMessage,
            onOpenPosition = { position, name ->
                openedPositionTarget = ResearchTargetDto(
                    symbol = position.symbol,
                    name = name,
                    status = "paper_position",
                    added_at = position.updated_at,
                )
            },
            onEnabledChange = { enabled ->
                if (!changingTradingEnabled) {
                    scope.launch {
                        changingTradingEnabled = true
                        operationMessage = null
                        val result = runCatching {
                            val current = api.adminConfig()
                            api.saveAdminConfig(current.copy(paper_trading_enabled = enabled))
                        }
                        if (result.isSuccess) {
                            snackbarHostState.showSnackbar(
                                if (enabled) "模拟账户自动执行已开启" else "模拟账户自动执行已暂停"
                            )
                            refresh()
                        } else {
                            snackbarHostState.showSnackbar("切换模拟账户自动执行失败，请稍后重试")
                        }
                        changingTradingEnabled = false
                    }
                }
            },
            onRun = {
                scope.launch {
                    runningNow = true
                    operationMessage = null
                    val result = runCatching { api.runPaperTradingNow() }
                    if (result.isSuccess) {
                        operationMessage = result.getOrNull()?.message?.ifBlank { "模拟决策轮换已完成" }
                        refresh()
                    } else {
                        snackbarHostState.showSnackbar("运行模拟决策失败，请稍后重试")
                    }
                    runningNow = false
                }
            },
            onOpenRunChain = { showRunChain = true },
            onOpenAllLogs = { showAllLogs = true },
            onOpenDecision = { selectedDecisionId = it },
            onOpenLab = { labOpen = true },
            modifier = Modifier.padding(paddingValues),
        )
    }

    if (showAllLogs) {
        PaperLogHistoryDialog(
            dashboard?.logs.orEmpty(),
            onDismiss = { showAllLogs = false },
            onOpenDecision = { selectedDecisionId = it },
        )
    }
    if (showRunChain) {
        PaperRunChainDialog(
            runs,
            onDismiss = { showRunChain = false },
            onOpenRun = {
                showRunChain = false
                selectedRunDetailId = it
            },
        )
    }
    if (selectedRunDetailId != null) {
        PaperRunDetailDialog(
            runDetail,
            runDetailLoading,
            runDetailError,
            onDismiss = { selectedRunDetailId = null },
            onOpenDecision = { selectedDecisionId = it },
        )
    }
    if (selectedDecisionId != null) {
        PaperDecisionAuditDialog(
            decisionReport,
            decisionContext,
            decisionLoading,
            decisionError,
            decisionLineage,
            onDismiss = { selectedDecisionId = null },
        )
    }
}

@Composable
internal fun StrategyPageHeader(
    refreshing: Boolean,
    onRefresh: () -> Unit,
) {
    TradingPageHeader("策略", "AI交易 · 模拟账户 · 决策复核") {
        IconButton(onClick = onRefresh, enabled = !refreshing) {
            if (refreshing) {
                CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            } else {
                Icon(Icons.Filled.Refresh, contentDescription = "刷新策略", tint = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

@Composable
internal fun StrategyExecutionContent(
    dashboard: PaperTradingDashboardDto?,
    positionPresentation: PaperPositionPresentation,
    runs: List<SimulationRunDto>,
    refreshing: Boolean,
    running: Boolean,
    changingEnabled: Boolean,
    errorMessage: String?,
    operationMessage: String?,
    onOpenPosition: (PaperTradingPositionDto, String) -> Unit,
    onEnabledChange: (Boolean) -> Unit,
    onRun: () -> Unit,
    onOpenRunChain: () -> Unit,
    onOpenAllLogs: () -> Unit,
    onOpenDecision: (String?) -> Unit,
    onOpenLab: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val logs = dashboard?.logs.orEmpty()
    val executedLogs = logs.filter { it.status == "executed" }
    val latestDecisionId = logs.firstOrNull { !it.decision_id.isNullOrBlank() }?.decision_id

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
    ) {
        item {
            StrategyQuickActions(
                latestDecisionId = latestDecisionId,
                onOpenDecision = onOpenDecision,
                onOpenLab = onOpenLab,
            )
        }

        item { CompactAccountEquityCard(dashboard?.account) }

        if (errorMessage != null) {
            item { StrategyStatusStrip(errorMessage, isError = true) }
        } else if (!operationMessage.isNullOrBlank()) {
            item { StrategyStatusStrip(operationMessage, isError = false) }
        } else if (refreshing && dashboard == null) {
            item { StrategyStatusStrip("正在同步模拟账户与执行状态…", isError = false) }
        }

        item { TradingSection("模拟账户持仓", "Paper Positions") }

        if (dashboard?.account?.positions.isNullOrEmpty()) {
            item { EmptyStatePlaceholder("当前没有模拟持仓") }
        } else {
            item {
                PaperPositionsTable(
                    positions = dashboard!!.account.positions,
                    presentation = positionPresentation,
                    onOpenDetail = onOpenPosition,
                )
            }
        }

        item {
            CompactExecutionControlPanel(
                running = running,
                changingEnabled = changingEnabled,
                status = dashboard?.status,
                onEnabledChange = onEnabledChange,
                onRun = onRun,
            )
        }

        item { HistoryLink(runs = runs, onClick = onOpenRunChain) }

        item { TradingSection("最近成交记录", "Execution Logs") }

        if (executedLogs.isEmpty()) {
            item { EmptyStatePlaceholder("暂无模拟成交记录") }
        }

        items(executedLogs.take(5), key = { it.id }) { log ->
            PaperLogRow(log, onOpenDecision = { onOpenDecision(log.decision_id) })
        }

        if (logs.size > 5) {
            item {
                TextButton(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.contentHorizontal),
                    onClick = onOpenAllLogs,
                ) {
                    Text("查看完整操作与拦截记录")
                }
            }
        }

        item {
            Text(
                "研究计划仍由自选 / 持仓的服务端 ReviewPlan 展示；本页不伪造新的研究权限或交易权限。",
                modifier = Modifier.padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.medium),
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun StrategyQuickActions(
    latestDecisionId: String?,
    onOpenDecision: (String?) -> Unit,
    onOpenLab: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.small),
        horizontalArrangement = Arrangement.spacedBy(AppSpacing.small),
    ) {
        StrategyQuickAction(
            label = "AI交易",
            subtitle = "当前",
            icon = Icons.Default.Terminal,
            selected = true,
            enabled = false,
            onClick = {},
            modifier = Modifier.weight(1f),
        )
        StrategyQuickAction(
            label = "决策复核",
            subtitle = if (latestDecisionId == null) "暂无记录" else "最近记录",
            icon = Icons.Default.Analytics,
            selected = false,
            enabled = latestDecisionId != null,
            onClick = { onOpenDecision(latestDecisionId) },
            modifier = Modifier.weight(1f),
        )
        StrategyQuickAction(
            label = "策略评估",
            subtitle = "SWING_V1",
            icon = Icons.Default.Science,
            selected = false,
            enabled = true,
            onClick = onOpenLab,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun StrategyQuickAction(
    label: String,
    subtitle: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    selected: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier
            .heightIn(min = AppSpacing.touchTarget)
            .clickable(enabled = enabled, onClick = onClick),
        shape = MaterialTheme.shapes.small,
        color = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
        border = BorderStroke(
            0.5.dp,
            if (selected) MaterialTheme.colorScheme.primary.copy(alpha = 0.35f) else MaterialTheme.colorScheme.outlineVariant,
        ),
    ) {
        Column(
            Modifier.padding(horizontal = AppSpacing.small, vertical = AppSpacing.small),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(AppSpacing.xs),
        ) {
            Icon(
                icon,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
                tint = if (selected || enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                label,
                style = CompactTypography.secondary,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
            )
            Text(
                subtitle,
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun CompactAccountEquityCard(account: PaperTradingAccountDto?) {
    val colors = MaterialTheme.marketColors
    val pnl = account?.total_pnl ?: 0.0
    val pnlColor = if (pnl >= 0) colors.rise else colors.fall

    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.small),
        color = MaterialTheme.colorScheme.surface,
        shape = MaterialTheme.shapes.medium,
        border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("模拟账套总权益", style = CompactTypography.secondary, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.width(AppSpacing.small))
                        Surface(
                            color = MaterialTheme.colorScheme.primaryContainer,
                            shape = RoundedCornerShape(4.dp),
                        ) {
                            Text(
                                "模拟账户",
                                modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                                style = CompactTypography.caption,
                                color = MaterialTheme.colorScheme.primary,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                    }
                    Text(
                        "¥${account?.total_equity?.money() ?: "--"}",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        account?.total_return_percent?.paperSignedPercent() ?: "--",
                        style = CompactTypography.rowValue,
                        fontWeight = FontWeight.Bold,
                        color = pnlColor,
                    )
                    Text("累计收益率", style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            TradingRowDivider()

            Row(Modifier.fillMaxWidth()) {
                CompactEquityMetric("可用现金", "¥${account?.available_cash?.money() ?: "--"}", Modifier.weight(1f))
                CompactEquityMetric("持仓市值", "¥${account?.market_value?.money() ?: "--"}", Modifier.weight(1f))
                CompactEquityMetric(
                    "累计盈亏",
                    account?.total_pnl?.let { "¥${it.paperSignedMoney()}" } ?: "--",
                    Modifier.weight(1f),
                    valueColor = pnlColor,
                )
            }
        }
    }
}

@Composable
private fun CompactEquityMetric(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: Color = MaterialTheme.colorScheme.onSurface,
) {
    Column(modifier) {
        Text(label, style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = CompactTypography.rowValue, fontWeight = FontWeight.SemiBold, color = valueColor, maxLines = 1)
    }
}

@Composable
private fun StrategyStatusStrip(message: String, isError: Boolean) {
    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs),
        color = if (isError) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f),
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            message,
            modifier = Modifier.padding(horizontal = AppSpacing.medium, vertical = AppSpacing.small),
            style = CompactTypography.secondary,
            color = if (isError) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun CompactExecutionControlPanel(
    running: Boolean,
    changingEnabled: Boolean,
    status: PaperTradingStatusDto?,
    onEnabledChange: (Boolean) -> Unit,
    onRun: () -> Unit,
) {
    val enabled = status?.enabled == true
    val statusLabel = when {
        status == null -> "读取中"
        running || status.running -> "运行中"
        enabled -> "已开启"
        else -> "已暂停"
    }

    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.medium),
        color = MaterialTheme.colorScheme.surface,
        shape = MaterialTheme.shapes.medium,
        border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Terminal, contentDescription = null, modifier = Modifier.size(18.dp), tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(AppSpacing.small))
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("模拟账户自动执行", style = CompactTypography.sectionTitle)
                        Spacer(Modifier.width(AppSpacing.small))
                        Text(
                            statusLabel,
                            style = CompactTypography.caption,
                            fontWeight = FontWeight.SemiBold,
                            color = if (enabled || running) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(
                        when {
                            status == null -> "正在读取服务端执行状态"
                            running || status.running -> "当前正在执行既有决策与风控链"
                            enabled -> "按服务端既有调度与执行安全规则运行"
                            else -> "暂停自动轮换；开启后才允许手动运行"
                        },
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (changingEnabled) {
                    CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                } else {
                    Switch(
                        checked = enabled,
                        onCheckedChange = onEnabledChange,
                        enabled = status != null && status.running != true && !running,
                    )
                }
            }

            Text(
                "仅作用于模拟账套，不会向真实券商提交订单。",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Button(
                onClick = onRun,
                enabled = enabled && !changingEnabled && !running && status?.running != true,
                modifier = Modifier.fillMaxWidth().heightIn(min = AppSpacing.touchTarget),
                shape = MaterialTheme.shapes.small,
            ) {
                Icon(Icons.Default.PlayArrow, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(AppSpacing.small))
                Text(
                    when {
                        running || status?.running == true -> "正在运行模拟决策…"
                        !enabled -> "请先开启模拟账户自动执行"
                        else -> "立即运行决策轮换"
                    }
                )
            }
        }
    }
}

@Composable
private fun HistoryLink(runs: List<SimulationRunDto>, onClick: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal)
            .clickable(onClick = onClick),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(0.5.dp, MaterialTheme.colorScheme.outlineVariant),
        shape = MaterialTheme.shapes.small,
    ) {
        Row(
            Modifier.heightIn(min = AppSpacing.touchTarget).padding(horizontal = AppSpacing.medium, vertical = AppSpacing.small),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("执行链路记录", style = CompactTypography.rowTitle)
                Text(
                    "最近完成：${runs.firstOrNull()?.started_at?.let { paperBeijingTimestamp(it) } ?: "从未运行"}",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = "查看执行链路", tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun EmptyStatePlaceholder(message: String) {
    Box(
        Modifier.fillMaxWidth().padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xxLarge),
        contentAlignment = Alignment.Center,
    ) {
        Text(message, style = CompactTypography.secondary, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

@Composable
private fun PaperLogRow(log: PaperTradingLogDto, onOpenDecision: () -> Unit) {
    val isBuy = log.side == "BUY"
    val actionColor = if (isBuy) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall

    Column(
        Modifier
            .fillMaxWidth()
            .clickable(enabled = log.decision_id != null, onClick = onOpenDecision)
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.rowVertical),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Surface(color = actionColor.copy(alpha = 0.1f), shape = RoundedCornerShape(4.dp)) {
                Text(
                    if (isBuy) "B 买入" else "S 卖出",
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                    style = CompactTypography.caption,
                    fontWeight = FontWeight.Bold,
                    color = actionColor,
                )
            }
            Spacer(Modifier.width(AppSpacing.small))
            Text(
                log.name.ifBlank { log.symbol },
                style = CompactTypography.rowTitle,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.weight(1f))
            Text("¥${log.price.money()}", style = CompactTypography.rowValue)
        }
        Spacer(Modifier.height(AppSpacing.xs))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "${log.symbol} · ${paperBeijingTimestamp(log.executed_at)} · ${log.quantity.paperQuantity()} 股",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.weight(1f))
            if (log.decision_id != null) {
                Text("分析记录", style = CompactTypography.caption, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
            }
        }
        Spacer(Modifier.height(AppSpacing.rowVertical))
        TradingRowDivider()
    }
}

private fun Double.money(): String = "%.2f".format(Locale.US, this)
private fun Double.paperSignedMoney(): String = "%+.2f".format(Locale.US, this)
private fun Double.paperSignedPercent(): String = "%+.2f%%".format(Locale.US, this)
private fun Double.paperQuantity(): String = if (this % 1.0 == 0.0) toLong().toString() else "%.2f".format(Locale.US, this)
private fun paperBeijingTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse {
    value.replace('T', ' ').substringBefore("+").substringBefore("Z")
}

@Composable
private fun PaperLogHistoryDialog(
    logs: List<PaperTradingLogDto>,
    onDismiss: () -> Unit,
    onOpenDecision: (String?) -> Unit,
) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("完整操作记录") },
    text = {
        LazyColumn {
            items(logs, key = { it.id }) { log ->
                PaperLogRow(log, onOpenDecision = { onOpenDecision(log.decision_id) })
            }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)

@Composable
private fun PaperRunChainDialog(
    runs: List<SimulationRunDto>,
    onDismiss: () -> Unit,
    onOpenRun: (String) -> Unit,
) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("执行链路记录") },
    text = {
        if (runs.isEmpty()) {
            Text("还没有执行记录。")
        } else {
            LazyColumn {
                items(runs, key = { it.run_id }) { run ->
                    PaperRunRow(run, onClick = { onOpenRun(run.run_id) })
                }
            }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)

@Composable
private fun PaperRunRow(run: SimulationRunDto, onClick: () -> Unit) {
    val statusColor = when (run.status) {
        "completed" -> Color(0xFF2E7D32)
        "failed" -> Color(0xFFC62828)
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "${paperBeijingTimestamp(run.started_at)} · ${if (run.trigger == "manual") "手动" else "自动"}",
                fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.bodyMedium,
            )
            Spacer(Modifier.weight(1f))
            Text(
                if (run.status == "completed") "完成" else "失败",
                color = statusColor,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Bold,
            )
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, contentDescription = null, tint = MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

@Composable
private fun PaperRunDetailDialog(
    run: SimulationRunDetailDto?,
    loading: Boolean,
    error: String?,
    onDismiss: () -> Unit,
    onOpenDecision: (String?) -> Unit,
) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("链路详情") },
    text = {
        LazyColumn(
            modifier = Modifier.heightIn(max = 440.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            error?.let { message ->
                item {
                    Surface(color = MaterialTheme.colorScheme.errorContainer, shape = MaterialTheme.shapes.medium) {
                        Text(
                            message,
                            modifier = Modifier.padding(AppSpacing.medium),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                    }
                }
            }
            if (!loading && run == null && error == null) {
                item { Text("该次执行没有可展示的链路数据。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            run?.let { data ->
                item {
                    Text(
                        "${paperBeijingTimestamp(data.started_at)} · ${if (data.trigger == "manual") "手动" else "自动"}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(data.message.ifBlank { "本次执行已完成。" }, style = MaterialTheme.typography.bodySmall)
                }
                item { Text("标的结果", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold) }
                if (data.symbols.isEmpty()) {
                    item { Text("本轮没有可处理标的。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
                data.symbols.forEach { symbol ->
                    item {
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clickable(
                                    enabled = symbol.detail["decision_id"] is String,
                                    onClick = { onOpenDecision(symbol.detail["decision_id"] as? String) },
                                )
                                .padding(vertical = 4.dp),
                        ) {
                            Text(symbol.symbol, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                            Text(symbol.terminal_state, style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
                if (data.stages.isNotEmpty()) {
                    item {
                        Text(
                            "执行阶段",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(top = AppSpacing.small),
                        )
                    }
                    items(data.stages, key = { it.id }) { stage ->
                        Column(Modifier.fillMaxWidth()) {
                            Row(Modifier.fillMaxWidth()) {
                                Text(stage.stage, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                                Text(stage.status, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            if (stage.symbol != null) {
                                Text(stage.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)

@Composable
fun PaperDecisionAuditDialog(
    report: DecisionReportDto?,
    context: Map<String, Any>,
    loading: Boolean,
    error: String?,
    lineage: DecisionLineageDto? = null,
    onDismiss: () -> Unit,
) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("操作分析记录") },
    text = {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            if (error != null) {
                item { Text(error, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
            }
            report?.let { decision ->
                item { Text("${decision.symbol} · ${decision.action}", fontWeight = FontWeight.Bold) }
                item { Text(decision.summary, style = MaterialTheme.typography.bodySmall) }
                decision.evidence.forEach { evidence ->
                    item { Text("${evidence.title}: ${evidence.description}", style = MaterialTheme.typography.labelSmall) }
                }
            }
            if (!loading && error == null && report == null) {
                item { Text("该记录暂无可展示的决策内容。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
            lineage?.let { data ->
                item {
                    Text(
                        "审计上下文 ${data.context_id} · ${data.features.size} 个特征",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            if (context.isNotEmpty()) {
                item {
                    Text(
                        "已加载 ${context.size} 项执行上下文",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)
