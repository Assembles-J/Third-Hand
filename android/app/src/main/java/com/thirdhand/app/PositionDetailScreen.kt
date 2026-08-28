package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.researchchat.ResearchChatController
import com.thirdhand.app.researchchat.ResearchChatLine
import com.thirdhand.app.researchchat.ResearchChatScreen
import com.thirdhand.app.ui.components.DenseRowDivider
import com.thirdhand.app.ui.components.DenseStateTag
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
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
            val salesDeferred = async { runCatching { api.sales(target.symbol) } }

            val quote = quoteDeferred.await().getOrNull()
            val holding = holdingDeferred.await().getOrNull()
            val paperPosition = accountDeferred.await().getOrNull()?.positions?.firstOrNull { it.symbol == target.symbol }
            val sales = salesDeferred.await().getOrDefault(emptyList())

            val name = firstValidSecurityName(target.symbol, quote?.name, holding?.name, paperPosition?.name, target.name) ?: target.symbol

            state = PositionDetailUiState(
                loading = false,
                quote = quote,
                holding = holding,
                paperPosition = paperPosition,
                sales = sales,
                resolvedName = name,
                error = if (quote == null && holding == null && paperPosition == null) "无法连接行情与持仓服务" else null,
            )
        }
    }

    LaunchedEffect(target.symbol) { load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            state.resolvedName ?: target.name,
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
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回") }
                },
                actions = {
                    IconButton(onClick = { secondaryPage = PositionSecondaryPage.DECISION }) {
                        Icon(Icons.Default.AutoGraph, contentDescription = "决策分析", tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = ::load, enabled = !state.loading) {
                        if (state.loading) {
                            CircularProgressIndicator(Modifier.size(AppSpacing.xLarge), strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Default.Refresh, contentDescription = "刷新")
                        }
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
        ) {
            if (state.loading && state.quote == null && state.holding == null && state.paperPosition == null) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            }

            item { PositionHeroSection(state) }

            state.error?.let { message ->
                item { PositionStatusMessage(message) }
            }

            item { PositionMetricsGrid(state) }

            item {
                CompactSectionTitle("技术图表")
                TradingPeriodKLinePanel(symbol = target.symbol, quote = state.quote)
            }

            item { CompactSectionTitle("成交流水") }

            if (state.sales.isEmpty()) {
                item {
                    Text(
                        "暂无卖出成交记录",
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.large),
                        textAlign = TextAlign.Center,
                        style = CompactTypography.secondary,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else {
                items(state.sales.take(20), key = { it.id }) { sale -> SaleHistoryItem(sale) }
            }
        }
    }
}

@Composable
internal fun PositionHeroSection(state: PositionDetailUiState) {
    val colors = MaterialTheme.marketColors
    val currentPrice = state.quote?.price ?: state.holding?.average_cost ?: state.paperPosition?.last_price ?: 0.0
    val averageCost = state.holding?.average_cost ?: state.paperPosition?.average_cost ?: 0.0
    val quantity = state.holding?.quantity ?: state.paperPosition?.quantity ?: 0.0
    val marketValue = currentPrice * quantity
    val pnl = if (averageCost > 0) (currentPrice - averageCost) * quantity else 0.0
    val pnlPercent = if (averageCost > 0) (currentPrice - averageCost) / averageCost * 100 else 0.0
    val pnlColor = when {
        pnl > 0 -> colors.rise
        pnl < 0 -> colors.fall
        else -> colors.neutral
    }
    val currency = state.quote?.currency.positionCurrencySymbol()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.rowVertical),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
            Column(Modifier.weight(1f)) {
                Text("持仓市值", style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    "$currency${marketValue.positionMoney()}",
                    style = CompactTypography.pageTitle,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("累计盈亏", style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(
                    "${if (pnl > 0) "+" else ""}$currency${pnl.positionMoney()}  ${if (pnlPercent > 0) "+" else ""}${"%.2f".format(Locale.US, pnlPercent)}%",
                    style = CompactTypography.rowValue,
                    color = pnlColor,
                )
            }
        }

        Spacer(Modifier.height(AppSpacing.small))

        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(
                "现价 $currency${currentPrice.positionMoney()}",
                style = CompactTypography.secondary,
                fontWeight = FontWeight.Medium,
            )
            Spacer(Modifier.width(AppSpacing.small))
            DenseStateTag(
                text = positionQuoteStateLabel(state.quote?.display_freshness),
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.weight(1f))
            Text(
                "数量 ${quantity.positionQuantity()}",
                style = CompactTypography.secondary,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    DenseRowDivider(inset = false)
}

@Composable
internal fun PositionMetricsGrid(state: PositionDetailUiState) {
    val quantity = state.holding?.quantity ?: state.paperPosition?.quantity ?: 0.0
    val cost = state.holding?.average_cost ?: state.paperPosition?.average_cost ?: 0.0
    val current = state.quote?.price ?: state.holding?.average_cost ?: state.paperPosition?.last_price ?: 0.0
    val currency = state.quote?.currency.positionCurrencySymbol()

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs),
    ) {
        PositionFactPair("现价", "$currency${current.positionMoney()}", "成本价", "$currency${cost.positionMoney()}")
        DenseRowDivider(inset = false)
        PositionFactPair(
            "持仓数量",
            quantity.positionQuantity(),
            "持仓天数",
            state.holding?.created_at?.let { "${calendarHoldingDays(it)} 天" } ?: "--",
        )
        DenseRowDivider(inset = false)
        PositionFactPair(
            "可用卖出",
            state.paperPosition?.sellable_quantity?.positionQuantity() ?: "--",
            "T+1锁定",
            state.paperPosition?.locked_quantity?.positionQuantity() ?: "0股",
        )
    }
    DenseRowDivider(inset = false)
}

