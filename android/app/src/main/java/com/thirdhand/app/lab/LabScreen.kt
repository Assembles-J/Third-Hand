package com.thirdhand.app.lab

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingSection
import kotlinx.coroutines.launch
import java.util.Locale

@Composable
fun LabScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val controller = remember(context) {
        LabController(NetworkLabRepository(context.applicationContext))
    }
    val state by controller.state.collectAsState()
    val scope = rememberCoroutineScope()

    BackHandler(onBack = onBack)
    LaunchedEffect(Unit) { controller.load() }

    LabScreenContent(
        state = state,
        onBack = onBack,
        onRefresh = { scope.launch { controller.refresh() } },
    )
}

@Composable
internal fun LabScreenContent(
    state: LabUiState,
    onBack: () -> Unit,
    onRefresh: () -> Unit,
) {
    val refreshing = state is LabUiState.Ready && state.refreshing
    val busy = state is LabUiState.Loading || refreshing
    val refreshEnabled = !busy && (state !is LabUiState.Error || state.recoverable)

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 28.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        item {
            TradingPageHeader(
                title = "策略实验室",
                subtitle = "只读 Evaluation · SWING_V1 与冻结基准",
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "返回管理")
                    }
                    IconButton(onClick = onRefresh, enabled = refreshEnabled) {
                        if (busy) {
                            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Filled.Refresh, contentDescription = "刷新策略实验室")
                        }
                    }
                }
            }
        }

        when (state) {
            LabUiState.Loading -> item { LabMessageCard("正在读取冻结实验、策略评估与基准结果…") }
            is LabUiState.Empty -> item { LabMessageCard(state.message) }
            is LabUiState.Error -> item {
                LabMessageCard(
                    text = "策略实验室暂不可用：${state.message}",
                    isError = true,
                    actionLabel = if (state.recoverable) "重试" else null,
                    onAction = onRefresh,
                )
            }
            is LabUiState.Ready -> {
                val data = state.dashboard
                item { ExperimentIdentityCard(data) }
                item { TradingSection("样本质量", "样本充分性不等于策略好坏；不足时只展示事实，不下结论") }
                item { SampleQualityCard(data) }
                item { TradingSection("策略表现", "来自 StrategyEvaluation；手机端不重算") }
                item { StrategyPerformanceCard(data.performance.strategy) }
                item { TradingSection("相对基准", "同一冻结实验、同一观察窗口的 point-in-time 对照") }
                item { BenchmarkCard(data.performance.benchmark) }
                item { TradingSection("周期表现", "3 / 5 / 10 / 20 个可观察交易日") }
                data.breakdown.benchmark_horizon_breakdown.forEach { row ->
                    item(key = "benchmark-${row.market}-${row.horizon_sessions}") { BenchmarkHorizonRow(row) }
                }
                if (data.breakdown.benchmark_horizon_breakdown.isEmpty()) {
                    item { LabMessageCard("暂无可用的周期基准拆分。") }
                }
                item { TradingSection("动作拆分", "按 Formal Action 与观察周期查看已冻结结果") }
                data.breakdown.action_breakdown.forEachIndexed { index, row ->
                    item(key = "action-$index-${row.action}-${row.horizon_sessions}") { DecisionBreakdownRow(row, mode = "action") }
                }
                if (data.breakdown.action_breakdown.isEmpty()) {
                    item { LabMessageCard("暂无动作拆分；可能是样本尚未达到可评估状态。") }
                }
                item { TradingSection("市场环境", "Regime 只作为评估切片，不产生交易动作") }
                data.breakdown.regime_breakdown.forEachIndexed { index, row ->
                    item(key = "regime-$index-${row.market_regime}-${row.horizon_sessions}") { DecisionBreakdownRow(row, mode = "regime") }
                }
                if (data.breakdown.regime_breakdown.isEmpty()) {
                    item { LabMessageCard("暂无市场环境拆分。") }
                }
                item { TradingSection("执行归因", "区分 EXECUTED / DEFERRED / BLOCKED 等真实执行结果") }
                data.breakdown.execution_attribution.forEach { row ->
                    item(key = "execution-${row.disposition}") { ExecutionRow(row) }
                }
                if (data.breakdown.execution_attribution.isEmpty()) {
                    item { LabMessageCard("暂无执行归因数据。") }
                }
                item { AvailabilityCard(data) }
                state.refreshError?.let { message ->
                    item { LabMessageCard("刷新失败，继续显示上次成功结果：$message", isError = true) }
                }
            }
        }
    }
}

