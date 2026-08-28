package com.thirdhand.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.components.DenseRowDivider
import com.thirdhand.app.ui.components.DenseStateTag
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.supervisorScope
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StockDetailDecisionRoute(
    target: ResearchTargetDto,
    onBack: () -> Unit,
    onResearch: (ResearchTargetDto) -> Unit,
) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var quote by remember(target.symbol) { mutableStateOf<MarketQuoteDto?>(null) }
    var holding by remember(target.symbol) { mutableStateOf<HoldingDto?>(null) }
    var paperPosition by remember(target.symbol) { mutableStateOf<PaperTradingPositionDto?>(null) }
    var loading by remember(target.symbol) { mutableStateOf(true) }
    var error by remember(target.symbol) { mutableStateOf<String?>(null) }
    var decisionWorkspaceOpen by remember(target.symbol) { mutableStateOf(false) }

    fun load() = scope.launch {
        loading = true
        error = null
        supervisorScope {
            val quoteResult = async {
                runCatching { loadLatestDisplayQuotes(api, listOf(target.symbol)).firstOrNull() }
            }
            val holdingResult = async {
                runCatching { api.holdings().firstOrNull { it.symbol == target.symbol } }
            }
            val paperAccountResult = async { runCatching { api.paperTradingAccount() } }

            quoteResult.await()
                .onSuccess { quote = it }
                .onFailure { error = "行情同步异常，可稍后重试" }
            holdingResult.await().onSuccess { holding = it }
            paperAccountResult.await().onSuccess { account ->
                paperPosition = account.positions.firstOrNull { it.symbol == target.symbol }
            }
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
                            Text("决策与研究", style = CompactTypography.pageTitle)
                            Text(
                                "${target.name} · ${target.symbol}",
                                style = CompactTypography.caption,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = { decisionWorkspaceOpen = false }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回股票事实")
                        }
                    },
                    actions = {
                        IconButton(onClick = { onResearch(target) }) {
                            Icon(
                                Icons.Default.AutoGraph,
                                contentDescription = "进入 AI Research",
                                tint = MaterialTheme.colorScheme.primary,
                            )
                        }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.surface,
                    ),
                )
            },
            containerColor = MaterialTheme.colorScheme.background,
        ) { paddingValues ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(paddingValues),
                contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            ) {
                item {
                    DecisionWorkspaceSummaryPanel(
                        symbol = target.symbol,
                        modifier = Modifier.padding(top = AppSpacing.xs),
                    )
                }
                item {
                    ResearchEntryRow(onClick = { onResearch(target) })
                }
            }
        }
        return
    }

    val holdingCost = holding?.average_cost ?: paperPosition?.average_cost
    val currentPrice = quote?.price
    val returnPercent = when {
        paperPosition != null -> paperPosition?.unrealized_return_percent
        holdingCost != null && holdingCost > 0.0 && currentPrice != null ->
            (currentPrice - holdingCost) / holdingCost * 100.0
        else -> null
    }
    val membershipLabel = when {
        holding != null -> "组合持仓"
        paperPosition != null -> "模拟持仓"
        else -> null
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            target.name,
                            style = CompactTypography.pageTitle,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Text(
                            target.symbol,
                            style = CompactTypography.caption,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    IconButton(onClick = { decisionWorkspaceOpen = true }) {
                        Icon(
                            Icons.Default.AutoGraph,
                            contentDescription = "决策与研究",
                            tint = MaterialTheme.colorScheme.primary,
                        )
                    }
                    IconButton(onClick = ::load, enabled = !loading) {
                        if (loading) {
                            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Filled.Refresh, contentDescription = "刷新")
                        }
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface,
                ),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
        ) {
            if (loading && quote == null) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            }

            item {
                StockFactsHeader(
                    quote = quote,
                    membershipLabel = membershipLabel,
                    averageCost = holdingCost,
                    returnPercent = returnPercent,
                )
            }

            error?.let { message ->
                item { StockDetailStatusMessage(message, ::load) }
            }

            item { StockMarketFacts(quote) }

            item { StockDetailSectionTitle("行情走势") }
            item { TradingPeriodKLinePanel(symbol = target.symbol, quote = quote) }
        }
    }
}

