package com.thirdhand.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Refresh
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
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
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
    var decisionWorkspaceOpen by remember(target.symbol) { mutableStateOf(false) }

    fun load() = scope.launch {
        loading = true
        error = null
        supervisorScope {
            val quoteResult = async { runCatching { loadLatestDisplayQuotes(api, listOf(target.symbol)).firstOrNull() } }
            val holdingResult = async { runCatching { api.holdings().firstOrNull { it.symbol == target.symbol } } }
            val reportResult = async { runCatching { api.latestDecision(target.symbol) } }
            val paperLogsResult = async { runCatching { api.paperTradingLogs(target.symbol, 50) } }
            val paperAccountResult = async { runCatching { api.paperTradingAccount() } }
            quoteResult.await().onSuccess { quote = it }.onFailure { error = "数据同步异常" }
            holdingResult.await().onSuccess { holding = it }
            reportResult.await().onSuccess { report = it }
            paperLogsResult.await().onSuccess { paperLogs = it }
            paperAccountResult.await().onSuccess { account -> paperPosition = account.positions.firstOrNull { it.symbol == target.symbol } }
        }
        loading = false
    }

    LaunchedEffect(target.symbol) { load() }

    BackHandler(enabled = decisionWorkspaceOpen) { decisionWorkspaceOpen = false }

    if (decisionWorkspaceOpen) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("决策工作区", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            Text("${target.name} · ${target.symbol}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = { decisionWorkspaceOpen = false }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回股票事实")
                        }
                    },
                    actions = {
                        IconButton(onClick = { onResearch(target) }) {
                            Icon(Icons.Default.AutoGraph, contentDescription = "进入 AI Research", tint = MaterialTheme.colorScheme.primary)
                        }
                    },
                )
            },
        ) { paddingValues ->
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(paddingValues),
                contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            ) {
                item { DecisionStatusBanner(quote, report) }
                item {
                    SectionHeader("决策报告", "Formal Decision · What Changed")
                    DecisionReportCard(report, onResearch = { onResearch(target) })
                }
                item {
                    SectionHeader("公司情报", "Research Evidence")
                    CompanyIntelligencePanel(
                        symbol = target.symbol,
                        researchPriority = if (paperPosition != null || holding != null) "L3" else "L2",
                    )
                }
                item {
                    SectionHeader("交易历史", "Paper Trading Logs")
                    if (paperLogs.isEmpty()) EmptyStateSmall("暂无交易记录")
                }
                items(paperLogs.take(10), key = { it.id }) { log ->
                    PaperLogRow(log, onOpenAnalysis = { selectedPaperDecisionId = log.decision_id })
                }
            }
        }

        if (selectedPaperDecisionId != null) {
            PaperDecisionAuditDialog(
                paperDecision,
                paperDecisionContext,
                paperDecisionLoading,
                paperDecisionError,
                onDismiss = { selectedPaperDecisionId = null }
            )
        }
        return
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(target.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(target.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    IconButton(onClick = { decisionWorkspaceOpen = true }) {
                        Icon(Icons.Default.AutoGraph, contentDescription = "决策与 AI", tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = ::load, enabled = !loading) {
                        if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        else Icon(Icons.Filled.Refresh, "刷新")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge)
        ) {
            item {
                DetailHeader(quote, holding, paperPosition)
            }

            error?.let { item { ErrorCard(it, ::load) } }

            item {
                MarketDataGrid(quote)
            }

            item {
                SectionHeader("行情走势", "Real-time K-Line")
                TradingPeriodKLinePanel(symbol = target.symbol, quote = quote)
            }
        }
    }
}

