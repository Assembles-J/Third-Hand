package com.thirdhand.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
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
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.components.DenseRowDivider
import com.thirdhand.app.ui.components.DenseStateTag
import com.thirdhand.app.ui.components.TradingPageHeader
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
                .onFailure { error = "模拟账套读取失败，请稍后重试" }
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
            .onSuccess {
                decisionReport = it.report
                decisionContext = it.context
            }
            .onFailure { decisionError = "无法读取操作分析记录，请稍后重试" }
        decisionLineage = runCatching { api.decisionLineage(decisionId) }.getOrNull()
        decisionLoading = false
    }

    PaperTradingOverview(
        dashboard = dashboard,
        presentation = positionPresentation,
        runs = runs,
        refreshing = refreshing,
        running = runningNow,
        changingEnabled = changingTradingEnabled,
        errorMessage = error,
        onRefresh = ::refresh,
        onEnabledChange = { enabled ->
            if (!changingTradingEnabled) {
                scope.launch {
                    changingTradingEnabled = true
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
                val result = runCatching { api.runPaperTradingNow() }
                if (result.isSuccess) {
                    snackbarHostState.showSnackbar(
                        result.getOrNull()?.message?.takeIf { it.isNotBlank() } ?: "决策轮换已完成"
                    )
                    refresh()
                } else {
                    snackbarHostState.showSnackbar("运行模拟决策失败，请稍后重试")
                }
                runningNow = false
            }
        },
        onOpenPosition = { position, name ->
            openedPositionTarget = ResearchTargetDto(
                symbol = position.symbol,
                name = name,
                status = "paper_position",
                last_activity_at = position.updated_at,
            )
        },
        onOpenRunChain = { showRunChain = true },
        onOpenDecision = { selectedDecisionId = it },
        onOpenAllLogs = { showAllLogs = true },
        snackbarHost = { SnackbarHost(snackbarHostState) },
    )

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
internal fun PaperTradingOverview(
    dashboard: PaperTradingDashboardDto?,
    presentation: PaperPositionPresentation,
    runs: List<SimulationRunDto>,
    refreshing: Boolean,
    running: Boolean,
    changingEnabled: Boolean,
    errorMessage: String?,
    onRefresh: () -> Unit,
    onEnabledChange: (Boolean) -> Unit,
    onRun: () -> Unit,
    onOpenPosition: (PaperTradingPositionDto, String) -> Unit,
    onOpenRunChain: () -> Unit,
    onOpenDecision: (String) -> Unit,
    onOpenAllLogs: () -> Unit,
    snackbarHost: @Composable () -> Unit = {},
) {
    Scaffold(
        topBar = {
            TradingPageHeader("策略执行", "模拟账套 · 决策驱动 · 风控执行") {
                IconButton(onClick = onRefresh, enabled = !refreshing) {
                    if (refreshing) {
                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Filled.Refresh, "刷新策略执行", tint = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        },
        snackbarHost = snackbarHost,
        containerColor = MaterialTheme.colorScheme.background,
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
        ) {
            item { AccountEquitySummary(dashboard?.account) }

            errorMessage?.let { message ->
                item { PaperTradingStatusMessage(message) }
            }

            item { TradingSection("持仓明细") }

            val positions = dashboard?.account?.positions.orEmpty()
            if (positions.isEmpty()) {
                item { EmptyStatePlaceholder("当前模拟账套暂无持仓") }
            } else {
                item {
                    PaperPositionsTable(
                        positions = positions,
                        presentation = presentation,
                        onOpenDetail = onOpenPosition,
                    )
                }
            }

            item { TradingSection("执行控制") }
            item {
                ExecutionControlPanel(
                    running = running,
                    changingEnabled = changingEnabled,
                    status = dashboard?.status,
                    onEnabledChange = onEnabledChange,
                    onRun = onRun,
                )
            }

            item { HistoryLink(runs = runs, onClick = onOpenRunChain) }

            item { TradingSection("最近成交") }

            val executedLogs = dashboard?.logs.orEmpty().filter { it.status == "executed" }
            if (executedLogs.isEmpty()) {
                item { EmptyStatePlaceholder("暂无成交记录") }
            }

            items(executedLogs.take(5), key = { it.id }) { log ->
                PaperLogRow(log, onOpenDecision = {
                    log.decision_id?.let(onOpenDecision)
                })
            }

            if (dashboard?.logs.orEmpty().size > 5) {
                item {
                    TextButton(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = AppSpacing.contentHorizontal),
                        onClick = onOpenAllLogs,
                    ) {
                        Text("查看完整操作与拦截记录", style = CompactTypography.secondary)
                    }
                }
            }
        }
    }
}

@Composable
internal fun AccountEquitySummary(account: PaperTradingAccountDto?) {
    val marketColors = MaterialTheme.marketColors
    val returnValue = account?.total_return_percent
    val returnColor = when {
        returnValue == null -> MaterialTheme.colorScheme.onSurfaceVariant
        returnValue >= 0 -> marketColors.rise
        else -> marketColors.fall
    }
    val pnlValue = account?.total_pnl
    val pnlColor = when {
        pnlValue == null -> MaterialTheme.colorScheme.onSurface
        pnlValue >= 0 -> marketColors.rise
        else -> marketColors.fall
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier.padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.sectionVertical,
            ),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "模拟账套总权益",
                        style = CompactTypography.secondary,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        "¥${account?.total_equity?.money() ?: "---"}",
                        style = CompactTypography.pageTitle.copy(
                            fontSize = 20.sp,
                            lineHeight = 26.sp,
                            fontWeight = FontWeight.Bold,
                        ),
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
                DenseStateTag(
                    text = returnValue?.let { "%+.2f%%".format(Locale.US, it) } ?: "--",
                    color = returnColor,
                )
            }

            HorizontalDivider(
                modifier = Modifier.padding(vertical = AppSpacing.small),
                thickness = 0.5.dp,
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f),
            )

            Row(Modifier.fillMaxWidth()) {
                AccountMetric(
                    label = "可用现金",
                    value = "¥${account?.available_cash?.money() ?: "--"}",
                    modifier = Modifier.weight(1f),
                )
                AccountMetric(
                    label = "持仓市值",
                    value = "¥${account?.market_value?.money() ?: "--"}",
                    modifier = Modifier.weight(1f),
                )
                AccountMetric(
                    label = "累计盈亏",
                    value = pnlValue?.let { "¥%+.2f".format(Locale.US, it) } ?: "--",
                    valueColor = pnlColor,
                    modifier = Modifier.weight(1f),
                )
            }
        }
    }
}