@Composable
internal fun StockFactsHeader(
    quote: MarketQuoteDto?,
    membershipLabel: String? = null,
    averageCost: Double? = null,
    returnPercent: Double? = null,
) {
    val marketColors = MaterialTheme.marketColors
    val changePercent = quote?.change_percent
    val valueColor = when {
        changePercent == null || changePercent == 0.0 -> marketColors.neutral
        changePercent > 0 -> marketColors.rise
        else -> marketColors.fall
    }
    val freshness = quote.stockFreshnessPresentation()
    val currency = quote?.currency.stockCurrencySymbol()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.rowVertical,
            ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.Bottom,
        ) {
            Text(
                text = quote?.price?.let { "$currency${it.stockMoney()}" } ?: "---",
                style = CompactTypography.pageTitle.copy(
                    fontSize = 20.sp,
                    lineHeight = 26.sp,
                    fontWeight = FontWeight.Bold,
                ),
                color = valueColor,
            )
            Spacer(Modifier.weight(1f))
            membershipLabel?.let {
                DenseStateTag(it, MaterialTheme.colorScheme.primary)
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(top = AppSpacing.xs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = quote?.change?.let { "%+.2f".format(Locale.US, it) } ?: "--",
                style = CompactTypography.secondary,
                color = valueColor,
            )
            Spacer(Modifier.width(AppSpacing.small))
            Text(
                text = changePercent?.let { "%+.2f%%".format(Locale.US, it) } ?: "--",
                style = CompactTypography.secondary,
                color = valueColor,
            )
            Spacer(Modifier.width(AppSpacing.medium))
            DenseStateTag(freshness.label, freshness.color)
            Spacer(Modifier.weight(1f))
            quote?.as_of?.takeIf { it.isNotBlank() }?.let { asOf ->
                Text(
                    stockTimestamp(asOf),
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        if (averageCost != null || returnPercent != null) {
            DenseRowDivider(
                modifier = Modifier.padding(vertical = AppSpacing.small),
                inset = false,
            )
            Row(Modifier.fillMaxWidth()) {
                StockHeaderMetric(
                    label = "参考成本",
                    value = averageCost?.let { "$currency${it.stockMoney()}" } ?: "--",
                    modifier = Modifier.weight(1f),
                )
                val returnColor = when {
                    returnPercent == null || returnPercent == 0.0 -> marketColors.neutral
                    returnPercent > 0 -> marketColors.rise
                    else -> marketColors.fall
                }
                StockHeaderMetric(
                    label = "参考盈亏",
                    value = returnPercent?.let { "%+.2f%%".format(Locale.US, it) } ?: "--",
                    valueColor = returnColor,
                    modifier = Modifier.weight(1f),
                    alignEnd = true,
                )
            }
        }
    }
    DenseRowDivider(inset = false)
}

@Composable
private fun StockHeaderMetric(
    label: String,
    value: String,
    modifier: Modifier,
    valueColor: Color = MaterialTheme.colorScheme.onSurface,
    alignEnd: Boolean = false,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = if (alignEnd) Alignment.End else Alignment.Start,
    ) {
        Text(
            label,
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            style = CompactTypography.rowValue,
            color = valueColor,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
internal fun StockMarketFacts(quote: MarketQuoteDto?) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(
                horizontal = AppSpacing.contentHorizontal,
                vertical = AppSpacing.rowVertical,
            ),
    ) {
        Column(Modifier.weight(1f)) {
            StockMarketFact("最高", quote?.high?.stockMoney() ?: "--")
            StockMarketFact("最低", quote?.low?.stockMoney() ?: "--")
        }
        Column(Modifier.weight(1f)) {
            StockMarketFact("今开", quote?.open?.stockMoney() ?: "--")
            StockMarketFact("昨收", quote?.previous_close?.stockMoney() ?: "--")
        }
        Column(Modifier.weight(1f)) {
            StockMarketFact("成交量", quote?.volume?.compactVolume() ?: "--", alignEnd = true)
            StockMarketFact("成交额", quote?.amount?.compactAmount() ?: "--", alignEnd = true)
        }
    }
    DenseRowDivider(inset = false)
}

@Composable
private fun StockMarketFact(label: String, value: String, alignEnd: Boolean = false) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = AppSpacing.xxs),
        horizontalArrangement = if (alignEnd) Arrangement.End else Arrangement.Start,
    ) {
        Text(
            "$label ",
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            style = CompactTypography.caption,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }
}