@Composable
private fun DetailHeader(quote: MarketQuoteDto?, holding: HoldingDto?, paperPosition: PaperTradingPositionDto?) {
    val colors = MaterialTheme.marketColors
    val changePercent = quote?.change_percent ?: 0.0
    val color = if (changePercent >= 0) colors.rise else colors.fall

    Surface(
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Bottom
            ) {
                Column {
                    Text(
                        text = quote?.price?.money() ?: "---",
                        style = MaterialTheme.typography.displayLarge,
                        fontWeight = FontWeight.ExtraBold,
                        color = color
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "${if (changePercent >= 0) "+" else ""}${"%.2f".format(quote?.change ?: 0.0)}",
                            style = MaterialTheme.typography.titleMedium,
                            color = color,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(Modifier.width(AppSpacing.medium))
                        Text(
                            text = "${if (changePercent >= 0) "+" else ""}${"%.2f".format(changePercent)}%",
                            style = MaterialTheme.typography.titleMedium,
                            color = color,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }

                if (paperPosition != null) {
                    Surface(
                        color = MaterialTheme.colorScheme.primaryContainer,
                        shape = MaterialTheme.shapes.small
                    ) {
                        Column(Modifier.padding(horizontal = 12.dp, vertical = 6.dp)) {
                            Text("当前持仓", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                            Text(
                                "${paperPosition.quantity.toInt()} 股",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                }
            }

            Spacer(Modifier.height(AppSpacing.large))

            if (paperPosition != null) {
                Row(
                    Modifier.fillMaxWidth().clip(MaterialTheme.shapes.medium).background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f)).padding(AppSpacing.medium),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    HeaderMetric("持仓成本", paperPosition.average_cost.money())
                    HeaderMetric("浮动盈亏", paperPosition.unrealized_return_percent.signedPercent(),
                        color = if (paperPosition.unrealized_return_percent >= 0) colors.rise else colors.fall)
                    HeaderMetric("持仓占比", "--")
                }
            }
        }
    }
}

@Composable
private fun HeaderMetric(label: String, value: String, color: Color = MaterialTheme.colorScheme.onSurface) {
    Column {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold, color = color)
    }
}

@Composable
private fun MarketDataGrid(quote: MarketQuoteDto?) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small),
        horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)
    ) {
        val modifier = Modifier.weight(1f)
        Column(modifier) {
            MarketDataItem("最高", quote?.high?.money() ?: "--")
            MarketDataItem("最低", quote?.low?.money() ?: "--")
        }
        Column(modifier) {
            MarketDataItem("今开", quote?.open?.money() ?: "--")
            MarketDataItem("昨收", quote?.previous_close?.money() ?: "--")
        }
        Column(modifier) {
            MarketDataItem("成交量", quote?.volume?.compactVolume() ?: "--")
            MarketDataItem("成交额", quote?.amount?.compactAmount() ?: "--")
        }
    }
}

@Composable
private fun MarketDataItem(label: String, value: String) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.labelSmall, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun SectionHeader(title: String, subtitle: String) {
    Column(Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large)) {
        Text(
            text = title.uppercase(),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
            letterSpacing = 0.5.sp
        )
        Text(
            text = subtitle,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun DecisionStatusBanner(quote: MarketQuoteDto?, report: DecisionReportDto?) {
    val presentation = quote.displayFreshnessPresentation()
    Surface(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
        color = if (presentation.isDegraded) MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.2f)
                else MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.2f),
        shape = MaterialTheme.shapes.medium,
        border = BorderStroke(1.dp, if (presentation.isDegraded) MaterialTheme.colorScheme.error.copy(alpha = 0.2f) else MaterialTheme.colorScheme.secondary.copy(alpha = 0.2f))
    ) {
        Row(Modifier.padding(AppSpacing.medium), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(if (presentation.isDegraded) MaterialTheme.marketColors.fall else MaterialTheme.marketColors.rise))
            Spacer(Modifier.width(AppSpacing.medium))
            Text(
                text = presentation.label,
                style = MaterialTheme.typography.labelSmall,
                fontWeight = FontWeight.Medium,
                color = if (presentation.isDegraded) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSecondaryContainer
            )
        }
    }
}

