package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

@Composable
fun PaperTradingScreen(onOpenDetail: (ResearchTargetDto) -> Unit) {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var dashboard by remember { mutableStateOf<PaperTradingDashboardDto?>(null) }
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
    fun refresh() {
        if (refreshing) return
        scope.launch {
            refreshing = true
            runCatching { api.paperTradingDashboard() }
                .onSuccess { dashboard = it; error = null }
                .onFailure { error = "暂时无法读取交易账套：${it.message ?: "请检查服务连接"}" }
            runs = runCatching { api.paperTradingRuns(limit = 20) }.getOrDefault(emptyList())
            refreshing = false
        }
    }
    LaunchedEffect(Unit) { refresh() }
    LaunchedEffect(dashboard?.status?.running, dashboard?.status?.last_status) {
        if (dashboard?.status?.running == true) {
            delay(2_000)
            refresh()
        }
    }
    LaunchedEffect(selectedDecisionId) {
        val decisionId = selectedDecisionId ?: return@LaunchedEffect
        decisionLoading = true; decisionError = null; decisionReport = null; decisionLineage = null
        runCatching { api.paperTradingDecisionAudit(decisionId) }
            .onSuccess { audit -> decisionReport = audit.report; decisionContext = audit.context; decisionLineage = runCatching { api.decisionLineage(decisionId) }.getOrNull() }
            .onFailure { decisionError = "无法读取该次决策留档：${it.message ?: "记录可能已过期"}" }
        decisionLoading = false
    }
    LaunchedEffect(selectedRunDetailId) {
        val runId = selectedRunDetailId ?: return@LaunchedEffect
        runDetailLoading = true; runDetailError = null; runDetail = null
        runCatching { api.paperTradingRunDetail(runId) }
            .onSuccess { runDetail = it }
            .onFailure { runDetailError = "无法读取本轮链路：${it.message ?: "请检查服务连接"}" }
        runDetailLoading = false
    }
    val account = dashboard?.account
    val status = dashboard?.status
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 28.dp),
    ) {
        item {
            TradingPageHeader("交易", "交易账套 · 不连接券商 · 所有成交均可追溯") {
                IconButton(onClick = ::refresh, enabled = !refreshing) {
                    if (refreshing) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, "刷新交易账套")
                }
            }
        }
        item {
            Column(Modifier.padding(horizontal = 20.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !runningNow,
                    onClick = {
                        scope.launch {
                            runningNow = true
                            message = "任务已提交，正在后台准备行情、日线、风险与决策；可离开页面，完成后会显示结果。"
                            message = runCatching { api.runPaperTradingNow() }.fold(
                                onSuccess = { it.message },
                                onFailure = { "提交交易任务失败：${it.message ?: "请检查服务连接"}" },
                            )
                            runningNow = false
                            refresh()
                        }
                    },
                ) {
                    if (runningNow) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.PlayArrow, null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (runningNow) "AI 正在分析市场" else "立即运行一轮")
                }
                message?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
        item {
            Card(
                modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("账套总权益", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                            Text("¥${account?.total_equity?.money() ?: "--"}", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimaryContainer)
                        }
                        Column(horizontalAlignment = Alignment.End) {
                            Text("累计收益", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
                            Text(account?.total_return_percent?.let { "${it.signed()}%" } ?: "--", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onPrimaryContainer)
                        }
                    }
                    TradingRowDivider()
                    Row {
                        PaperMetric("可用现金", "¥${account?.available_cash?.money() ?: "--"}", Modifier.weight(1f))
                        PaperMetric("持仓市值", "¥${account?.market_value?.money() ?: "--"}", Modifier.weight(1f))
                        PaperMetric("累计盈亏", "¥${account?.total_pnl?.money() ?: "--"}", Modifier.weight(1f))
                    }
                    Text("累计净入金 ¥${account?.net_contributions?.money() ?: "--"} · 收益已剔除后续入金与出金", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onPrimaryContainer)
                }
            }
        }
        item {
            val enabled = status?.enabled == true
            Column(Modifier.padding(horizontal = 20.dp, vertical = 14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(if (status?.running == true) "自动执行中" else if (enabled) "自动执行已开启" else "自动执行已关闭", fontWeight = FontWeight.Bold)
                if (status?.running == true) LinearProgressIndicator(Modifier.fillMaxWidth())
                Text(
                    when {
                        status == null -> "正在读取执行状态…"
                        !enabled -> "请到管理页开启；仅在开盘时间按设置间隔执行。"
                        status.running -> "本轮正在分析，完成后会自动刷新账套。"
                        status.seconds_until_next_run > 0 -> "下一次检查约在 ${maxOf(1, status.seconds_until_next_run / 60)} 分钟后。"
                        else -> "等待下一次市场检查。"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                status?.last_finished_at?.let { Text("最近完成：${paperBeijingTimestamp(it)} · 执行 ${status.last_executed} 笔", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            }
        }
        item {
            Column(
                Modifier.fillMaxWidth().clickable { showRunChain = true }.padding(horizontal = 20.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("本轮执行链路", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.weight(1f))
                    Text("最近 ${runs.size} 轮", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, "查看执行链路", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text("候选 → 行情 → 日线 → 风险 → 新闻 → 决策 → 执行；每只股票都有明确终态", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                runs.firstOrNull()?.let { latest ->
                    Text(
                        "最近：${paperBeijingTimestamp(latest.started_at)} · ${if (latest.trigger == "manual") "手动" else "自动"} · 生成 ${latest.generated} · 执行 ${latest.executed} · 跳过 ${latest.skipped} · ${paperRunStatusLabel(latest.status)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            TradingRowDivider()
        }
        error?.let { item { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 8.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
        item { TradingSection("持仓", "成本、现价和盈亏都来自这套独立账本") }
        if (account?.positions.isNullOrEmpty()) item {
            Text("当前没有持仓。可点击“立即运行一轮”，或开启自动执行后等待下一轮决策。", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        items(account?.positions.orEmpty(), key = { it.symbol }) { position ->
            Column(Modifier.fillMaxWidth().clickable { onOpenDetail(ResearchTargetDto(position.symbol, position.name, "paper_position", position.updated_at)) }.padding(horizontal = 20.dp, vertical = 12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(position.name.ifBlank { position.symbol }, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleSmall)
                        Text(position.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text("¥${position.last_price.money()}", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleMedium)
                        Text("${position.unrealized_return_percent.signed()}%", color = if (position.unrealized_pnl >= 0) MaterialTheme.colorScheme.tertiary else MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelMedium)
                    }
                }
                Row(Modifier.padding(top = 10.dp).fillMaxWidth()) {
                    PaperPositionMetric("持仓", "${position.quantity.clean()} 股", Modifier.weight(1f))
                    PaperPositionMetric("成本", "¥${position.average_cost.money()}", Modifier.weight(1f))
                    PaperPositionMetric("市值", "¥${position.market_value.money()}", Modifier.weight(1f))
                    PaperPositionMetric("浮盈", "¥${position.unrealized_pnl.money()}", Modifier.weight(1f))
                }
                Spacer(Modifier.height(8.dp)); TradingRowDivider()
            }
        }
        item { TradingSection("最近成交", "仅展示最近 6 笔成交；B / S 不会与实际操作混淆") }
        val executedLogs = dashboard?.logs.orEmpty().filter { it.status == "executed" }
        if (executedLogs.isEmpty()) item { Text("暂时没有成交。被拦截或不满足条件的决策会保存在完整记录中。", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(executedLogs.take(6), key = { it.id }) { log -> PaperLogRow(log, onOpenDecision = { selectedDecisionId = log.decision_id }) }
        if (dashboard?.logs.orEmpty().size > 6) item { TextButton(modifier = Modifier.padding(horizontal = 12.dp), onClick = { showAllLogs = true }) { Text("查看全部操作与拦截记录") } }
    }
    if (showAllLogs) PaperLogHistoryDialog(dashboard?.logs.orEmpty(), onDismiss = { showAllLogs = false }, onOpenDecision = { selectedDecisionId = it })
    if (showRunChain) PaperRunChainDialog(runs, onDismiss = { showRunChain = false }, onOpenRun = { selectedRunDetailId = it })
    if (selectedRunDetailId != null) PaperRunDetailDialog(runDetail, runDetailLoading, runDetailError, onDismiss = { selectedRunDetailId = null }, onOpenDecision = { selectedDecisionId = it })
    if (selectedDecisionId != null) PaperDecisionAuditDialog(decisionReport, decisionContext, decisionLoading, decisionError, decisionLineage, onDismiss = { selectedDecisionId = null })
}

@Composable private fun PaperMetric(label: String, value: String, modifier: Modifier) = Column(modifier) {
    Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onPrimaryContainer)
    Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onPrimaryContainer)
}

@Composable private fun PaperPositionMetric(label: String, value: String, modifier: Modifier) = Column(modifier) {
    Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
}

@Composable private fun PaperLogRow(log: PaperTradingLogDto, onOpenDecision: () -> Unit) {
    val action = when (log.side) { "BUY" -> "B  买入"; "SELL" -> "S  卖出"; else -> "跳过" }
    Column(Modifier.fillMaxWidth().clickable(enabled = log.decision_id != null, onClick = onOpenDecision).padding(horizontal = 20.dp, vertical = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("$action · ${log.name.ifBlank { log.symbol }}", fontWeight = FontWeight.SemiBold)
                Text("${log.symbol} · ${paperBeijingTimestamp(log.executed_at)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(if (log.status == "skipped") "未成交" else "¥${log.price.money()}", color = if (log.status == "skipped") MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
        }
        Text(if (log.status == "skipped") paperSkipReason(log.reason) else "${log.quantity.clean()} 股 · 费用 ¥${log.fee.money()} · 现金 ¥${log.cash_before.money()} → ¥${log.cash_after.money()}", Modifier.padding(top = 4.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (log.status == "executed") {
            Text("成交语义 ${log.fill_price_mode ?: "未记录"}${log.execution_quote_at?.let { " · 报价 $it" }.orEmpty()}${log.execution_quote_source?.let { " · 来源 $it" }.orEmpty()}", Modifier.padding(top = 3.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(8.dp)); TradingRowDivider()
    }
}

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
        if (runs.isEmpty()) Text("还没有执行记录。点击“立即运行一轮”后，这里会展示候选、行情、日线、风险、新闻、决策与执行的完整链路。")
        else LazyColumn { items(runs, key = { it.run_id }) { run -> PaperRunRow(run, onClick = { onOpenRun(run.run_id) }) } }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)

@Composable private fun PaperRunRow(run: SimulationRunDto, onClick: () -> Unit) {
    val statusColor = when (run.status) { "completed" -> Color(0xFF2E7D32); "failed" -> Color(0xFFC62828); else -> MaterialTheme.colorScheme.onSurfaceVariant }
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("${paperBeijingTimestamp(run.started_at)} · ${if (run.trigger == "manual") "手动" else "自动"}", fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.weight(1f))
            Text(paperRunStatusLabel(run.status), color = statusColor, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("候选 ${run.symbol_count} · 生成 ${run.generated} · 执行 ${run.executed} · 跳过 ${run.skipped}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (run.message.isNotBlank()) Text(run.message, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable private fun PaperRunDetailDialog(run: SimulationRunDetailDto?, loading: Boolean, error: String?, onDismiss: () -> Unit, onOpenDecision: (String?) -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text(run?.let { "执行链路 · ${paperBeijingTimestamp(it.started_at)}" } ?: "执行链路") },
    text = {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("正在加载本轮链路…") }
            error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
            run?.let { data ->
                item {
                    Text(data.message, style = MaterialTheme.typography.bodySmall)
                    Text("状态 ${paperRunStatusLabel(data.status)} · 候选 ${data.symbol_count} · 生成 ${data.generated} · 执行 ${data.executed} · 跳过 ${data.skipped}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                item { Text("阶段时间线", fontWeight = FontWeight.SemiBold) }
                data.stages.forEach { stage -> item { PaperStageRow(stage) } }
                if (data.symbols.isNotEmpty()) {
                    item { Text("每只股票终态", fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 6.dp)) }
                    data.symbols.forEach { symbol -> item { PaperSymbolStateRow(symbol, onOpenDecision = { onOpenDecision(symbol.detail["decision_id"] as? String) }) } }
                }
            }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)

@Composable private fun PaperStageRow(stage: SimulationRunStageDto) {
    val label = paperStageLabels[stage.stage] ?: stage.stage
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(label, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
            stage.symbol?.let { Text(" · $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            Spacer(Modifier.weight(1f))
            Text("${paperStageStatusLabel(stage.status)}${if (stage.elapsed_ms > 0) " · ${stage.elapsed_ms}ms" else ""}", color = paperStageStatusColor(stage.status), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
        }
        val reason = stage.detail["reason"] as? String ?: stage.detail["error"] as? String
        if (!reason.isNullOrBlank()) Text(paperTerminalReason(reason), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable private fun PaperSymbolStateRow(symbol: SimulationRunSymbolDto, onOpenDecision: () -> Unit) {
    val terminal = paperTerminalLabels[symbol.terminal_state] ?: symbol.terminal_state
    val decisionId = symbol.detail["decision_id"] as? String
    val symbolName = symbol.detail["name"] as? String ?: ""
    val terminalColor = when (symbol.terminal_state) {
        "executed" -> Color(0xFF2E7D32)
        "skipped_data_unavailable", "blocked_by_gate", "skipped_execution" -> Color(0xFFC62828)
        "decision_generated", "decision_reused" -> Color(0xFF1565C0)
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }
    Column(Modifier.fillMaxWidth().clickable(enabled = decisionId != null, onClick = onOpenDecision).padding(vertical = 4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(if (symbolName.isNotBlank() && symbolName != symbol.symbol) "$symbolName · ${symbol.symbol}" else symbol.symbol, fontWeight = FontWeight.SemiBold, style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.width(8.dp))
            Text(terminal, color = terminalColor, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
            if (decisionId != null) {
                Spacer(Modifier.weight(1f))
                Text("查看决策", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, "查看决策", tint = MaterialTheme.colorScheme.primary)
            }
        }
        val reason = symbol.detail["reason"] as? String
        if (!reason.isNullOrBlank()) Text(paperTerminalReason(reason), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

private val paperStageLabels = mapOf(
    "candidate_pool" to "候选池",
    "market_quotes" to "行情",
    "daily_history" to "日线",
    "risk" to "风险",
    "news" to "新闻",
    "decision" to "决策",
    "execution" to "执行",
    "equity_snapshot" to "净值快照",
)
private val paperTerminalLabels = mapOf(
    "decision_generated" to "已生成决策",
    "decision_reused" to "复用已有决策",
    "skipped_data_unavailable" to "数据不可用，跳过",
    "blocked_by_gate" to "门槛拦截",
    "not_due" to "未到执行日",
    "executed" to "已执行",
    "skipped_execution" to "执行跳过",
)
private fun paperRunStatusLabel(status: String): String = when (status) {
    "completed" -> "已完成"; "failed" -> "失败"; "running" -> "进行中"; else -> status
}
private fun paperStageStatusLabel(status: String): String = when (status) {
    "ok" -> "完成"; "failed" -> "失败"; "skipped" -> "跳过"; else -> status
}
private fun paperStageStatusColor(status: String): Color = when (status) {
    "ok" -> Color(0xFF2E7D32); "failed" -> Color(0xFFC62828); "skipped" -> Color(0xFF9E9E9E); else -> Color(0xFF616161)
}
private fun paperTerminalReason(reason: String): String = when {
    reason.contains("missing_quote") -> "缺少可用行情"
    reason.contains("insufficient_daily_bars") -> "本地日线不足 60 根"
    reason.contains("no_decision_report") -> "本轮没有可执行的决策"
    reason.contains("execution_not_due_next_market_session") -> "决策未到期：需在下一交易日成交"
    reason.contains("execution_action_gate_blocked") -> "动作门槛未放行"
    reason.contains("execution_quote_missing") -> "缺少成交报价"
    reason.contains("invalid_side_or_sizing") -> "动作或数量无效"
    reason.contains("paper_sell_blocked_no_position") -> "没有可卖出的持仓"
    reason.contains("decision_already_executed") -> "该决策已执行，避免重复"
    reason.contains("within_interval") -> "执行间隔内复用已有决策"
    reason.contains("waiting_for_daily_history") -> "等待日线补齐（限频中）"
    reason.contains("no_daily_bars") -> "本地没有可用日线"
    reason.contains("upstream_unavailable") -> "行情源暂不可用"
    else -> reason
}

@Composable fun PaperDecisionAuditDialog(report: DecisionReportDto?, context: Map<String, Any>, loading: Boolean, error: String?, lineage: DecisionLineageDto? = null, onDismiss: () -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("操作分析记录") },
    text = {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("正在加载完整决策留档…") }
            error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
            report?.let { item {
                Text("${it.name.ifBlank { it.symbol }} · ${it.action} · ${paperBeijingTimestamp(it.generated_at)}", fontWeight = FontWeight.Bold)
                Text(it.summary, style = MaterialTheme.typography.bodySmall)
                it.data_quality?.let { quality ->
                    DecisionAuditLine("输入完整度", "${quality.score_percent}% · ${quality.status}", error = quality.status != "ready")
                    quality.action_gates.firstOrNull { gate -> gate.action == it.action }?.let { gate ->
                        DecisionAuditLine("本动作权限", gate.permission + gate.unavailable_fields.takeIf { fields -> fields.isNotEmpty() }?.let { " · 缺少 ${it.joinToString()}" }.orEmpty(), error = gate.permission != "allowed")
                    }
                    quality.source_freshness.forEach { source ->
                        DecisionAuditLine("数据时效 · ${source.source_key}", "${source.status}${source.as_of?.let { " · 截至 $it" }.orEmpty()}${source.reason?.let { " · $it" }.orEmpty()}", error = source.status != "fresh")
                    }
                }
                it.sizing?.let { sizing -> DecisionAuditLine("仓位计算", "建议 ${sizing.suggested_quantity?.clean() ?: "--"} 股；目标 ${sizing.target_quantity?.clean() ?: "--"} 股；现金上限 ${sizing.quantity_by_cash?.clean() ?: "--"} 股") }
                DecisionAuditLine("成交语义", "${it.execution_price_mode ?: "未记录"}${it.execution_eligible_after?.let { " · 决策报价截至 $it" }.orEmpty()}")
                if (it.audit_versions.isNotEmpty()) DecisionAuditLine("版本快照", it.audit_versions.entries.joinToString(" · ") { "${it.key}=${it.value.take(12)}" })
                if (it.action_candidates.isNotEmpty()) DecisionAuditLine("规则候选", it.action_candidates.joinToString { candidate -> "${candidate.action}（评分 ${"%.2f".format(candidate.policy_score)}）" })
                it.operation_items?.forEach { operation -> DecisionAuditLine(operation.title, operation.trigger) }
                Text("AI 推理依据", fontWeight = FontWeight.SemiBold)
                it.ai_assessment?.reasoning_steps?.forEach { step -> DecisionAuditLine(step.stage, step.summary + step.evidence_ids.takeIf { ids -> ids.isNotEmpty() }?.let { "\n引用证据：${it.joinToString()}" }.orEmpty()) }
                Text("证据数据点", fontWeight = FontWeight.SemiBold)
                it.evidence.forEach { evidence -> DecisionAuditLine(evidence.title, evidence.description) }
                if (it.ai_assessment?.missing_evidence?.isNotEmpty() == true) DecisionAuditLine("缺失数据", it.ai_assessment.missing_evidence.joinToString(), error = true)
                lineage?.let { data ->
                    DecisionAuditLine("数据链路", "影子特征 ${data.features.size} 项 · 原始快照 ${data.snapshots.size} 条（仅审计，不改变本次规则）")
                    data.features.forEach { feature -> DecisionAuditLine(feature.feature_key, "${feature.value ?: "不可用"} · ${feature.quality_status} · 可用时间 ${feature.available_at}") }
                }
                DecisionAuditContext(context)
                Text("输入快照 ${it.input_hash.take(12)} · 模型 ${it.model ?: "规则引擎"}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } }
        }
    },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)

@Composable private fun DecisionAuditLine(label: String, value: String, error: Boolean = false) = Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
    Text(label, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
    Text(value, style = MaterialTheme.typography.bodySmall, color = if (error) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable private fun DecisionAuditContext(context: Map<String, Any>) {
    if (context.isEmpty()) return
    fun field(section: String, key: String): String? = (context[section] as? Map<*, *>)?.get(key)?.toString()
    Text("决策输入快照", fontWeight = FontWeight.SemiBold)
    field("quote", "price")?.let { DecisionAuditLine("市场价格", it) }
    field("account", "available_cash")?.let { DecisionAuditLine("可用资金", it) }
    field("position", "quantity")?.let { DecisionAuditLine("持仓数量", "$it 股") }
    field("daily_bars", "count")?.let { DecisionAuditLine("日线数据范围", "$it 根") }
    field("data_quality", "status")?.let { DecisionAuditLine("数据质量", it) }
    listOf("technical" to "技术因子", "risk" to "风险因子", "market_regime" to "市场环境", "relative_strength" to "相对强弱").forEach { (key, label) ->
        val values = context[key] as? Map<*, *> ?: return@forEach
        val readable = values.entries.filter { it.value != null }.joinToString(" · ") { "${it.key}=${it.value}" }
        if (readable.isNotBlank()) DecisionAuditLine(label, readable)
    }
}

private fun Double.money() = "%.2f".format(Locale.US, this)
private fun Double.clean() = if (this % 1.0 == 0.0) toInt().toString() else "%.2f".format(Locale.US, this)
private fun Double.signed() = "%.2f".format(Locale.US, this)
private fun paperBeijingTimestamp(value: String): String = runCatching { OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8)).format(DateTimeFormatter.ofPattern("MM-dd HH:mm")) }.getOrElse { value.replace('T', ' ').substringBefore("+").substringBefore("Z") }
private fun paperSkipReason(reason: String): String = when {
    reason.contains("insufficient_paper_cash") -> "可用资金不足，未买入"
    reason.contains("insufficient_paper_position") -> "持仓不足，未卖出"
    reason.contains("paper_t1_unsellable_quantity") -> "A 股 T+1：今日买入的仓位下一交易日才能卖出"
    reason.contains("already_executed") -> "该份决策已执行，避免重复交易"
    reason.contains("100_share_lot") -> "数量不符合 A 股一手 100 股规则"
    reason.contains("no_executable") -> "当前没有满足条件的买卖信号"
    else -> "本轮暂不操作：$reason"
}
