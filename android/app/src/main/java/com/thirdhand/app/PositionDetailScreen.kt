package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.ShowChart
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
import com.thirdhand.app.researchchat.ResearchChatController
import com.thirdhand.app.researchchat.ResearchChatLine
import com.thirdhand.app.researchchat.ResearchChatScreen
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PositionDetailRoute(
    target: ResearchTargetDto,
    onBack: () -> Unit,
) {
    var secondaryPage by remember(target.symbol) { mutableStateOf<PositionSecondaryPage?>(null) }

    when (secondaryPage) {
        PositionSecondaryPage.DECISION -> {
            PositionDecisionSecondaryScreen(
                target = target,
                onBack = { secondaryPage = null },
                onOpenResearch = { secondaryPage = PositionSecondaryPage.RESEARCH },
            )
            return
        }
        PositionSecondaryPage.RESEARCH -> {
            PositionResearchSubroute(target = target, onClose = { secondaryPage = PositionSecondaryPage.DECISION })
            return
        }
        null -> Unit
    }

    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var state by remember(target.symbol) { mutableStateOf(PositionDetailUiState()) }

    fun load() = scope.launch {
        state = state.copy(loading = true, error = null)
        supervisorScope {
            val quoteDeferred = async { runCatching { loadLatestDisplayQuotes(api, listOf(target.symbol)).firstOrNull() } }
            val holdingDeferred = async { runCatching { api.holdings().firstOrNull { it.symbol == target.symbol } } }
            val accountDeferred = async { runCatching { api.paperTradingAccount() } }
            val logsDeferred = async { runCatching { api.paperTradingLogs(target.symbol, 100) } }

            val quote = quoteDeferred.await().getOrNull()
            val holding = holdingDeferred.await().getOrNull()
            val paperPosition = accountDeferred.await().getOrNull()?.positions?.firstOrNull { it.symbol == target.symbol }
            val logs = logsDeferred.await().getOrDefault(emptyList())

            val name = firstValidSecurityName(target.symbol, quote?.name, holding?.name, paperPosition?.name, target.name) ?: target.symbol

            state = PositionDetailUiState(
                loading = false,
                quote = quote,
                holding = holding,
                paperPosition = paperPosition,
                paperLogs = logs,
                resolvedName = name,
                error = if (quote == null && holding == null && paperPosition == null) "无法连接行情服务" else null,
            )
        }
    }

    LaunchedEffect(target.symbol) { load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(state.resolvedName ?: target.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text(target.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回") }
                },
                actions = {
                    IconButton(onClick = { secondaryPage = PositionSecondaryPage.DECISION }) {
                        Icon(Icons.Default.AutoGraph, contentDescription = "决策分析", tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = ::load, enabled = !state.loading) {
                        if (state.loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        else Icon(Icons.Default.Refresh, contentDescription = "刷新")
                    }
                }
            )
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge)
        ) {
            item {
                PositionHeroSection(state)
            }

            item {
                PositionMetricsGrid(state)
            }

            item {
                SectionLabel("技术图表", "K-Line View")
                Card(
                    modifier = Modifier.padding(horizontal = AppSpacing.xxLarge),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    shape = MaterialTheme.shapes.large,
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Box(Modifier.padding(vertical = AppSpacing.medium)) {
                        TradingPeriodKLinePanel(symbol = target.symbol, quote = state.quote)
                    }
                }
            }

            item {
                SectionLabel("成交流水", "Transaction History")
            }

            val executedLogs = state.paperLogs.filter { it.status == "executed" }
            if (executedLogs.isEmpty()) {
                item {
                    Text("暂无成交事实记录", Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), textAlign = TextAlign.Center, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else {
                items(executedLogs.take(20)) { log ->
                    LogItem(log)
                }
            }
        }
    }
}

@Composable
private fun PositionHeroSection(state: PositionDetailUiState) {
    val colors = MaterialTheme.marketColors
    val currentPrice = state.quote?.price ?: state.paperPosition?.last_price ?: 0.0
    val averageCost = state.paperPosition?.average_cost ?: state.holding?.average_cost ?: 0.0
    val quantity = state.paperPosition?.quantity ?: state.holding?.quantity ?: 0.0
    val pnl = if(averageCost > 0) (currentPrice - averageCost) * quantity else 0.0
    val isPositive = pnl >= 0

    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface
    ) {
        Column(Modifier.padding(AppSpacing.xxLarge)) {
            Text("当前持仓市值", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(
                text = "¥${state.paperPosition?.market_value?.positionMoney() ?: (currentPrice * quantity).positionMoney()}",
                style = MaterialTheme.typography.displayMedium,
                fontWeight = FontWeight.ExtraBold,
                color = MaterialTheme.colorScheme.onSurface
            )

            Spacer(Modifier.height(AppSpacing.medium))

            Surface(
                color = (if (isPositive) colors.rise else colors.fall).copy(alpha = 0.1f),
                shape = MaterialTheme.shapes.small
            ) {
                Row(Modifier.padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.ShowChart,
                        null,
                        modifier = Modifier.size(16.dp),
                        tint = if (isPositive) colors.rise else colors.fall
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "累计盈亏: ${if(isPositive)"+" else ""}${pnl.positionMoney()}",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold,
                        color = if (isPositive) colors.rise else colors.fall
                    )
                }
            }
        }
    }
}

@Composable
private fun PositionMetricsGrid(state: PositionDetailUiState) {
    val quantity = state.paperPosition?.quantity ?: state.holding?.quantity ?: 0.0
    val cost = state.paperPosition?.average_cost ?: state.holding?.average_cost ?: 0.0
    val current = state.quote?.price ?: state.paperPosition?.last_price ?: 0.0

    Card(
        modifier = Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(Modifier.padding(AppSpacing.large), verticalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
            Row(Modifier.fillMaxWidth()) {
                MetricCell("现价", current.positionMoney(), Modifier.weight(1f))
                MetricCell("持仓数量", quantity.positionQuantity(), Modifier.weight(1f))
            }
            TradingRowDivider()
            Row(Modifier.fillMaxWidth()) {
                MetricCell("成本价", cost.positionMoney(), Modifier.weight(1f))
                MetricCell("持仓天数", state.holding?.created_at?.let { calendarHoldingDays(it).toString() } ?: "--", Modifier.weight(1f))
            }
            TradingRowDivider()
            Row(Modifier.fillMaxWidth()) {
                MetricCell("可用卖出", state.paperPosition?.sellable_quantity?.positionQuantity() ?: "--", Modifier.weight(1f))
                MetricCell("T+1锁定", state.paperPosition?.locked_quantity?.positionQuantity() ?: "0", Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun MetricCell(label: String, value: String, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun SectionLabel(title: String, subtitle: String) {
    Column(Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large)) {
        Text(title.uppercase(Locale.ROOT), style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary, letterSpacing = 1.sp)
        Text(subtitle, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun LogItem(log: PaperTradingLogDto) {
    val isBuy = log.side == "BUY"
    val colors = MaterialTheme.marketColors
    val color = if (isBuy) colors.rise else colors.fall

    Column(Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(color))
            Spacer(Modifier.width(AppSpacing.medium))
            Text(if(isBuy) "买入成交" else "卖出成交", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.weight(1f))
            Text("¥${log.price.positionMoney()}", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
        }
        Row(Modifier.padding(start = 16.dp, top = 2.dp)) {
            Text(
                "${log.executed_at.take(10)} · ${log.quantity.toInt()} 股",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
        Spacer(Modifier.height(AppSpacing.medium))
        TradingRowDivider()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun PositionDecisionSecondaryScreen(
    target: ResearchTargetDto,
    onBack: () -> Unit,
    onOpenResearch: () -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("决策与研究", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回") }
                }
            )
        }
    ) { padding ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).background(MaterialTheme.colorScheme.background)) {
            item {
                DecisionWorkspaceSummaryPanel(
                    symbol = target.symbol,
                    modifier = Modifier.padding(top = AppSpacing.large),
                )
            }
            item {
                Column(Modifier.padding(AppSpacing.xxLarge), verticalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
                    Text("这里集中展示 Formal Decision、What Changed 等决策演进过程。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Button(onClick = onOpenResearch, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium) {
                        Icon(Icons.Default.AutoGraph, null)
                        Spacer(Modifier.width(AppSpacing.small))
                        Text("进入 AI Research 深度对话")
                    }
                }
            }
        }
    }
}

@Composable
fun PositionResearchSubroute(
    target: ResearchTargetDto,
    onClose: () -> Unit,
) {
    val controller = remember(target.symbol) { ResearchChatController() }
    var conversation by remember(target.symbol) { mutableStateOf<List<ResearchChatLine>>(emptyList()) }
    var question by remember(target.symbol) { mutableStateOf("") }
    LaunchedEffect(target.symbol) { controller.beginNewResearch(target.symbol) }
    ResearchChatScreen(
        controller = controller,
        conversation = conversation,
        onConversationChange = { conversation = it },
        question = question,
        onQuestionChange = { question = it },
        initialTarget = target,
        onOpenTradePlan = {},
        onOpenPortfolio = onClose,
        onOpenRules = {},
        onClose = onClose,
    )
}

private data class PositionDetailUiState(
    val loading: Boolean = true,
    val quote: MarketQuoteDto? = null,
    val holding: HoldingDto? = null,
    val paperPosition: PaperTradingPositionDto? = null,
    val paperLogs: List<PaperTradingLogDto> = emptyList(),
    val resolvedName: String? = null,
    val error: String? = null,
)

private enum class PositionSecondaryPage { DECISION, RESEARCH }

private fun Double.positionMoney(): String = "%.2f".format(Locale.US, this)
private fun Double.positionQuantity(): String = if (this % 1.0 == 0.0) "${toLong()} 股" else "%.2f 股".format(Locale.US, this)

private fun calendarHoldingDays(value: String): Long {
    val start = runCatching { OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8)).toLocalDate() }
        .getOrElse { runCatching { LocalDate.parse(value.take(10)) }.getOrNull() }
        ?: return 0
    return ChronoUnit.DAYS.between(start, LocalDate.now(ZoneOffset.ofHours(8))).coerceAtLeast(0) + 1
}

internal fun firstValidSecurityName(symbol: String, vararg values: String?): String? =
    values.firstOrNull { it.isValidSecurityName(symbol) }?.trim()

internal fun String?.isValidSecurityName(symbol: String): Boolean {
    val value = this?.trim().orEmpty()
    return value.isNotBlank() && !value.equals(symbol.trim(), ignoreCase = true)
}