@Composable
private fun AccountMetric(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: Color = MaterialTheme.colorScheme.onSurface,
) {
    Column(modifier) {
        Text(
            label,
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            style = CompactTypography.rowValue,
            color = valueColor,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
internal fun ExecutionControlPanel(
    running: Boolean,
    changingEnabled: Boolean,
    status: PaperTradingStatusDto?,
    onEnabledChange: (Boolean) -> Unit,
    onRun: () -> Unit,
) {
    val enabled = status?.enabled == true
    val stateText = when {
        status == null -> "读取中"
        running || status.running -> "运行中"
        enabled -> "已开启"
        else -> "已暂停"
    }
    val stateColor = if (enabled || running || status?.running == true) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.onSurfaceVariant
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = AppSpacing.touchTarget),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("模拟账户自动执行", style = CompactTypography.rowTitle)
                    Spacer(Modifier.width(AppSpacing.denseGap))
                    DenseStateTag(stateText, stateColor)
                }
                Text(
                    when {
                        status == null -> "正在读取模拟账套执行状态"
                        enabled -> "按既有决策与风控链自动轮换"
                        else -> "开启后恢复既有模拟账套自动轮换"
                    },
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.width(AppSpacing.small))
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
            "仅控制模拟账套，不会向真实券商提交订单。",
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(top = AppSpacing.xs),
        )

        Button(
            onClick = onRun,
            enabled = enabled && !changingEnabled && !running && status?.running != true,
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = AppSpacing.small)
                .heightIn(min = AppSpacing.touchTarget),
            shape = RoundedCornerShape(8.dp),
            contentPadding = PaddingValues(
                horizontal = AppSpacing.medium,
                vertical = AppSpacing.small,
            ),
        ) {
            Icon(Icons.Default.PlayArrow, null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(AppSpacing.small))
            Text(
                when {
                    running || status?.running == true -> "正在运行决策轮换"
                    !enabled -> "请先开启模拟账户自动执行"
                    else -> "立即运行决策轮换"
                },
                style = CompactTypography.body,
            )
        }

        DenseRowDivider(
            modifier = Modifier.padding(top = AppSpacing.small),
            inset = false,
        )
    }
}

@Composable
internal fun HistoryLink(runs: List<SimulationRunDto>, onClick: () -> Unit) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .heightIn(min = AppSpacing.touchTarget)
                .padding(
                    horizontal = AppSpacing.contentHorizontal,
                    vertical = AppSpacing.rowVertical,
                ),
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
            Icon(
                Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = "查看执行链路",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        DenseRowDivider(inset = true)
    }
}