@Composable
private fun DecisionReportCard(report: DecisionReportDto?, onResearch: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(Modifier.padding(AppSpacing.large)) {
            if (report == null) {
                Text("暂无决策报告，点击下方按钮开始分析", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Surface(color = MaterialTheme.colorScheme.primary, shape = RoundedCornerShape(4.dp)) {
                        Text(
                            report.action.actionLabel(),
                            Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = Color.White
                        )
                    }
                    Spacer(Modifier.width(AppSpacing.small))
                    Text(
                        "报告生成于：${report.generated_at.take(16)}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(Modifier.height(AppSpacing.small))
                Text(report.summary, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
            }

            Spacer(Modifier.height(AppSpacing.large))

            Button(
                onClick = onResearch,
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.medium
            ) {
                Icon(Icons.Default.AutoGraph, null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(AppSpacing.small))
                Text("进入 AI 研究室")
            }
        }
    }
}

@Composable
private fun PaperLogRow(log: PaperTradingLogDto, onOpenAnalysis: () -> Unit) {
    val isBuy = log.side == "BUY"
    val color = if (isBuy) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall

    Column(Modifier.fillMaxWidth().clickable(onClick = onOpenAnalysis).padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Surface(
                color = color.copy(alpha = 0.1f),
                shape = RoundedCornerShape(4.dp),
                border = BorderStroke(0.5.dp, color.copy(alpha = 0.5f))
            ) {
                Text(
                    if (isBuy) "买入" else "卖出",
                    Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = color
                )
            }
            Spacer(Modifier.width(AppSpacing.medium))
            Text(
                log.executed_at.substringBefore("T").takeLast(5) + " " + log.executed_at.substringAfter("T").take(5),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.weight(1f))
            Text(
                "¥${"%.2f".format(log.price)}",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Bold
            )
        }
        Spacer(Modifier.height(4.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "${log.quantity.toInt()} 股 · 成交额 ¥${"%.0f".format(log.price * log.quantity)}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.weight(1f))
            Icon(Icons.Default.ChevronRight, null, modifier = Modifier.size(16.dp), tint = MaterialTheme.colorScheme.outlineVariant)
        }
        Spacer(Modifier.height(AppSpacing.medium))
        HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
    }
}

@Composable private fun ErrorCard(message: String, retry: () -> Unit) = Surface(
    Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
    color = MaterialTheme.colorScheme.errorContainer,
    shape = MaterialTheme.shapes.medium
) {
    Row(Modifier.padding(AppSpacing.medium), verticalAlignment = Alignment.CenterVertically) {
        Text(message, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onErrorContainer)
        TextButton(onClick = retry) { Text("重试") }
    }
}

@Composable private fun EmptyStateSmall(msg: String) = Text(
    msg,
    Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
    style = MaterialTheme.typography.bodySmall,
    color = MaterialTheme.colorScheme.onSurfaceVariant,
    textAlign = TextAlign.Center
)

private data class DisplayFreshnessPresentation(val label: String, val isDegraded: Boolean)

private fun MarketQuoteDto?.displayFreshnessPresentation(): DisplayFreshnessPresentation = when (this?.display_freshness) {
    "live" -> DisplayFreshnessPresentation("当前决策基于最新行情快照", false)
    "session_close" -> DisplayFreshnessPresentation("行情为最近交易日收盘快照，仅供展示参考", false)
    "refreshing" -> DisplayFreshnessPresentation("行情正在刷新，暂展示上一份有效快照", false)
    "stale" -> DisplayFreshnessPresentation("行情数据已过期，决策参考价值降低", true)
    else -> DisplayFreshnessPresentation("行情暂不可用，决策参考价值降低", true)
}
private fun String.actionLabel(): String = mapOf("OPEN" to "建仓买入", "BUY" to "继续买入", "ADD" to "择机加仓", "HOLD" to "继续持有", "REDUCE" to "逢高减仓", "SELL" to "清仓卖出", "EXIT" to "止损退出", "STOP" to "强制止损", "REVIEW" to "待查", "OBSERVE" to "观望")[uppercase(Locale.ROOT)] ?: this
private fun Double.money(): String = "%.2f".format(Locale.US, this)
private fun Double.signedPercent(): String = "${if (this >= 0) "+" else ""}${"%.2f".format(Locale.US, this)}%"
private fun Double.compactVolume(): String = when {
    this >= 100_000_000 -> "%.1f亿".format(this / 100_000_000)
    this >= 10_000 -> "%.1f万".format(this / 10_000)
    else -> "%.0f".format(this)
}
private fun Double.compactAmount(): String = when {
    this >= 100_000_000 -> "%.1f亿".format(this / 100_000_000)
    this >= 10_000 -> "%.1f万".format(this / 10_000)
    else -> "%.0f".format(this)
}