@Composable
private fun ExperimentIdentityCard(data: LabDashboardData) {
    val experiment = data.experiment
    Card(
        Modifier.padding(horizontal = 20.dp, vertical = 8.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("${experiment.strategy_id} · v${experiment.strategy_version}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text("实验 ${experiment.experiment_id}@${experiment.experiment_version} · ${labExperimentStatus(experiment.status)}", style = MaterialTheme.typography.bodySmall)
            Text("冻结 Universe ${experiment.universe_snapshot_hash.take(12)}…", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("Evaluation 仅测量历史结果，不会自动修改 Formal SWING_V1。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
        }
    }
}

@Composable
private fun SampleQualityCard(data: LabDashboardData) {
    val strategy = data.performance.strategy
    val counts = data.summary.outcome_counts
    Card(
        Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(labSampleQualityLabel(strategy.sample_quality), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            LabMetricPair("已解析决策", strategy.resolved_decision_count?.toString() ?: "—", "完成交易", strategy.completed_trade_count?.toString() ?: "—")
            LabMetricPair("覆盖证券", strategy.distinct_symbol_count?.toString() ?: "—", "终态结果", counts.decision_terminal_count.toString())
            val unresolved = counts.decision_insufficient_count + counts.decision_invalid_count
            Text("数据不足/无效结果 $unresolved 条", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun StrategyPerformanceCard(strategy: LabStrategyPerformanceDto) {
    Card(
        Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            if (!strategy.available) {
                Text("StrategyEvaluation 尚未物化。", fontWeight = FontWeight.SemiBold)
                LabReasonCodes(strategy.reason_codes)
                return@Column
            }
            LabMetricPair("胜率", labPercent(strategy.win_rate), "盈亏比", labNumber(strategy.payoff_ratio))
            LabMetricPair("Expectancy", labSignedPercent(strategy.expectancy), "Profit Factor", labNumber(strategy.profit_factor))
            LabMetricPair("平均单笔净收益", labSignedPercent(strategy.average_episode_net_return), "平均持有", strategy.average_holding_sessions?.let { "${labNumber(it)} 日" } ?: "—")
            LabMetricPair("总费用", strategy.total_fees?.let { String.format(Locale.US, "%.2f", it) } ?: "—", "最大连续亏损", strategy.max_consecutive_losses?.toString() ?: "—")
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Text("账户级总收益 / 最大回撤 / 换手率", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
            if (strategy.total_return == null || strategy.max_drawdown == null || strategy.turnover == null) {
                Text("尚不可用：实验级 Equity Curve 尚未建立。不会用重叠 TradeEpisode 拼出假账户曲线。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                LabReasonCodes(strategy.reason_codes)
            } else {
                LabMetricPair("总收益", labSignedPercent(strategy.total_return), "最大回撤", labSignedPercent(strategy.max_drawdown))
            }
        }
    }
}

@Composable
private fun BenchmarkCard(benchmark: LabBenchmarkPerformanceDto) {
    Card(
        Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (!benchmark.available) {
                Text("BenchmarkEvaluation 尚未物化。", fontWeight = FontWeight.SemiBold)
                LabReasonCodes(benchmark.reason_codes)
                return@Column
            }
            Text(labBenchmarkTypeLabel(benchmark.benchmark_type), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            LabMetricPair("策略窗口均值", labSignedPercent(benchmark.mean_strategy_forward_return), "基准窗口均值", labSignedPercent(benchmark.mean_benchmark_forward_return))
            Text("相对基准 ${labSignedPercent(benchmark.mean_excess_forward_return)}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
            if (benchmark.portfolio_excess_return == null) {
                Text("账户级相对收益尚不可用；需等待实验与基准 Equity Curve 同步建立。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                LabReasonCodes(benchmark.reason_codes)
            }
        }
    }
}

@Composable
private fun BenchmarkHorizonRow(row: LabBenchmarkHorizonItemDto) {
    Card(Modifier.padding(horizontal = 20.dp, vertical = 2.dp).fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("${row.market} · ${row.horizon_sessions} 日", Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                Text("n=${row.resolved_count}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            LabMetricPair("策略", labSignedPercent(row.mean_strategy_forward_return), "基准", labSignedPercent(row.mean_benchmark_forward_return))
            Text("Excess ${labSignedPercent(row.mean_excess_forward_return)}", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary)
        }
    }
}

@Composable
private fun DecisionBreakdownRow(row: LabDecisionBreakdownItemDto, mode: String) {
    val title = if (mode == "action") labActionLabel(row.action) else labRegimeLabel(row.market_regime)
    Card(Modifier.padding(horizontal = 20.dp, vertical = 2.dp).fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("$title · ${row.horizon_sessions} 日", Modifier.weight(1f), fontWeight = FontWeight.SemiBold)
                Text("n=${row.sample_count}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text("平均收益 ${labSignedPercent(row.mean_forward_return)} · MFE ${labSignedPercent(row.mean_mfe)} · MAE ${labSignedPercent(row.mean_mae)}", style = MaterialTheme.typography.bodySmall)
            Text("有利 ${row.favorable_count} · 不利 ${row.unfavorable_count} · 混合 ${row.mixed_count} · 中性 ${row.neutral_count}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ExecutionRow(row: LabExecutionBreakdownItemDto) {
    Card(Modifier.padding(horizontal = 20.dp, vertical = 2.dp).fillMaxWidth()) {
        Row(Modifier.padding(14.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(labExecutionLabel(row.disposition), fontWeight = FontWeight.SemiBold)
                Text("已解析 ${row.resolved_count} · 未解析 ${row.nonresolved_count}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(row.count.toString(), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun AvailabilityCard(data: LabDashboardData) {
    val counts = data.summary.outcome_counts
    Card(
        Modifier.padding(horizontal = 20.dp, vertical = 8.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("数据口径", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Text("PENDING 决策数：${counts.pending_decision_count?.toString() ?: "未物化"}", style = MaterialTheme.typography.bodySmall)
            counts.pending_count_reason?.let { Text(labReasonLabel(it), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
            Text("实验 Universe 在创建时冻结；当前自选/持仓变化不会回写历史样本。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (data.breakdown.reason_codes.isNotEmpty()) LabReasonCodes(data.breakdown.reason_codes)
        }
    }
}

@Composable
private fun LabMessageCard(
    text: String,
    isError: Boolean = false,
    actionLabel: String? = null,
    onAction: () -> Unit = {},
) {
    Card(
        Modifier.padding(horizontal = 20.dp, vertical = 12.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(text, color = if (isError) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
            actionLabel?.let { label -> TextButton(onClick = onAction) { Text(label) } }
        }
    }
}

@Composable
private fun LabMetricPair(labelA: String, valueA: String, labelB: String, valueB: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        LabMetricCell(labelA, valueA, Modifier.weight(1f))
        LabMetricCell(labelB, valueB, Modifier.weight(1f))
    }
}

@Composable
private fun LabMetricCell(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun LabReasonCodes(codes: List<String>) {
    if (codes.isEmpty()) return
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        codes.distinct().forEach { code ->
            Text(labReasonLabel(code), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

private fun labPercent(value: Double?): String = value?.let { String.format(Locale.US, "%.1f%%", it * 100.0) } ?: "—"
private fun labSignedPercent(value: Double?): String = value?.let { String.format(Locale.US, "%+.2f%%", it * 100.0) } ?: "—"
private fun labNumber(value: Double?): String = value?.let { String.format(Locale.US, "%.2f", it) } ?: "—"

private fun labSampleQualityLabel(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "STRONG" -> "样本质量：强"
    "USABLE" -> "样本质量：可用"
    "LOW" -> "样本质量：偏低"
    "INSUFFICIENT" -> "样本质量：不足"
    else -> "样本质量：未知"
}

private fun labExperimentStatus(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "PLANNED" -> "计划中"
    "ACTIVE" -> "进行中"
    "CLOSED" -> "已关闭"
    "CANCELLED" -> "已取消"
    else -> value
}

private fun labBenchmarkTypeLabel(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "MARKET_INDEX" -> "市场指数基准"
    "BUY_AND_HOLD_SYMBOL" -> "标的买入持有基准"
    "EQUAL_WEIGHT_ELIGIBLE_UNIVERSE" -> "冻结 Universe 等权基准"
    "FORMAL_SWING_V1" -> "Formal SWING_V1 参考实验"
    "NEUTRAL_DIAGNOSTIC" -> "中性诊断基准"
    else -> "基准类型未知"
}

private fun labActionLabel(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "BUY" -> "买入"
    "WAIT" -> "等待"
    "HOLD" -> "持有"
    "ADD" -> "加仓"
    "REDUCE" -> "减仓"
    "EXIT" -> "退出"
    "BLOCKED" -> "阻断"
    else -> value ?: "未知动作"
}

private fun labRegimeLabel(value: String?): String = value?.takeIf { it.isNotBlank() } ?: "未知环境"

private fun labExecutionLabel(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "EXECUTED" -> "已执行"
    "PARTIALLY_EXECUTED" -> "部分执行"
    "BLOCKED" -> "执行阻断"
    "DEFERRED" -> "延后执行"
    "EXPIRED" -> "已过期"
    "NOT_APPLICABLE" -> "无需执行"
    else -> value
}

private fun labReasonLabel(code: String): String = when (code) {
    "experiment_equity_curve_unavailable_n3_4" -> "账户级收益/回撤/换手率需等待实验 Equity Curve。"
    "experiment_and_benchmark_equity_curves_unavailable_n3_5" -> "账户级基准与 Excess 需等待双方 Equity Curve。"
    "pending_outcomes_are_derived_not_materialized_n3_6" -> "PENDING 结果按观察窗口动态推导，当前不持久化为历史成绩。"
    "strategy_evaluation_not_materialized" -> "StrategyEvaluation 尚未生成。"
    "benchmark_evaluation_not_materialized" -> "BenchmarkEvaluation 尚未生成。"
    else -> code
}
