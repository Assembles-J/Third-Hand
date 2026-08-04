package com.thirdhand.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import retrofit2.HttpException
import java.util.Locale

/** Immutable screen contract; independently loaded sections keep their last usable data. */
private data class StockDetailDecisionUiState(
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val quote: MarketQuoteDto? = null,
    val holding: HoldingDto? = null,
    val availableCash: AvailableCashDto? = null,
    val decision: DecisionReportDto? = null,
    val personalRules: List<PersonalRuleDto> = emptyList(),
    val learningCases: List<LearningCaseDto> = emptyList(),
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
    var state by remember(target.symbol) { mutableStateOf(StockDetailDecisionUiState()) }
    var decisionGenerating by remember(target.symbol) { mutableStateOf(false) }
    var executionDialogOpen by remember(target.symbol) { mutableStateOf(false) }
    var recordingExecution by remember(target.symbol) { mutableStateOf(false) }

    fun load(showSpinner: Boolean = false) = scope.launch {
        state = state.copy(loading = state.quote == null, refreshing = showSpinner, errors = emptyMap())
        val errors = mutableMapOf<String, String>()
        supervisorScope {
            val quote = async { runCatching { ApiClient.marketQuotes(api, MarketQuoteBatchRequestDto(listOf(target.symbol), refresh = true)).firstOrNull() } }
            val holdings = async { runCatching { api.holdings().firstOrNull { it.symbol == target.symbol } } }
            val cash = async { runCatching { api.availableCash() } }
            val decisionHistory = async { runCatching { api.decisionHistory(target.symbol, 1).firstOrNull() } }
            val rules = async { runCatching { api.personalRules().filter { it.enabled && (it.symbol == null || it.symbol == target.symbol) } } }
            val cases = async { runCatching { api.learningCases(target.symbol) } }
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
                personalRules = value("个人规则", rules.await()) ?: state.personalRules,
                learningCases = value("学习案例", cases.await()) ?: state.learningCases,
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
        onGenerateDecision = ::generateDecision,
        onRecordExecution = { executionDialogOpen = true },
        onEvaluatePerformance = ::evaluatePerformance,
    )
    if (executionDialogOpen) {
        val suggestedQuantity = state.latestReview?.items?.firstOrNull { it.symbol == target.symbol }?.suggested_quantity
            ?: state.decision?.sizing?.suggested_quantity
        AlertDialog(
            onDismissRequest = { if (!recordingExecution) executionDialogOpen = false },
            title = { Text("记录建议是否执行") },
            text = { Text("“已执行”会记录建议数量 ${suggestedQuantity?.formatQuantity() ?: "—"} 与当前行情；“未执行”只用于后续模拟收益，不会被视为真实盈亏。") },
            confirmButton = { Button(onClick = { recordExecution(true) }, enabled = !recordingExecution && suggestedQuantity != null && state.quote?.price != null) { Text(if (recordingExecution) "保存中…" else "已执行") } },
            dismissButton = { TextButton(onClick = { recordExecution(false) }, enabled = !recordingExecution) { Text("未执行（模拟）") } },
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
    onGenerateDecision: () -> Unit,
    onRecordExecution: () -> Unit,
    onEvaluatePerformance: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxWidth(),
        contentPadding = androidx.compose.foundation.layout.PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TextButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回"); Text("返回") }
                Spacer(Modifier.weight(1f))
                TextButton(onClick = onRefresh, enabled = !state.refreshing) { Icon(Icons.Filled.Refresh, "刷新数据"); Text(if (state.refreshing) "刷新中" else "刷新") }
            }
        }
        item { QuoteHeader(target, state.quote, state.holding, state.availableCash) }
        state.errors["行情"]?.let { item { ErrorCard("行情不可用", it, onRefresh) } }
        if (state.loading) item { LoadingCard("正在分别读取行情、仓位、规则和决策数据…") }
        item {
            RiskAndFreshnessBanner(state.quote, state.decision)
        }
        item {
            ActionPlanCard(
                report = state.decision,
                reviewItem = state.latestReview?.items?.firstOrNull { it.symbol == target.symbol },
                generating = decisionGenerating,
                onGenerate = onGenerateDecision,
                onRecordExecution = onRecordExecution,
            )
        }
        state.errors["决策报告"]?.let { item { ErrorCard("决策报告不可用", it, onGenerateDecision) } }
        item { TradingPeriodKLinePanel(symbol = target.symbol, quote = state.quote) }
        item { PositionSizingCard(state.decision?.sizing, state.availableCash, state.holding) }
        item { EvidenceStack(state.decision) }
        item { RulesCard(state.personalRules, state.errors["个人规则"]) }
        item { LearningCasesCard(state.learningCases, state.errors["学习案例"]) }
        item { AdvicePerformanceCard(state.latestReview, target.symbol, recordingExecution, onEvaluatePerformance) }
        state.errors["收益复盘"]?.let { item { ErrorCard("收益复盘不可用", it, onEvaluatePerformance) } }
        item {
            FilledTonalButton(onClick = onResearch, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Filled.AutoGraph, "打开 AI 研究会话")
                Spacer(Modifier.width(8.dp))
                Text("打开 AI 研究会话，补充问题")
            }
        }
    }
}

