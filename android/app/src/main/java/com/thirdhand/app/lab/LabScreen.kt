package com.thirdhand.app.lab

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Science
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.launch
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
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

    Scaffold(
        topBar = {
            TradingPageHeader(
                title = "策略实验室",
                subtitle = "SWING_V1 仿真评估与压力测试中心",
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                    IconButton(onClick = { scope.launch { controller.refresh() } }, enabled = state !is LabUiState.Loading) {
                        if (state is LabUiState.Loading) {
                            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Filled.Refresh, contentDescription = "刷新")
                        }
                    }
                }
            }
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues).background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small)
        ) {
            when (val uiState = state) {
                LabUiState.Loading -> {
                    item {
                        Box(Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator()
                        }
                    }
                }
                is LabUiState.Empty -> {
                    item {
                        Surface(
                            modifier = Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
                            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
                            shape = MaterialTheme.shapes.medium
                        ) {
                            Text(uiState.message, Modifier.padding(AppSpacing.large), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                is LabUiState.Error -> {
                    item {
                        Surface(
                            modifier = Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
                            color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.2f),
                            shape = MaterialTheme.shapes.medium
                        ) {
                            Column(Modifier.padding(AppSpacing.large)) {
                                Text("实验室暂时离线", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.error)
                                Text(uiState.message, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
                is LabUiState.Ready -> {
                    val data = uiState.dashboard
                    item { ExperimentIdentityCard(data) }

                    item { TradingSection("核心绩效指标", "Performance Analytics") }
                    item { StrategyPerformanceCard(data.performance.strategy) }

                    item { TradingSection("相对基准对比", "Benchmark Comparison") }
                    item { BenchmarkCard(data.performance.benchmark) }

                    item { TradingSection("多维度归因", "Factor Attribution") }

                    if (data.breakdown.action_breakdown.isNotEmpty()) {
                        item { Text("动作执行收益", modifier = Modifier.padding(horizontal = AppSpacing.xxLarge), style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold) }
                        items(data.breakdown.action_breakdown.take(5)) { row ->
                            BreakdownRow(label = labActionLabel(row.action), count = row.sample_count, value = row.mean_forward_return)
                        }
                    }

                    if (data.breakdown.regime_breakdown.isNotEmpty()) {
                        item { Text("市场环境适应性", modifier = Modifier.padding(start = AppSpacing.xxLarge, top = 8.dp, end = AppSpacing.xxLarge), style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold) }
                        items(data.breakdown.regime_breakdown.take(5)) { row ->
                            BreakdownRow(label = labRegimeLabel(row.market_regime), count = row.sample_count, value = row.mean_forward_return)
                        }
                    }

                    item { TradingSection("执行归因", "Execution Attribution") }
                    items(data.breakdown.execution_attribution) { row ->
                        ExecutionRowNew(row)
                    }
                }
            }
        }
    }
}

/** Pure rendering entry used by screenshot tests; it does not create a controller. */
@Composable
fun LabScreenContent(state: LabUiState, onBack: () -> Unit, onRefresh: () -> Unit) {
    Scaffold(
        topBar = {
            TradingPageHeader(title = "策略实验室", subtitle = "SWING_V1 仿真评估与压力测试中心") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }
                    IconButton(onClick = onRefresh) { Icon(Icons.Filled.Refresh, "刷新") }
                }
            }
        },
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues).background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            when (state) {
                LabUiState.Loading -> item { Box(Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), contentAlignment = Alignment.Center) { CircularProgressIndicator() } }
                is LabUiState.Empty -> item { Text(state.message, Modifier.padding(AppSpacing.xxLarge)) }
                is LabUiState.Error -> item { Text(state.message, Modifier.padding(AppSpacing.xxLarge), color = MaterialTheme.colorScheme.error) }
                is LabUiState.Ready -> {
                    val data = state.dashboard
                    item { ExperimentIdentityCard(data) }
                    item { TradingSection("核心绩效指标", "Performance Analytics") }
                    item { StrategyPerformanceCard(data.performance.strategy) }
                    item { TradingSection("相对基准对比", "Benchmark Comparison") }
                    item { BenchmarkCard(data.performance.benchmark) }
                }
            }
        }
    }
}

