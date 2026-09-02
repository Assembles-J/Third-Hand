package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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

    val context = androidx.compose.ui.platform.LocalContext.current
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
            val name = firstValidSecurityName(
                target.symbol,
                quote?.name,
                holding?.name,
                paperPosition?.name,
                target.name,
            ) ?: target.symbol

            state = PositionDetailUiState(
                loading = false,
                quote = quote,
                holding = holding,
                paperPosition = paperPosition,
                sales = sales,
                resolvedName = name,
                error = if (quote == null && holding == null && paperPosition == null) {
                    "无法连接行情与持仓服务"
                } else null,
            )
        }
    }

    LaunchedEffect(target.symbol) { load() }

    Scaffold(
        topBar = {
            PositionDetailTopBar(
                title = state.resolvedName ?: target.name,
                symbol = target.symbol,
                loading = state.loading,
                onBack = onBack,
                onDecision = { secondaryPage = PositionSecondaryPage.DECISION },
                onRefresh = ::load,
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.medium),
        ) {
            if (state.loading && state.quote == null && state.holding == null && state.paperPosition == null) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            }

            item { PositionHoldingSummaryCard(state) }

            state.error?.let { message ->
                item { PositionStatusMessage(message) }
            }

            item {
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
private fun PositionDetailTopBar(
    title: String,
    symbol: String,
    loading: Boolean,
    onBack: () -> Unit,
    onDecision: () -> Unit,
    onRefresh: () -> Unit,
) {
    Surface(
        color = MaterialTheme.colorScheme.primary,
        contentColor = MaterialTheme.colorScheme.onPrimary,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .height(58.dp)
                .padding(horizontal = AppSpacing.xs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack, modifier = Modifier.size(AppSpacing.touchTarget)) {
                Icon(
                    Icons.AutoMirrored.Filled.ArrowBack,
                    contentDescription = "返回",
                    tint = MaterialTheme.colorScheme.onPrimary,
                )
            }

            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(start = AppSpacing.small),
            ) {
                Text(
                    title,
                    style = CompactTypography.pageTitle,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    symbol,
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.80f),
                    maxLines = 1,
                )
            }

            IconButton(onClick = onDecision, modifier = Modifier.size(AppSpacing.touchTarget)) {
                Icon(
                    Icons.Default.AutoGraph,
                    contentDescription = "决策分析",
                    tint = MaterialTheme.colorScheme.onPrimary,
                )
            }
            IconButton(
                onClick = onRefresh,
                enabled = !loading,
                modifier = Modifier.size(AppSpacing.touchTarget),
            ) {
                if (loading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(18.dp),
                        strokeWidth = 2.dp,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                } else {
                    Icon(
                        Icons.Default.Refresh,
                        contentDescription = "刷新",
                        tint = MaterialTheme.colorScheme.onPrimary,
                    )
                }
            }
        }
    }
}

@Composable
internal fun PositionHoldingSummaryCard(state: PositionDetailUiState) {
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

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = AppSpacing.large, vertical = AppSpacing.large),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.medium),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Bottom,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "持仓市值",
                        style = CompactTypography.secondary,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        "$currency${marketValue.positionMoney()}",
                        style = MaterialTheme.typography.headlineLarge,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        "累计盈亏",
                        style = CompactTypography.secondary,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        "${if (pnl > 0) "+" else ""}$currency${pnl.positionMoney()}  ${if (pnlPercent > 0) "+" else ""}${"%.2f".format(Locale.US, pnlPercent)}%",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = pnlColor,
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium),
            ) {
                PositionSummaryFact(
                    label = "现价",
                    value = "$currency${currentPrice.positionMoney()}",
                    modifier = Modifier.weight(1f),
                    badge = positionQuoteStateLabel(state.quote?.display_freshness),
                )
                PositionSummaryFact(
                    label = "成本价",
                    value = "$currency${averageCost.positionMoney()}",
                    modifier = Modifier.weight(1f),
                )
                PositionSummaryFact(
                    label = "持仓数量",
                    value = quantity.positionQuantity(),
                    modifier = Modifier.weight(1f),
                    alignEnd = true,
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium),
            ) {
                PositionSummaryFact(
                    label = "可用卖出",
                    value = state.paperPosition?.sellable_quantity?.positionQuantity() ?: "--",
                    modifier = Modifier.weight(1f),
                )
                PositionSummaryFact(
                    label = "锁定数量",
                    value = state.paperPosition?.locked_quantity?.positionQuantity() ?: "--",
                    modifier = Modifier.weight(1f),
                    alignEnd = true,
                )
            }
        }
    }
}

@Composable
private fun PositionSummaryFact(
    label: String,
    value: String,
    modifier: Modifier,
    badge: String? = null,
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
            maxLines = 1,
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                value,
                style = CompactTypography.rowValue,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (!badge.isNullOrBlank()) {
                Spacer(Modifier.width(AppSpacing.xxs))
                DenseStateTag(text = badge, color = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

/** Kept for screenshot/test compatibility while the route uses the combined V2 card. */
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

/** Kept for screenshot/test compatibility while the route uses the combined V2 card. */
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
            "锁定数量",
            state.paperPosition?.locked_quantity?.positionQuantity() ?: "--",
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
            .padding(horizontal = AppSpacing.contentHorizontal),
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
            top = AppSpacing.xs,
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

@Composable
private fun PositionDecisionSecondaryScreen(
    target: ResearchTargetDto,
    onBack: () -> Unit,
    onOpenResearch: () -> Unit,
) {
    Scaffold(
        topBar = {
            Surface(
                color = MaterialTheme.colorScheme.primary,
                contentColor = MaterialTheme.colorScheme.onPrimary,
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .statusBarsPadding()
                        .height(54.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "返回",
                            tint = MaterialTheme.colorScheme.onPrimary,
                        )
                    }
                    Text(
                        "决策与研究",
                        style = CompactTypography.pageTitle,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                }
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(MaterialTheme.colorScheme.background),
        ) {
            item {
                DecisionWorkspaceSummaryPanel(
                    symbol = target.symbol,
                    modifier = Modifier.padding(top = AppSpacing.large),
                )
            }
            item {
                Column(
                    Modifier.padding(AppSpacing.contentHorizontal),
                    verticalArrangement = Arrangement.spacedBy(AppSpacing.large),
                ) {
                    Text(
                        "这里集中展示 Formal Decision、What Changed 等决策演进过程。",
                        style = CompactTypography.secondary,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Button(
                        onClick = onOpenResearch,
                        modifier = Modifier.fillMaxWidth(),
                        shape = MaterialTheme.shapes.medium,
                    ) {
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