@Composable
private fun PaperTradingStatusMessage(message: String) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.xs,
            ),
        color = MaterialTheme.colorScheme.errorContainer,
        shape = RoundedCornerShape(6.dp),
    ) {
        Text(
            message,
            modifier = Modifier.padding(
                horizontal = AppSpacing.medium,
                vertical = AppSpacing.small,
            ),
            style = CompactTypography.secondary,
            color = MaterialTheme.colorScheme.onErrorContainer,
        )
    }
}

@Composable
private fun EmptyStatePlaceholder(msg: String) {
    Box(
        Modifier
            .fillMaxWidth()
            .padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.xLarge,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            msg,
            style = CompactTypography.secondary,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun PaperLogRow(log: PaperTradingLogDto, onOpenDecision: () -> Unit) {
    val isBuy = log.side == "BUY"
    val color = if (isBuy) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall
    val hasDecision = log.decision_id != null

    Column(
        Modifier
            .fillMaxWidth()
            .clickable(enabled = hasDecision, onClick = onOpenDecision)
            .padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.rowVertical,
            ),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            DenseStateTag(
                text = if (isBuy) "B 买入" else "S 卖出",
                color = color,
            )
            Spacer(Modifier.width(AppSpacing.small))
            Text(
                log.name.ifBlank { log.symbol },
                style = CompactTypography.rowTitle,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.weight(1f))
            Text("¥${log.price.money()}", style = CompactTypography.rowValue)
        }
        Row(
            modifier = Modifier.padding(top = AppSpacing.xxs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "${log.symbol} · ${paperBeijingTimestamp(log.executed_at)} · ${log.quantity.toInt()} 股",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.weight(1f))
            Text(
                if (hasDecision) "分析记录" else "无分析记录",
                style = CompactTypography.caption,
                color = if (hasDecision) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
            )
        }
        DenseRowDivider(
            modifier = Modifier.padding(top = AppSpacing.rowVertical),
            inset = false,
        )
    }
}

private fun Double.money() = "%.2f".format(Locale.US, this)

private fun paperBeijingTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse {
    value.replace('T', ' ')
        .substringBefore("+")
        .substringBefore("Z")
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
                PaperLogRow(
                    log,
                    onOpenDecision = { onOpenDecision(log.decision_id) },
                )
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
    Column(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(vertical = 10.dp),
    ) {
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
            Icon(
                Icons.AutoMirrored.Filled.KeyboardArrowRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.outlineVariant,
            )
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
            if (loading) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            }
            error?.let { message ->
                item {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer,
                        shape = MaterialTheme.shapes.medium,
                    ) {
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
                item {
                    Text(
                        "该次执行没有可展示的链路数据。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            run?.let { data ->
                item {
                    Text(
                        "${paperBeijingTimestamp(data.started_at)} · ${if (data.trigger == "manual") "手动" else "自动"}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        data.message.ifBlank { "本次执行已完成。" },
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                item {
                    Text(
                        "标的结果",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                    )
                }
                if (data.symbols.isEmpty()) {
                    item {
                        Text(
                            "本轮没有可处理标的。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                data.symbols.forEach { symbol ->
                    item {
                        Row(
                            Modifier
                                .fillMaxWidth()
                                .clickable(
                                    enabled = symbol.detail["decision_id"] is String,
                                    onClick = {
                                        onOpenDecision(symbol.detail["decision_id"] as? String)
                                    },
                                )
                                .padding(vertical = 4.dp),
                        ) {
                            Text(
                                symbol.symbol,
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.weight(1f),
                            )
                            Text(
                                symbol.terminal_state,
                                style = MaterialTheme.typography.labelSmall,
                            )
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
                                Text(
                                    stage.stage,
                                    style = MaterialTheme.typography.bodySmall,
                                    fontWeight = FontWeight.SemiBold,
                                    modifier = Modifier.weight(1f),
                                )
                                Text(
                                    stage.status,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            if (stage.symbol != null) {
                                Text(
                                    stage.symbol,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
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
            if (loading) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            }
            error?.let { message ->
                item {
                    Text(
                        message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            report?.let { reportItem ->
                item {
                    Text(
                        "${reportItem.symbol} · ${reportItem.action}",
                        fontWeight = FontWeight.Bold,
                    )
                }
                item {
                    Text(
                        reportItem.summary,
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                reportItem.evidence.forEach { evidence ->
                    item {
                        Text(
                            "${evidence.title}: ${evidence.description}",
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                }
            }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)