@Composable
private fun StockDetailSectionTitle(title: String) {
    Text(
        text = title,
        modifier = Modifier.padding(
            start = AppSpacing.contentHorizontal,
            end = AppSpacing.contentHorizontal,
            top = AppSpacing.sectionVertical,
            bottom = AppSpacing.xs,
        ),
        style = CompactTypography.sectionTitle,
        color = MaterialTheme.colorScheme.onSurface,
    )
}

@Composable
private fun ResearchEntryRow(onClick: () -> Unit) {
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
            Icon(
                Icons.Default.AutoGraph,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(18.dp),
            )
            Spacer(Modifier.width(AppSpacing.small))
            Column(Modifier.weight(1f)) {
                Text("AI 深度研究", style = CompactTypography.rowTitle)
                Text(
                    "进入现有研究与对话，不改变正式决策权限",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Icon(
                Icons.Default.ChevronRight,
                contentDescription = "进入 AI 深度研究",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        DenseRowDivider()
    }
}

@Composable
private fun StockDetailStatusMessage(message: String, retry: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal)
            .heightIn(min = AppSpacing.touchTarget),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            message,
            modifier = Modifier.weight(1f),
            style = CompactTypography.secondary,
            color = MaterialTheme.colorScheme.error,
        )
        TextButton(onClick = retry) {
            Text("重试", style = CompactTypography.secondary)
        }
    }
    DenseRowDivider(inset = false)
}

private data class StockFreshnessPresentation(
    val label: String,
    val color: Color,
)

@Composable
private fun MarketQuoteDto?.stockFreshnessPresentation(): StockFreshnessPresentation = when (this?.display_freshness) {
    "live", "realtime" -> StockFreshnessPresentation("实时", MaterialTheme.marketColors.rise)
    "session_close" -> StockFreshnessPresentation("收盘", MaterialTheme.colorScheme.onSurfaceVariant)
    "refreshing" -> StockFreshnessPresentation("同步中", MaterialTheme.colorScheme.primary)
    "stale" -> StockFreshnessPresentation("过期", MaterialTheme.marketColors.warning)
    else -> StockFreshnessPresentation("暂无行情", MaterialTheme.colorScheme.onSurfaceVariant)
}

private fun stockTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse {
    value.replace('T', ' ')
        .substringBefore('+')
        .substringBefore('Z')
        .take(16)
}

private fun String?.stockCurrencySymbol(): String = when (this?.uppercase(Locale.ROOT)) {
    "HKD" -> "HK$"
    "USD" -> "$"
    else -> "¥"
}

private fun Double.stockMoney(): String = "%.2f".format(Locale.US, this)

private fun Double.compactVolume(): String = when {
    this >= 100_000_000 -> "%.1f亿".format(Locale.US, this / 100_000_000)
    this >= 10_000 -> "%.1f万".format(Locale.US, this / 10_000)
    else -> "%.0f".format(Locale.US, this)
}

private fun Double.compactAmount(): String = when {
    this >= 100_000_000 -> "%.1f亿".format(Locale.US, this / 100_000_000)
    this >= 10_000 -> "%.1f万".format(Locale.US, this / 10_000)
    else -> "%.0f".format(Locale.US, this)
}
