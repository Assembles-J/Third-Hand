package com.thirdhand.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import java.time.Instant
import java.util.Locale

/** Immutable screen contract; independently loaded sections keep their last usable data. */
private data class StockDetailDecisionUiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val quote: MarketQuoteDto? = null,
    val holding: HoldingDto? = null,
    val availableCash: AvailableCashDto? = null,
    val decision: DecisionReportDto? = null,
    val latestReview: DailyReviewDto? = null,
    val errors: Map<String, String> = emptyMap(),
)

@Composable
fun StockDetailDecisionRoute(
    target: ResearchTargetDto,
    onBack: () -> Unit,
    onResearch: (ResearchTargetDto) -> Unit,
) {
    val context = LocalContext.current
    val api = remember { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var quote by remember(target.symbol) { mutableStateOf<MarketQuoteDto?>(null) }
    var holding by remember(target.symbol) { mutableStateOf<HoldingDto?>(null) }
    var paperPosition by remember(target.symbol) { mutableStateOf<PaperTradingPositionDto?>(null) }
    var report by remember(target.symbol) { mutableStateOf<DecisionReportDto?>(null) }
    var paperLogs by remember(target.symbol) { mutableStateOf<List<PaperTradingLogDto>>(emptyList()) }
    var selectedPaperDecisionId by remember(target.symbol) { mutableStateOf<String?>(null) }
    var paperDecision by remember(target.symbol) { mutableStateOf<DecisionReportDto?>(null) }
    var paperDecisionContext by remember(target.symbol) { mutableStateOf<Map<String, Any>>(emptyMap()) }
    var paperDecisionError by remember(target.symbol) { mutableStateOf<String?>(null) }
    var paperDecisionLoading by remember(target.symbol) { mutableStateOf(false) }
    var loading by remember(target.symbol) { mutableStateOf(true) }
    var error by remember(target.symbol) { mutableStateOf<String?>(null) }

    fun load() = scope.launch {
        loading = true
        error = null
        supervisorScope {
            val quoteResult = async { runCatching { ApiClient.marketQuotes(api, MarketQuoteBatchRequestDto(listOf(target.symbol), refresh = true)).firstOrNull() } }
            val holdingResult = async { runCatching { api.holdings().firstOrNull { it.symbol == target.symbol } } }
            val reportResult = async { runCatching { api.latestDecision(target.symbol) } }
            val paperLogsResult = async { runCatching { api.paperTradingLogs(target.symbol, 50) } }
            val paperAccountResult = async { runCatching { api.paperTradingAccount() } }
            quoteResult.await().onSuccess { quote = it }.onFailure { error = "行情读取失败：${it.message ?: "请稍后重试"}" }
            holdingResult.await().onSuccess { holding = it }
            reportResult.await().onSuccess { report = it }
            paperLogsResult.await().onSuccess { paperLogs = it }
            paperAccountResult.await().onSuccess { account -> paperPosition = account.positions.firstOrNull { it.symbol == target.symbol } }
        }
        loading = false
    }

    LaunchedEffect(target.symbol) { load() }
    LaunchedEffect(selectedPaperDecisionId) {
        val decisionId = selectedPaperDecisionId ?: return@LaunchedEffect
        paperDecisionLoading = true; paperDecisionError = null; paperDecision = null; paperDecisionContext = emptyMap()
        runCatching { api.paperTradingDecisionAudit(decisionId) }
            .onSuccess { paperDecision = it.report; paperDecisionContext = it.context }
            .onFailure { paperDecisionError = "无法读取这笔交易操作的分析记录：${it.message ?: "记录可能已过期"}" }
        paperDecisionLoading = false
    }
    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
    ) {
        item {
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回"); Text("返回") }
                Spacer(Modifier.weight(1f))
                TextButton(onClick = ::load, enabled = !loading) { Icon(Icons.Filled.Refresh, "刷新行情"); Text(if (loading) "刷新中" else "刷新") }
            }
        }
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                Text(target.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("${target.symbol} · 数据 ${quote?.as_of ?: quote?.retrieved_at ?: "暂不可用"}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(quote?.price?.money() ?: "—", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold)
                quote?.let {
                    val rise = (it.change_percent ?: 0.0) >= 0
                    Text("${if (rise) "↑" else "↓"} ${(it.change ?: 0.0).signedMoney()}  ${(it.change_percent ?: 0.0).signedPercent()}", color = if (rise) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall, fontWeight = FontWeight.SemiBold)
                }
                holding?.let { Text("持仓 ${it.quantity.formatQuantity()} · 成本 ${it.average_cost.money()}", style = MaterialTheme.typography.bodyMedium) }
                paperPosition?.let { Text("持仓 ${it.quantity.formatQuantity()} 股 · 成本 ${it.average_cost.money()} · 浮盈 ${it.unrealized_return_percent.signedPercent()}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary) }
                Text("行情来源 ${quote?.source ?: "—"} · ${quote?.freshness_note ?: "等待行情"}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        error?.let { message -> item { ErrorCard("行情不可用", message, ::load) } }
        if (loading && quote == null) item { LoadingCard("正在读取行情…") }
        item { DenseDivider() }
        item { TradingPeriodKLinePanel(symbol = target.symbol, quote = quote) }
        item { DenseDivider() }
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("交易操作记录", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Text("B / S 为交易账套成交；点击任一记录查看结构化操作分析。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (paperLogs.isEmpty()) Text("暂无该股票的交易操作记录。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        items(paperLogs.take(20), key = { it.id }) { log -> StockDetailPaperLogRow(log, onOpenAnalysis = { selectedPaperDecisionId = log.decision_id }) }
        item { DenseDivider() }
        item {
            Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("AI 分析工作台", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                if (report == null) {
                    Text("尚无已保存的统一分析。可在 AI 研究中提问，系统会先生成并保存一份分析报告。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    Text("${report!!.action.actionLabel()} · ${report!!.status}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(report!!.summary, style = MaterialTheme.typography.bodySmall)
                    Text("报告 ${report!!.decision_id.take(8)} · ${report!!.generated_at.take(16)} · 行情截至 ${report!!.market_as_of ?: "未知"}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                FilledTonalButton(onClick = { onResearch(target) }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Filled.AutoGraph, "打开 AI 研究")
                    Spacer(Modifier.width(8.dp))
                    Text(if (report == null) "开始 AI 分析" else "在 AI 研究中解释这份报告")
                }
            }
        }
        item { Text("交易操作请在“交易”页执行。", modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    }
    if (selectedPaperDecisionId != null) PaperDecisionAuditDialog(paperDecision, paperDecisionContext, paperDecisionLoading, paperDecisionError, onDismiss = { selectedPaperDecisionId = null })
}

@Composable
private fun StockDetailPaperLogRow(log: PaperTradingLogDto, onOpenAnalysis: () -> Unit) {
    val action = when (log.side) { "BUY" -> "B 买入"; "SELL" -> "S 卖出"; else -> "未执行" }
    Column(Modifier.fillMaxWidth().clickable(enabled = log.decision_id != null, onClick = onOpenAnalysis).padding(horizontal = 12.dp, vertical = 10.dp)) {
        Row(Modifier.fillMaxWidth()) {
            Column(Modifier.weight(1f)) {
                Text("$action · ${log.name.ifBlank { log.symbol }}", fontWeight = FontWeight.SemiBold)
                Text("${log.symbol} · ${log.executed_at.replace('T', ' ').substringBefore("+").takeLast(16)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(if (log.status == "executed") "¥${"%.2f".format(log.price)}" else "已拦截", color = if (log.status == "executed") MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelMedium)
        }
        Text(if (log.status == "executed") "${log.quantity.toInt()} 股 · 费用 ¥${"%.2f".format(log.fee)} · 点击查看操作分析" else stockDetailSkipReason(log.reason), Modifier.padding(top = 3.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        HorizontalDivider(Modifier.padding(top = 10.dp), color = MaterialTheme.colorScheme.outlineVariant)
    }
}

private fun stockDetailSkipReason(reason: String): String = when {
    reason.contains("paper_t1_unsellable") -> "A 股 T+1 限制：今日买入仓位不可卖出"
    reason.contains("no_position") -> "交易账套无持仓，卖出信号已拦截"
    reason.contains("insufficient_paper_cash") -> "可用资金不足"
    else -> "本轮未成交：$reason"
}

@Composable
private fun LegacyStockDetailDecisionRoute(
    target: ResearchTargetDto,
    onBack: () -> Unit,
    onResearch: (ResearchTargetDto) -> Unit,
) {
    val context = LocalContext.current
    val api = remember { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var state by remember(target.symbol) { mutableStateOf(StockDetailDecisionUiState()) }
    var decisionGenerating by remember(target.symbol) { mutableStateOf(false) }
    var executionDialogOpen by remember(target.symbol) { mutableStateOf(false) }
    var recordingExecution by remember(target.symbol) { mutableStateOf(false) }
    var editHoldingOpen by remember(target.symbol) { mutableStateOf(false) }
    var holdingEditError by remember(target.symbol) { mutableStateOf<String?>(null) }

    fun load(showSpinner: Boolean = false) = scope.launch {
        state = state.copy(loading = state.quote == null, refreshing = showSpinner, errors = emptyMap())
        val errors = mutableMapOf<String, String>()
        supervisorScope {
            val quote = async { runCatching { ApiClient.marketQuotes(api, MarketQuoteBatchRequestDto(listOf(target.symbol), refresh = true)).firstOrNull() } }
            val holdings = async { runCatching { api.holdings().firstOrNull { it.symbol == target.symbol } } }
            val cash = async { runCatching { api.availableCash() } }
            val decisionHistory = async { runCatching { api.decisionHistory(target.symbol, 1).firstOrNull() } }
            val reviews = async { runCatching { api.dailyReviews().firstOrNull { review -> review.items.any { it.symbol == target.symbol } } } }

            fun <T> value(section: String, result: Result<T>): T? = result.getOrElse {
                errors[section] = it.message ?: "读取失败"
                null
            }
            state = state.copy(
                loading = false,
                refreshing = false,
                quote = value("行情", quote.await()) ?: state.quote,
                holding = value("持仓", holdings.await()) ?: state.holding,
                availableCash = value("资金", cash.await()) ?: state.availableCash,
                decision = value("决策报告", decisionHistory.await()) ?: state.decision,
                latestReview = value("执行记录", reviews.await()) ?: state.latestReview,
                errors = errors.toMap(),
            )
        }
    }

    fun generateDecision() = scope.launch {
        decisionGenerating = true
        val result = runCatching {
            val job = api.generateDecision(DecisionGenerateRequestDto(listOf(target.symbol))).jobs.firstOrNull()
                ?: error("服务没有创建决策任务")
            repeat(24) {
                delay(500)
                val status = api.decisionJob(job.job_id)
                if (status.status == "completed") return@runCatching api.decisionHistory(target.symbol, 1).firstOrNull()
                if (status.status == "failed") error(status.error_message ?: "决策生成失败")
            }
            error("决策仍在生成，请稍后刷新")
        }
        decisionGenerating = false
        result.onSuccess { report -> state = state.copy(decision = report, errors = state.errors - "决策报告") }
            .onFailure { state = state.copy(errors = state.errors + ("决策报告" to (it.message ?: "生成失败"))) }
    }

    fun recordExecution(executed: Boolean) = scope.launch {
        recordingExecution = true
        val result = runCatching {
            val review = state.latestReview ?: api.generateDailyReview(DailyReviewGenerateRequestDto(listOf(target.symbol)))
            val suggestedQuantity = review.items.firstOrNull { it.symbol == target.symbol }?.suggested_quantity
                ?: state.decision?.sizing?.suggested_quantity
            if (executed && (suggestedQuantity == null || suggestedQuantity <= 0 || state.quote?.price == null)) {
                error("缺少建议数量或行情，不能把查看建议当作已执行")
            }
            api.recordDailyReviewExecution(
                review.id,
                target.symbol,
                DailyReviewExecutionInputDto(
                    execution_status = if (executed) "executed" else "skipped",
                    executed_quantity = if (executed) suggestedQuantity!! else 0.0,
                    executed_price = if (executed) state.quote!!.price else null,
                    note = if (executed) "由股票详情页记录" else "用户选择未执行建议",
                ),
            )
        }
        recordingExecution = false
        executionDialogOpen = false
        result.onSuccess { review -> state = state.copy(latestReview = review, errors = state.errors - "执行记录") }
            .onFailure { state = state.copy(errors = state.errors + ("执行记录" to (it.message ?: "记录失败"))) }
    }

    fun evaluatePerformance() = scope.launch {
        val review = state.latestReview ?: return@launch
        runCatching { api.evaluateDailyReview(review.id) }
            .onSuccess { updated -> state = state.copy(latestReview = updated, errors = state.errors - "收益复盘") }
            .onFailure { state = state.copy(errors = state.errors + ("收益复盘" to (it.message ?: "评估失败"))) }
    }

    LaunchedEffect(target.symbol) { load() }
    StockDetailDecisionScreen(
        target = target,
        state = state,
        decisionGenerating = decisionGenerating,
        recordingExecution = recordingExecution,
        onBack = onBack,
        onResearch = { onResearch(target) },
        onRefresh = { load(showSpinner = true) },
        onEditHolding = { editHoldingOpen = true },
        onGenerateDecision = ::generateDecision,
        onRecordExecution = { executionDialogOpen = true },
        onEvaluatePerformance = ::evaluatePerformance,
    )
    if (editHoldingOpen) {
        state.holding?.let { holding ->
            AddHoldingDialog(
                title = "编辑持仓",
                initial = HoldingInputDto(holding.symbol, holding.name, holding.quantity, holding.average_cost),
                onDismiss = { editHoldingOpen = false },
                onSave = { input -> scope.launch {
                    runCatching { api.updateHolding(holding.id, input) }
                        .onSuccess { updated ->
                            state = state.copy(holding = updated)
                            editHoldingOpen = false
                            load(showSpinner = false)
                        }
                        .onFailure { holdingEditError = it.message ?: "请稍后重试。" }
                } },
            )
        } ?: run { editHoldingOpen = false }
    }
    holdingEditError?.let { message ->
        AlertDialog(
            onDismissRequest = { holdingEditError = null },
            title = { Text("更新持仓失败") },
            text = { Text(message) },
            confirmButton = { TextButton(onClick = { holdingEditError = null }) { Text("知道了") } },
        )
    }
    if (executionDialogOpen) {
        val suggestedQuantity = state.latestReview?.items?.firstOrNull { it.symbol == target.symbol }?.suggested_quantity
            ?: state.decision?.sizing?.suggested_quantity
        AlertDialog(
            onDismissRequest = { if (!recordingExecution) executionDialogOpen = false },
            title = { Text("记录建议是否执行") },
            text = { Text("“已执行”会记录建议数量 ${suggestedQuantity?.formatQuantity() ?: "—"} 与当前行情；“未执行”只用于后续交易收益，不会被视为真实盈亏。") },
            confirmButton = { Button(onClick = { recordExecution(true) }, enabled = !recordingExecution && suggestedQuantity != null && state.quote?.price != null) { Text(if (recordingExecution) "保存中…" else "已执行") } },
            dismissButton = { TextButton(onClick = { recordExecution(false) }, enabled = !recordingExecution) { Text("未执行（对照）") } },
        )
    }
}

@Composable
private fun StockDetailDecisionScreen(
    target: ResearchTargetDto,
    state: StockDetailDecisionUiState,
    decisionGenerating: Boolean,
    recordingExecution: Boolean,
    onBack: () -> Unit,
    onResearch: () -> Unit,
    onRefresh: () -> Unit,
    onEditHolding: () -> Unit,
    onGenerateDecision: () -> Unit,
    onRecordExecution: () -> Unit,
    onEvaluatePerformance: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(0.dp),
    ) {
        item {
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp), horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TextButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回"); Text("返回") }
                Spacer(Modifier.weight(1f))
                TextButton(onClick = onEditHolding, enabled = state.holding != null) { Text("编辑持仓") }
                TextButton(onClick = onRefresh, enabled = !state.refreshing) { Icon(Icons.Filled.Refresh, "刷新数据"); Text(if (state.refreshing) "刷新中" else "刷新") }
            }
        }
        item { QuoteHeader(target, state.quote, state.holding, state.availableCash) }
        item { DenseDivider() }
        state.errors["行情"]?.let { item { ErrorCard("行情不可用", it, onRefresh) } }
        if (state.loading) item { LoadingCard("正在读取行情、仓位和决策数据…") }
        item {
            RiskAndFreshnessBanner(state.quote, state.decision)
        }
        item { DenseDivider() }
        item { TradingPeriodKLinePanel(symbol = target.symbol, quote = state.quote) }
        item { DenseDivider() }
        item {
            ActionPlanCard(
                report = state.decision,
                reviewItem = state.latestReview?.items?.firstOrNull { it.symbol == target.symbol },
                generating = decisionGenerating,
                onGenerate = onGenerateDecision,
                onRecordExecution = onRecordExecution,
            )
        }
        item { DenseDivider() }
        state.errors["决策报告"]?.let { item { ErrorCard("决策报告不可用", it, onGenerateDecision) } }
        item { PositionSizingCard(state.decision?.sizing, state.availableCash, state.holding) }
        item { DenseDivider() }
        item { EvidenceStack(state.decision) }
        item { DenseDivider() }
        item { AdvicePerformanceCard(state.latestReview, target.symbol, recordingExecution, onEvaluatePerformance) }
        state.errors["收益复盘"]?.let { item { ErrorCard("收益复盘不可用", it, onEvaluatePerformance) } }
        item {
            FilledTonalButton(onClick = onResearch, modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp)) {
                Icon(Icons.Filled.AutoGraph, "打开 AI 研究会话")
                Spacer(Modifier.width(8.dp))
                Text("打开 AI 研究会话，补充问题")
            }
        }
    }
}

@Composable private fun QuoteHeader(target: ResearchTargetDto, quote: MarketQuoteDto?, holding: HoldingDto?, cash: AvailableCashDto?) = Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Column {
            Text(target.name, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("${target.symbol} · ${target.status}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Text("数据 ${quote?.as_of ?: quote?.retrieved_at ?: "不可用"}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(18.dp)) {
        Column(Modifier.weight(0.9f)) {
            Text(quote?.price?.money() ?: "—", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold)
            quote?.let {
                val rise = (it.change_percent ?: 0.0) >= 0
                Text("${if (rise) "↑" else "↓"} ${(it.change ?: 0.0).signedMoney()}  ${(it.change_percent ?: 0.0).signedPercent()}", color = if (rise) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall, fontWeight = FontWeight.SemiBold)
            }
        }
        Column(Modifier.weight(1.1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
            QuoteMetricRow("高", quote?.high?.money(), "低", quote?.low?.money())
            QuoteMetricRow("开", quote?.open?.money(), "昨收", quote?.previous_close?.money())
            QuoteMetricRow("持仓", holding?.quantity?.formatQuantity(), "可用", cash?.available_cash?.money())
        }
    }
    Text("行情来源 ${quote?.source ?: "—"} · ${quote?.freshness_note ?: "等待行情"}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f))
    QuoteMarketStrip(quote)
}

/** Compact spot strip inspired by terminal layouts; it never labels aggregate flow as a large order. */
@Composable private fun QuoteMarketStrip(quote: MarketQuoteDto?) = Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
    Row(Modifier.fillMaxWidth()) {
        MarketMicroMetric("买一价", quote?.bid_price?.money() ?: "—", Modifier.weight(1f), MaterialTheme.marketColors.rise)
        MarketMicroMetric("卖一价", quote?.ask_price?.money() ?: "—", Modifier.weight(1f), MaterialTheme.marketColors.fall)
        MarketMicroMetric("量比", quote?.volume_ratio?.let { "%.2f".format(Locale.US, it) } ?: "—", Modifier.weight(0.75f), MaterialTheme.colorScheme.onSurface)
        MarketMicroMetric("换手", quote?.turnover_rate?.let { "%.2f%%".format(Locale.US, it) } ?: "—", Modifier.weight(0.85f), MaterialTheme.colorScheme.onSurface)
    }
    Row(Modifier.fillMaxWidth()) {
        Text("成交量 ${quote?.volume?.compactVolume() ?: "—"}", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium)
        Text("成交额 ${quote?.amount?.compactAmount() ?: "—"}", Modifier.weight(1f), style = MaterialTheme.typography.labelMedium)
        Text("盘口：价格 / 数量", Modifier.weight(1.3f), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    OrderBookDepth(quote?.ask_levels.orEmpty(), quote?.bid_levels.orEmpty())
}

@Composable private fun OrderBookDepth(asks: List<OrderBookLevelDto>, bids: List<OrderBookLevelDto>) {
    if (asks.isEmpty() && bids.isEmpty()) {
        Text("五档盘口暂未返回；刷新后重试。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        return
    }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("卖盘", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.marketColors.fall)
            asks.asReversed().forEachIndexed { index, level ->
                Text("卖${asks.size - index}  ${level.price?.money() ?: "—"} / ${level.volume?.compactVolume() ?: "—"}", style = MaterialTheme.typography.labelSmall)
            }
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text("买盘", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.marketColors.rise)
            bids.forEachIndexed { index, level ->
                Text("买${index + 1}  ${level.price?.money() ?: "—"} / ${level.volume?.compactVolume() ?: "—"}", style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable private fun MarketMicroMetric(label: String, value: String, modifier: Modifier, color: androidx.compose.ui.graphics.Color) = Column(modifier) {
    Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(value, style = MaterialTheme.typography.bodySmall, color = color, fontWeight = FontWeight.SemiBold)
}

@Composable private fun QuoteMetricRow(firstLabel: String, firstValue: String?, secondLabel: String, secondValue: String?) = Row(Modifier.fillMaxWidth()) {
    Text(firstLabel, Modifier.width(30.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(firstValue ?: "—", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    Text(secondLabel, Modifier.width(34.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    Text(secondValue ?: "—", Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
}

@Composable private fun RiskAndFreshnessBanner(quote: MarketQuoteDto?, report: DecisionReportDto?) = Column(Modifier.fillMaxWidth().background(if (quote?.isStale() == true) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceContainerLow).padding(horizontal = 12.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(3.dp)) {
    val invalidation = report?.operation_items?.firstOrNull { it.invalidation_price != null }?.invalidation_price ?: report?.sizing?.invalidation_price
    val title = when {
        quote == null -> "行情不可用"
        quote.isStale() -> "报价已过期：先刷新再决定"
        quote.refresh_status == "stored" -> "缓存行情快照"
        !quote.is_realtime -> "公开行情快照（可能延迟）"
        else -> "行情状态正常"
    }
    Text(title, fontWeight = FontWeight.Bold)
    Text(
        if (quote == null) "没有可核验的行情，不能把建议当作可执行订单。"
        else "状态：${quote.refresh_status} · ${quote.freshness_note} · 获取时间 ${quote.retrieved_at}",
        style = MaterialTheme.typography.bodySmall,
    )
    if (invalidation != null) Text("失效价位：${invalidation.money()}；触及后停止沿用本建议并复查。", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    report?.status?.let { Text("建议状态：$it · ${report.generated_at}", style = MaterialTheme.typography.labelSmall) }
}

@Composable private fun ActionPlanCard(report: DecisionReportDto?, reviewItem: DailyReviewItemDto?, generating: Boolean, onGenerate: () -> Unit, onRecordExecution: () -> Unit) = Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
        Text("最终建议（结构化）", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if (report == null) {
            Text("暂无已保存的决策报告。生成前会使用当前行情、持仓、指标、规则与学习资料；不会自动下单。")
            Button(onClick = onGenerate, enabled = !generating, modifier = Modifier.fillMaxWidth()) { Text(if (generating) "正在生成决策…" else "生成结构化建议") }
        } else {
            Text("建议动作：${report.action.actionLabel()}", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text(report.summary, style = MaterialTheme.typography.bodyMedium)
            val zone = reviewItem?.price_zone
            Text("价格区间：${zone?.get("low")?.money() ?: "未提供下限"} ～ ${zone?.get("high")?.money() ?: "未提供上限"}；缺少区间时只显示参考价，不虚构范围。", style = MaterialTheme.typography.bodySmall)
            report.operation_items.orEmpty().forEach { item ->
                Text("${item.title} · 复查/触发条件：${item.trigger} · 参考价：${item.reference_price?.money() ?: "—"} · 数量：${item.suggested_quantity?.formatQuantity() ?: "待计算"} · 状态：${item.status}", style = MaterialTheme.typography.bodySmall)
                item.invalidation_price?.let { Text("失效/止损：${it.money()}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold) }
            }
            Text("模型置信度表示证据强度，不表示盈利概率。", style = MaterialTheme.typography.labelSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onGenerate, enabled = !generating, modifier = Modifier.weight(1f)) { Text(if (generating) "更新中…" else "更新建议") }
                Button(onClick = onRecordExecution, modifier = Modifier.weight(1f)) { Text("记录是否执行") }
            }
        }
}

@Composable private fun PositionSizingCard(sizing: PositionSizingResultDto?, cash: AvailableCashDto?, holding: HoldingDto?) = Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("建议数量与资金占用", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if (sizing == null) Text("尚无仓位测算。必须有行情、失效条件、资金和市场手数等假设才会给出数量。", style = MaterialTheme.typography.bodySmall)
        else {
            Text("建议数量：${sizing.suggested_quantity?.formatQuantity() ?: "计算不完整"} · 目标总持仓：${sizing.target_quantity?.formatQuantity() ?: "—"}")
            Text("预计资金占用：${sizing.suggested_quantity?.let { quantity -> sizing.entry_price?.times(quantity)?.money() } ?: "—"} · 可用资金：${cash?.available_cash?.money() ?: "—"}", style = MaterialTheme.typography.bodySmall)
            Text("风险预算：${sizing.risk_capital?.money() ?: "—"} · 每股到失效价风险：${sizing.risk_per_share?.money() ?: "—"} · 手数：${sizing.lot_size ?: "未提供"}", style = MaterialTheme.typography.bodySmall)
            if (sizing.blocked_reasons.isNotEmpty()) Text("不能精确执行：${sizing.blocked_reasons.joinToString("；")}", color = MaterialTheme.marketColors.warning, style = MaterialTheme.typography.bodySmall)
        }
        holding?.let { Text("事实：当前持有 ${it.quantity.formatQuantity()}，成本 ${it.average_cost.money()}。", style = MaterialTheme.typography.labelSmall) }
}

@Composable private fun EvidenceStack(report: DecisionReportDto?) = Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
    val evidence = report?.evidence.orEmpty()
        Text("依据分层：事实、指标、AI 判断", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        EvidenceGroup("客观事实 / 市场与事件", evidence.filter { it.category.contains("market", true) || it.category.contains("event", true) || it.category.contains("quote", true) })
        EvidenceGroup("指标结果", evidence.filter { it.category.contains("technical", true) || it.category.contains("trend", true) || it.category.contains("relative", true) })
        EvidenceGroup("个人规则与风险约束", evidence.filter { it.category.contains("rule", true) || it.category.contains("risk", true) })
        report?.ai_assessment?.let { ai ->
            HorizontalDivider()
            Text("AI 判断（不是客观事实）", fontWeight = FontWeight.Bold)
            Text(ai.summary, style = MaterialTheme.typography.bodySmall)
            Text("不确定性：${ai.uncertainty}", style = MaterialTheme.typography.bodySmall)
            ai.reasoning_steps.forEach { Text("${it.stage}：${it.summary}", style = MaterialTheme.typography.labelSmall) }
        }
        if (evidence.isEmpty() && report?.ai_assessment == null) Text("尚无决策证据；请生成结构化建议后查看。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable private fun EvidenceGroup(title: String, items: List<DecisionEvidenceDto>) {
    Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
    if (items.isEmpty()) Text("暂无", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    else {
        items.take(5).forEach { item -> Text("${item.title}：${item.description}（${item.source}）", style = MaterialTheme.typography.bodySmall) }
        if (items.size > 5) Text("当前仅展示 5 / ${items.size} 条；完整证据请在交易操作分析记录中查看。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable private fun RulesCard(rules: List<PersonalRuleDto>, error: String?) = Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("个人规则", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        error?.let { Text("加载失败：$it", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        if (rules.isEmpty()) Text("没有适用于该标的的启用规则。", style = MaterialTheme.typography.bodySmall) else rules.forEach { rule -> Text("${rule.scope}：单标的上限 ${rule.max_position_percent}% · 亏损复查 ${rule.loss_review_percent}% · 波动复查 ${rule.volatility_review_percent}%", style = MaterialTheme.typography.bodySmall) }
}

@Composable private fun LearningCasesCard(cases: List<LearningCaseDto>, error: String?) = Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("学习案例", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        error?.let { Text("加载失败：$it", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        if (cases.isEmpty()) Text("暂无该标的的复盘案例。", style = MaterialTheme.typography.bodySmall) else cases.take(3).forEach { item -> Text("${item.title}：${item.lesson} · 结果：${item.outcome}", style = MaterialTheme.typography.bodySmall, maxLines = 3, overflow = TextOverflow.Ellipsis) }
}

@Composable private fun AdvicePerformanceCard(review: DailyReviewDto?, symbol: String, recording: Boolean, onEvaluate: () -> Unit) = Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
    val item = review?.items?.firstOrNull { it.symbol == symbol }
        Text("执行与收益复盘", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if (item == null) Text("尚未记录此建议是否执行。记录后会区分真实成交收益和未执行建议的对照收益。", style = MaterialTheme.typography.bodySmall)
        else {
            Text("执行状态：${item.execution_status.executionLabel()} · 建议数量 ${item.suggested_quantity?.formatQuantity() ?: "—"}")
            Text("实际收益：${item.actual_pnl?.signedMoney() ?: "待后续行情评估"}（仅有真实成交时计算）", style = MaterialTheme.typography.bodySmall)
            Text("对照收益：${item.theoretical_pnl?.signedMoney() ?: "待后续行情评估"}（未执行/对照，不是已实现收益）", style = MaterialTheme.typography.bodySmall)
            if (review.status == "evaluated") Text("评估时间：${review.evaluated_at ?: "—"}", style = MaterialTheme.typography.labelSmall)
            OutlinedButton(onClick = onEvaluate, enabled = !recording, modifier = Modifier.fillMaxWidth()) { Text("用后续行情计算实际 / 对照收益") }
        }
        if (recording) CircularProgressIndicator(modifier = Modifier.width(18.dp))
}

@Composable private fun LoadingCard(message: String) = Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) { CircularProgressIndicator(modifier = Modifier.width(18.dp)); Text(message, style = MaterialTheme.typography.bodySmall) }
@Composable private fun ErrorCard(title: String, message: String, retry: () -> Unit) = Column(Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.errorContainer).padding(horizontal = 12.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { Text(title, fontWeight = FontWeight.Bold); Text(message, style = MaterialTheme.typography.bodySmall); TextButton(onClick = retry) { Text("重试") } }
@Composable private fun DenseDivider() = HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.55f))

/** A cached or delayed public quote is not expired while its server retrieval time is recent. */
private fun MarketQuoteDto.isStale(): Boolean {
    if (price == null || !error_code.isNullOrBlank() || refresh_status == "stale_fallback") return true
    val retrieved = runCatching { Instant.parse(retrieved_at).toEpochMilli() }.getOrNull() ?: return false
    return retrieved < Instant.now().minusSeconds(20 * 60).toEpochMilli()
}
private fun String.actionLabel(): String = mapOf("OPEN" to "买入", "BUY" to "买入", "ADD" to "加仓", "HOLD" to "持有", "REDUCE" to "减仓", "SELL" to "卖出", "EXIT" to "卖出", "STOP" to "止损", "REVIEW" to "复查", "OBSERVE" to "观察")[uppercase(Locale.ROOT)] ?: "需复查（$this）"
private fun String.executionLabel(): String = mapOf("pending" to "待记录", "executed" to "已执行", "partial" to "部分执行", "skipped" to "未执行")[lowercase(Locale.ROOT)] ?: this
private fun Double.money(): String = "%.2f".format(Locale.US, this)
private fun Double.signedMoney(): String = "${if (this >= 0) "+" else ""}${money()}"
private fun Double.signedPercent(): String = "${if (this >= 0) "+" else ""}${"%.2f".format(Locale.US, this)}%"
private fun Double.formatQuantity(): String = if (this % 1.0 == 0.0) "${toLong()} 股" else "${"%.2f".format(Locale.US, this)} 股"
private fun Double.compactVolume(): String = when {
    kotlin.math.abs(this) >= 100_000_000 -> "%.2f亿股".format(Locale.US, this / 100_000_000)
    kotlin.math.abs(this) >= 10_000 -> "%.2f万股".format(Locale.US, this / 10_000)
    else -> "%.0f股".format(Locale.US, this)
}
private fun Double.compactAmount(): String = when {
    kotlin.math.abs(this) >= 100_000_000 -> "%.2f亿".format(Locale.US, this / 100_000_000)
    kotlin.math.abs(this) >= 10_000 -> "%.2f万".format(Locale.US, this / 10_000)
    else -> money()
}