@Composable
private fun ExperimentIdentityCard(data: LabDashboardData) {
    val experiment = data.experiment
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)),
        shape = MaterialTheme.shapes.large
    ) {
        Row(Modifier.padding(AppSpacing.xxLarge), verticalAlignment = Alignment.CenterVertically) {
            Surface(color = MaterialTheme.colorScheme.primary, shape = CircleShape, modifier = Modifier.size(40.dp)) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(Icons.Default.Science, null, tint = Color.White, modifier = Modifier.size(20.dp))
                }
            }
            Spacer(Modifier.width(AppSpacing.large))
            Column {
                Text("${experiment.strategy_id} · v${experiment.strategy_version}", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
                Text("实验 ID: ${experiment.experiment_id} · ${labExperimentStatus(experiment.status)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun StrategyPerformanceCard(strategy: LabStrategyPerformanceDto) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(AppSpacing.xxLarge), verticalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                MetricItem("胜率 (Win Rate)", labPercent(strategy.win_rate), Modifier.weight(1f))
                MetricItem("盈亏比 (P/L)", labNumber(strategy.payoff_ratio), Modifier.weight(1f))
            }
            TradingRowDivider()
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                MetricItem("期望收益 (Exp)", labSignedPercent(strategy.expectancy), Modifier.weight(1f))
                MetricItem("最大回撤 (MDD)", labSignedPercent(strategy.max_drawdown), Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun BenchmarkCard(benchmark: LabBenchmarkPerformanceDto) {
    val colors = MaterialTheme.marketColors
    val excess = benchmark.mean_excess_forward_return ?: 0.0

    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(AppSpacing.xxLarge)) {
            Text(labBenchmarkTypeLabel(benchmark.benchmark_type), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(AppSpacing.medium))
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
                Text(
                    text = labSignedPercent(excess),
                    style = MaterialTheme.typography.displaySmall,
                    fontWeight = FontWeight.ExtraBold,
                    color = if (excess >= 0) colors.rise else colors.fall
                )
                Spacer(Modifier.width(AppSpacing.small))
                Text("Alpha / 超额收益", style = MaterialTheme.typography.labelMedium, modifier = Modifier.padding(bottom = 6.dp))
            }
        }
    }
}

@Composable
private fun BreakdownRow(label: String, count: Int, value: Double?) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(label, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
        Text("n=$count", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.width(AppSpacing.large))
        Text(
            labSignedPercent(value),
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Bold,
            color = if ((value ?: 0.0) >= 0) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall
        )
    }
}

@Composable
private fun ExecutionRowNew(row: LabExecutionBreakdownItemDto) {
    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = 2.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
        shape = MaterialTheme.shapes.small
    ) {
        Row(Modifier.padding(AppSpacing.medium), verticalAlignment = Alignment.CenterVertically) {
            Text(labExecutionLabel(row.disposition), Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
            Text("${row.count} 笔", style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
        }
    }
}

@Composable
private fun MetricItem(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
    }
}

// Helpers
private fun labPercent(value: Double?): String = value?.let { String.format(Locale.US, "%.1f%%", it * 100.0) } ?: "—"
private fun labSignedPercent(value: Double?): String = value?.let { String.format(Locale.US, "%+.2f%%", it * 100.0) } ?: "—"
private fun labNumber(value: Double?): String = value?.let { String.format(Locale.US, "%.2f", it) } ?: "—"

private fun labExperimentStatus(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "PLANNED" -> "计划中"
    "ACTIVE" -> "进行中"
    "CLOSED" -> "已关闭"
    "CANCELLED" -> "已取消"
    else -> value
}

private fun labBenchmarkTypeLabel(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "MARKET_INDEX" -> "市场指数对照 (Index)"
    "BUY_AND_HOLD_SYMBOL" -> "持股不动对照 (B&H)"
    else -> "全市场基准对照"
}

private fun labActionLabel(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "BUY" -> "建仓"
    "ADD" -> "加仓"
    "REDUCE" -> "减仓"
    "EXIT" -> "止损/清仓"
    else -> value ?: "其他"
}

private fun labRegimeLabel(value: String?): String = value?.takeIf { it.isNotBlank() } ?: "未知环境"

private fun labExecutionLabel(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "EXECUTED" -> "完成成交"
    "PARTIALLY_EXECUTED" -> "部分成交"
    "BLOCKED" -> "策略阻断"
    "DEFERRED" -> "延后执行"
    else -> value
}