@Composable private fun QuoteHeader(target: ResearchTargetDto, quote: MarketQuoteDto?, holding: HoldingDto?, cash: AvailableCashDto?) = Card {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(target.name, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("${target.symbol} · ${target.status}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(quote?.price?.money() ?: "行情暂不可用", style = MaterialTheme.typography.displaySmall, fontWeight = FontWeight.Bold)
        quote?.let {
            val rise = (it.change_percent ?: 0.0) >= 0
            Text("${if (rise) "↑" else "↓"} ${(it.change ?: 0.0).signedMoney()}  (${(it.change_percent ?: 0.0).signedPercent()})", color = if (rise) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall, fontWeight = FontWeight.SemiBold)
            Text("客观行情 · ${it.source} · 数据时间 ${it.as_of ?: it.retrieved_at}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        HorizontalDivider()
        Text("持仓 ${holding?.quantity?.formatQuantity() ?: "未持有"} · 成本 ${holding?.average_cost?.money() ?: "—"} · 可用资金 ${cash?.available_cash?.money() ?: "—"}", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable private fun RiskAndFreshnessBanner(quote: MarketQuoteDto?, report: DecisionReportDto?) = Card(colors = CardDefaults.cardColors(containerColor = if (quote?.isStale() == true) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceVariant)) {
    val invalidation = report?.operation_items?.firstOrNull { it.invalidation_price != null }?.invalidation_price ?: report?.sizing?.invalidation_price
    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(if (quote?.isStale() == true) "数据已过期：先刷新再决定" else "风险与有效性", fontWeight = FontWeight.Bold)
        Text(if (quote == null) "没有可核验的实时行情，不能把建议当作可执行订单。" else "数据新鲜度：${quote.freshness_note} · ${quote.refresh_status}", style = MaterialTheme.typography.bodySmall)
        if (invalidation != null) Text("失效价位：${invalidation.money()}；触及后应停止沿用本建议并复查。", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
        report?.status?.let { Text("建议状态：$it · 生成于 ${report.generated_at} · 底层行情 ${report.market_as_of ?: "未提供"}", style = MaterialTheme.typography.labelSmall) }
    }
}

@Composable private fun ActionPlanCard(report: DecisionReportDto?, reviewItem: DailyReviewItemDto?, generating: Boolean, onGenerate: () -> Unit, onRecordExecution: () -> Unit) = Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
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
}

@Composable private fun PositionSizingCard(sizing: PositionSizingResultDto?, cash: AvailableCashDto?, holding: HoldingDto?) = Card {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
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
}

@Composable private fun EvidenceStack(report: DecisionReportDto?) = Card {
    val evidence = report?.evidence.orEmpty()
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
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
}

@Composable private fun EvidenceGroup(title: String, items: List<DecisionEvidenceDto>) {
    Text(title, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
    if (items.isEmpty()) Text("暂无", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    else items.take(5).forEach { item -> Text("${item.title}：${item.description}（${item.source}）", style = MaterialTheme.typography.bodySmall) }
}

@Composable private fun RulesCard(rules: List<PersonalRuleDto>, error: String?) = Card {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("个人规则", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        error?.let { Text("加载失败：$it", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        if (rules.isEmpty()) Text("没有适用于该标的的启用规则。", style = MaterialTheme.typography.bodySmall) else rules.forEach { rule -> Text("${rule.scope}：单标的上限 ${rule.max_position_percent}% · 亏损复查 ${rule.loss_review_percent}% · 波动复查 ${rule.volatility_review_percent}%", style = MaterialTheme.typography.bodySmall) }
    }
}

@Composable private fun LearningCasesCard(cases: List<LearningCaseDto>, error: String?) = Card {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
        Text("学习案例", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        error?.let { Text("加载失败：$it", color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        if (cases.isEmpty()) Text("暂无该标的的复盘案例。", style = MaterialTheme.typography.bodySmall) else cases.take(3).forEach { item -> Text("${item.title}：${item.lesson} · 结果：${item.outcome}", style = MaterialTheme.typography.bodySmall, maxLines = 3, overflow = TextOverflow.Ellipsis) }
    }
}

@Composable private fun AdvicePerformanceCard(review: DailyReviewDto?, symbol: String, recording: Boolean, onEvaluate: () -> Unit) = Card {
    val item = review?.items?.firstOrNull { it.symbol == symbol }
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("执行与收益复盘", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        if (item == null) Text("尚未记录此建议是否执行。记录后会区分真实成交收益和未执行建议的模拟收益。", style = MaterialTheme.typography.bodySmall)
        else {
            Text("执行状态：${item.execution_status.executionLabel()} · 建议数量 ${item.suggested_quantity?.formatQuantity() ?: "—"}")
            Text("实际收益：${item.actual_pnl?.signedMoney() ?: "待后续行情评估"}（仅有真实成交时计算）", style = MaterialTheme.typography.bodySmall)
            Text("模拟收益：${item.theoretical_pnl?.signedMoney() ?: "待后续行情评估"}（未执行/对照，不是已实现收益）", style = MaterialTheme.typography.bodySmall)
            if (review.status == "evaluated") Text("评估时间：${review.evaluated_at ?: "—"}", style = MaterialTheme.typography.labelSmall)
            OutlinedButton(onClick = onEvaluate, enabled = !recording, modifier = Modifier.fillMaxWidth()) { Text("用后续行情计算实际 / 模拟收益") }
        }
        if (recording) CircularProgressIndicator(modifier = Modifier.width(18.dp))
    }
}

@Composable private fun LoadingCard(message: String) = Card { Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) { CircularProgressIndicator(modifier = Modifier.width(20.dp)); Text(message, style = MaterialTheme.typography.bodySmall) } }
@Composable private fun ErrorCard(title: String, message: String, retry: () -> Unit) = Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) { Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { Text(title, fontWeight = FontWeight.Bold); Text(message, style = MaterialTheme.typography.bodySmall); TextButton(onClick = retry) { Text("重试") } } }

private fun MarketQuoteDto.isStale(): Boolean = refresh_status != "fresh" || !is_realtime || freshness_note.contains("过期") || freshness_note.contains("延迟")
private fun String.actionLabel(): String = mapOf("OPEN" to "买入", "BUY" to "买入", "ADD" to "加仓", "HOLD" to "持有", "REDUCE" to "减仓", "SELL" to "卖出", "EXIT" to "卖出", "STOP" to "止损", "REVIEW" to "复查", "OBSERVE" to "观察")[uppercase(Locale.ROOT)] ?: "需复查（$this）"
private fun String.executionLabel(): String = mapOf("pending" to "待记录", "executed" to "已执行", "partial" to "部分执行", "skipped" to "未执行")[lowercase(Locale.ROOT)] ?: this
private fun Double.money(): String = "%.2f".format(Locale.US, this)
private fun Double.signedMoney(): String = "${if (this >= 0) "+" else ""}${money()}"
private fun Double.signedPercent(): String = "${if (this >= 0) "+" else ""}${"%.2f".format(Locale.US, this)}%"
private fun Double.formatQuantity(): String = if (this % 1.0 == 0.0) "${toLong()} 股" else "${"%.2f".format(Locale.US, this)} 股"