@Composable
private fun PositionFactPair(
    leftLabel: String,
    leftValue: String,
    rightLabel: String,
    rightValue: String,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = AppSpacing.rowVertical),
    ) {
        PositionFactCell(leftLabel, leftValue, Modifier.weight(1f))
        PositionFactCell(rightLabel, rightValue, Modifier.weight(1f), alignEnd = true)
    }
}

@Composable
private fun PositionFactCell(
    label: String,
    value: String,
    modifier: Modifier,
    alignEnd: Boolean = false,
) {
    Column(modifier, horizontalAlignment = if (alignEnd) Alignment.End else Alignment.Start) {
        Text(label, style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = CompactTypography.rowValue, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun PositionStatusMessage(message: String) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs),
        color = MaterialTheme.colorScheme.errorContainer,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            message,
            modifier = Modifier.padding(horizontal = AppSpacing.medium, vertical = AppSpacing.small),
            style = CompactTypography.secondary,
            color = MaterialTheme.colorScheme.onErrorContainer,
        )
    }
}

@Composable
private fun CompactSectionTitle(title: String) {
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
private fun SaleHistoryItem(sale: SaleRecordDto) {
    val colors = MaterialTheme.marketColors
    val pnlColor = when {
        sale.realized_pnl > 0 -> colors.rise
        sale.realized_pnl < 0 -> colors.fall
        else -> colors.neutral
    }

    Column(
        Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.rowHorizontal, vertical = AppSpacing.rowVertical),
    ) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("卖出成交", style = CompactTypography.rowTitle, fontWeight = FontWeight.SemiBold)
                Text(
                    "${sale.sold_at.take(10)} · ${sale.quantity.positionQuantity()}",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("¥${sale.sale_price.positionMoney()}", style = CompactTypography.rowValue)
                Text(
                    "已实现 ${if (sale.realized_pnl > 0) "+" else ""}¥${sale.realized_pnl.positionMoney()}",
                    style = CompactTypography.caption,
                    color = pnlColor,
                )
            }
        }
    }
    DenseRowDivider()
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
                title = { Text("决策与研究", style = CompactTypography.pageTitle) },
                navigationIcon = {
                    IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回") }
                },
            )
        },
    ) { padding ->
        LazyColumn(modifier = Modifier.fillMaxSize().padding(padding).background(MaterialTheme.colorScheme.background)) {
            item {
                DecisionWorkspaceSummaryPanel(
                    symbol = target.symbol,
                    modifier = Modifier.padding(top = AppSpacing.large),
                )
            }
            item {
                Column(Modifier.padding(AppSpacing.contentHorizontal), verticalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
                    Text(
                        "这里集中展示 Formal Decision、What Changed 等决策演进过程。",
                        style = CompactTypography.secondary,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
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

internal data class PositionDetailUiState(
    val loading: Boolean = true,
    val quote: MarketQuoteDto? = null,
    val holding: HoldingDto? = null,
    val paperPosition: PaperTradingPositionDto? = null,
    val sales: List<SaleRecordDto> = emptyList(),
    val resolvedName: String? = null,
    val error: String? = null,
)

private enum class PositionSecondaryPage { DECISION, RESEARCH }

private fun positionQuoteStateLabel(state: String?): String = when (state) {
    "live", "realtime" -> "实时"
    "session_close", "close" -> "收盘"
    "refreshing", "loading" -> "刷新中"
    "stale", "stale_fallback" -> "延迟"
    else -> "暂估"
}

private fun Double.positionMoney(): String = "%.2f".format(Locale.US, this)
private fun Double.positionQuantity(): String = if (this % 1.0 == 0.0) "${toLong()}股" else "%.2f股".format(Locale.US, this)

private fun String?.positionCurrencySymbol(): String = when (this?.uppercase(Locale.ROOT)) {
    "HKD" -> "HK$"
    "USD" -> "$"
    "CNY", "RMB", null, "" -> "¥"
    else -> "$this "
}

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
