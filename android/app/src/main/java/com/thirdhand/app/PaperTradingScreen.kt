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
import androidx.compose.ui.text.font.FontWeight
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
    var selectedDecisionId by remember { mutableStateOf<String?>(null) }
    var decisionReport by remember { mutableStateOf<DecisionReportDto?>(null) }
    var decisionContext by remember { mutableStateOf<Map<String, Any>>(emptyMap()) }
    var decisionLoading by remember { mutableStateOf(false) }
    var decisionError by remember { mutableStateOf<String?>(null) }
    fun refresh() {
        if (refreshing) return
        scope.launch {
            refreshing = true
            runCatching { api.paperTradingDashboard() }
                .onSuccess { dashboard = it; error = null }
                .onFailure { error = "暂时无法读取模拟账套：${it.message ?: "请检查服务连接"}" }
            refreshing = false
        }
    }
    LaunchedEffect(Unit) { refresh() }
    LaunchedEffect(selectedDecisionId) {
        val decisionId = selectedDecisionId ?: return@LaunchedEffect
        decisionLoading = true; decisionError = null; decisionReport = null
        runCatching { api.paperTradingDecisionAudit(decisionId) }
            .onSuccess { decisionReport = it.report; decisionContext = it.context }
            .onFailure { decisionError = "无法读取该次决策留档：${it.message ?: "记录可能已过期"}" }
        decisionLoading = false
    }
    val account = dashboard?.account
    val status = dashboard?.status
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 28.dp),
    ) {
        item {
            TradingPageHeader("模拟", "独立账套 · 不连接券商 · 所有成交均可追溯") {
                IconButton(onClick = ::refresh, enabled = !refreshing) {
                    if (refreshing) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, "刷新模拟账套")
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
                            message = "正在请求 AI 完成一轮市场判断…"
                            message = runCatching { api.runPaperTradingNow() }.fold(
                                onSuccess = { "${it.message}：执行 ${it.executed} 笔，暂不操作 ${it.skipped} 笔" },
                                onFailure = { "立即模拟失败：${it.message ?: "请检查服务连接"}" },
                            )
                            runningNow = false
                            refresh()
                        }
                    },
                ) {
                    if (runningNow) CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.PlayArrow, null)
                    Spacer(Modifier.width(8.dp))
                    Text(if (runningNow) "AI 正在分析市场" else "立即模拟一次")
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
        error?.let { item { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 8.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
        item { TradingSection("模拟持仓", "成本、现价和盈亏都来自这套独立账本") }
        if (account?.positions.isNullOrEmpty()) item {
            Text("当前没有模拟持仓。可点击“立即模拟一次”，或开启自动执行后等待下一轮决策。", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
        item { TradingSection("最近成交", "仅展示最近 6 笔模拟成交；B / S 不会与实际操作混淆") }
        val executedLogs = dashboard?.logs.orEmpty().filter { it.status == "executed" }
        if (executedLogs.isEmpty()) item { Text("暂时没有模拟成交。被拦截或不满足条件的决策会保存在完整记录中。", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(executedLogs.take(6), key = { it.id }) { log -> PaperLogRow(log, onOpenDecision = { selectedDecisionId = log.decision_id }) }
        if (dashboard?.logs.orEmpty().size > 6) item { TextButton(modifier = Modifier.padding(horizontal = 12.dp), onClick = { showAllLogs = true }) { Text("查看全部操作与拦截记录") } }
    }
    if (showAllLogs) PaperLogHistoryDialog(dashboard?.logs.orEmpty(), onDismiss = { showAllLogs = false }, onOpenDecision = { selectedDecisionId = it })
    if (selectedDecisionId != null) PaperDecisionAuditDialog(decisionReport, decisionContext, decisionLoading, decisionError, onDismiss = { selectedDecisionId = null })
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
        Spacer(Modifier.height(8.dp)); TradingRowDivider()
    }
}

@Composable private fun PaperLogHistoryDialog(logs: List<PaperTradingLogDto>, onDismiss: () -> Unit, onOpenDecision: (String?) -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("完整操作记录") },
    text = { LazyColumn { items(logs, key = { it.id }) { log -> PaperLogRow(log, onOpenDecision = { onOpenDecision(log.decision_id) }) } } },
    confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
)

@Composable fun PaperDecisionAuditDialog(report: DecisionReportDto?, context: Map<String, Any>, loading: Boolean, error: String?, onDismiss: () -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("操作分析记录") },
    text = {
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()); Text("正在加载完整决策留档…") }
            error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
            report?.let { item {
                Text("${it.symbol} · ${it.action} · ${paperBeijingTimestamp(it.generated_at)}", fontWeight = FontWeight.Bold)
                Text(it.summary, style = MaterialTheme.typography.bodySmall)
                it.sizing?.let { sizing -> DecisionAuditLine("仓位计算", "建议 ${sizing.suggested_quantity?.clean() ?: "--"} 股；目标 ${sizing.target_quantity?.clean() ?: "--"} 股；现金上限 ${sizing.quantity_by_cash?.clean() ?: "--"} 股") }
                if (it.action_candidates.isNotEmpty()) DecisionAuditLine("规则候选", it.action_candidates.joinToString { candidate -> "${candidate.action}（评分 ${"%.2f".format(candidate.policy_score)}）" })
                it.operation_items?.forEach { operation -> DecisionAuditLine(operation.title, operation.trigger) }
                Text("AI 推理依据", fontWeight = FontWeight.SemiBold)
                it.ai_assessment?.reasoning_steps?.forEach { step -> DecisionAuditLine(step.stage, step.summary + step.evidence_ids.takeIf { ids -> ids.isNotEmpty() }?.let { "\n引用证据：${it.joinToString()}" }.orEmpty()) }
                Text("证据数据点", fontWeight = FontWeight.SemiBold)
                it.evidence.forEach { evidence -> DecisionAuditLine(evidence.title, evidence.description) }
                if (it.ai_assessment?.missing_evidence?.isNotEmpty() == true) DecisionAuditLine("缺失数据", it.ai_assessment.missing_evidence.joinToString(), error = true)
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
    field("account", "available_cash")?.let { DecisionAuditLine("模拟可用资金", it) }
    field("position", "quantity")?.let { DecisionAuditLine("模拟持仓数量", "$it 股") }
    field("daily_bars", "count")?.let { DecisionAuditLine("日线数据范围", "$it 根") }
    field("data_quality", "status")?.let { DecisionAuditLine("数据质量", it) }
}

private fun Double.money() = "%.2f".format(Locale.US, this)
private fun Double.clean() = if (this % 1.0 == 0.0) toInt().toString() else "%.2f".format(Locale.US, this)
private fun Double.signed() = "%.2f".format(Locale.US, this)
private fun paperBeijingTimestamp(value: String): String = runCatching { OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8)).format(DateTimeFormatter.ofPattern("MM-dd HH:mm")) }.getOrElse { value.replace('T', ' ').substringBefore("+").substringBefore("Z") }
private fun paperSkipReason(reason: String): String = when {
    reason.contains("insufficient_paper_cash") -> "可用模拟资金不足，未买入"
    reason.contains("insufficient_paper_position") -> "模拟持仓不足，未卖出"
    reason.contains("paper_t1_unsellable_quantity") -> "A 股 T+1：今日买入的仓位下一交易日才能卖出"
    reason.contains("already_executed") -> "该份决策已执行，避免重复交易"
    reason.contains("100_share_lot") -> "数量不符合 A 股一手 100 股规则"
    reason.contains("no_executable") -> "当前没有满足条件的买卖信号"
    else -> "本轮暂不操作：$reason"
}
