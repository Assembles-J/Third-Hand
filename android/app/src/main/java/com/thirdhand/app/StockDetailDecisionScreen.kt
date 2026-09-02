package com.thirdhand.app

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Wallet
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.zIndex
import com.thirdhand.app.ui.components.CompactBottomNavigation
import com.thirdhand.app.ui.components.CompactNavigationItem
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
        StockDecisionSecondarySurface(
            target = target,
            onBack = { decisionWorkspaceOpen = false },
            onResearch = { onResearch(target) },
        )
        return
    }

    StockDetailVisualScaffold(
        target = target,
        quote = quote,
        holding = holding,
        paperPosition = paperPosition,
        loading = loading,
        error = error,
        onBack = onBack,
        onDecision = { decisionWorkspaceOpen = true },
        onRefresh = ::load,
        chartContent = {
            TradingPeriodKLinePanel(symbol = target.symbol, quote = quote)
        },
        onPrimaryDestination = {
            // The current single-activity shell owns the actual tab state. Until
            // that owner exposes destination callbacks to this nested route,
            // leaving detail returns to the already-selected primary destination.
            onBack()
        },
    )
}

@Composable
private fun StockDecisionSecondarySurface(
    target: ResearchTargetDto,
    onBack: () -> Unit,
    onResearch: () -> Unit,
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
                        .height(60.dp)
                        .padding(horizontal = AppSpacing.xs),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    IconButton(onClick = onBack, modifier = Modifier.size(AppSpacing.touchTarget)) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回股票详情")
                    }
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .padding(start = AppSpacing.small),
                    ) {
                        Text("决策与研究", style = CompactTypography.pageTitle, fontWeight = FontWeight.SemiBold)
                        Text(
                            "${target.name} · ${target.symbol}",
                            style = CompactTypography.caption,
                            color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.82f),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    IconButton(onClick = onResearch, modifier = Modifier.size(AppSpacing.touchTarget)) {
                        Icon(Icons.Default.AutoGraph, contentDescription = "进入 AI 深度研究")
                    }
                }
            }
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
            item { ResearchEntryRow(onClick = onResearch) }
        }
    }
}

/**
 * Pure stock-detail visual surface used by the real route and screenshot fixtures.
 * The hierarchy intentionally follows the approved reference: red system/header
 * chrome -> overlapping white factual summary -> one technical chart card ->
 * compact technical/decision entry -> persistent five-item primary navigation.
 */
@Composable
internal fun StockDetailVisualScaffold(
    target: ResearchTargetDto,
    quote: MarketQuoteDto?,
    holding: HoldingDto?,
    paperPosition: PaperTradingPositionDto?,
    loading: Boolean,
    error: String?,
    onBack: () -> Unit,
    onDecision: () -> Unit,
    onRefresh: () -> Unit,
    chartContent: @Composable () -> Unit,
    onPrimaryDestination: (Int) -> Unit,
) {
    Scaffold(
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.primary),
            ) {
                StockTargetTopBar(
                    target = target,
                    loading = loading,
                    onBack = onBack,
                    onDecision = onDecision,
                    onRefresh = onRefresh,
                )
                Spacer(Modifier.height(24.dp))
            }
        },
        bottomBar = {
            CompactBottomNavigation(
                selectedTab = 3,
                items = stockDetailPrimaryItems(),
                onTabSelected = onPrimaryDestination,
                modifier = Modifier.height(56.dp),
            )
        },
        containerColor = MaterialTheme.colorScheme.background,
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .offset(y = (-24).dp)
                .zIndex(1f),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            item {
                StockTargetSummaryCard(
                    target = target,
                    quote = quote,
                    holding = holding,
                    paperPosition = paperPosition,
                )
            }

            if (loading && quote == null && holding == null && paperPosition == null) {
                item {
                    LinearProgressIndicator(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = AppSpacing.contentHorizontal),
                    )
                }
            }

            error?.let { message ->
                item { StockDetailStatusMessage(message, onRefresh) }
            }

            item { chartContent() }

            item { StockTechnicalSummaryCard(onClick = onDecision) }
        }
    }
}

@Composable
private fun StockTargetTopBar(
    target: ResearchTargetDto,
    loading: Boolean,
    onBack: () -> Unit,
    onDecision: () -> Unit,
    onRefresh: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .height(62.dp)
            .padding(horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack, modifier = Modifier.size(AppSpacing.touchTarget)) {
            Icon(
                Icons.AutoMirrored.Filled.ArrowBack,
                contentDescription = "返回",
                tint = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier.size(28.dp),
            )
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .padding(start = 8.dp),
        ) {
            Text(
                target.name,
                style = CompactTypography.pageTitle.copy(fontSize = 20.sp, lineHeight = 24.sp),
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onPrimary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                target.symbol.substringBefore('.'),
                style = CompactTypography.secondary,
                color = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.92f),
                maxLines = 1,
            )
        }

        IconButton(onClick = onDecision, modifier = Modifier.size(AppSpacing.touchTarget)) {
            Icon(
                Icons.Default.AutoGraph,
                contentDescription = "决策与研究",
                tint = MaterialTheme.colorScheme.onPrimary,
                modifier = Modifier.size(26.dp),
            )
        }
        IconButton(
            onClick = onRefresh,
            enabled = !loading,
            modifier = Modifier.size(AppSpacing.touchTarget),
        ) {
            if (loading) {
                CircularProgressIndicator(
                    modifier = Modifier.size(20.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary,
                )
            } else {
                Icon(
                    Icons.Default.Refresh,
                    contentDescription = "刷新",
                    tint = MaterialTheme.colorScheme.onPrimary,
                    modifier = Modifier.size(28.dp),
                )
            }
        }
    }
}

@Composable
internal fun StockTargetSummaryCard(
    target: ResearchTargetDto,
    quote: MarketQuoteDto?,
    holding: HoldingDto?,
    paperPosition: PaperTradingPositionDto?,
) {
    val colors = MaterialTheme.marketColors
    val currency = quote?.currency.stockCurrencySymbol()
    val currentPrice = quote?.price ?: paperPosition?.last_price
    val averageCost = holding?.average_cost ?: paperPosition?.average_cost
    val quantity = holding?.quantity ?: paperPosition?.quantity
    val hasPosition = quantity != null && quantity > 0.0 && averageCost != null && averageCost > 0.0

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 3.dp),
    ) {
        if (hasPosition) {
            val price = currentPrice ?: averageCost
            val marketValue = price * quantity
            val pnl = (price - averageCost) * quantity
            val pnlPercent = if (averageCost > 0.0) (price - averageCost) / averageCost * 100.0 else 0.0
            val pnlColor = when {
                pnl > 0.0 -> colors.rise
                pnl < 0.0 -> colors.fall
                else -> colors.neutral
            }
            val sellable = paperPosition?.sellable_quantity
            val locked = paperPosition?.locked_quantity
            val lockLabel = if (target.symbol.isCnSecuritySymbol()) "T+1锁定" else "锁定数量"

            Column(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                verticalArrangement = Arrangement.spacedBy(15.dp),
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
                            "$currency${marketValue.stockPositionMoney()}",
                            style = MaterialTheme.typography.headlineLarge.copy(fontSize = 29.sp, lineHeight = 34.sp),
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface,
                        )
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text(
                            "累计盈亏",
                            style = CompactTypography.secondary,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Text(
                            "${if (pnl > 0) "+" else ""}$currency${pnl.stockPositionMoney()}  ${if (pnlPercent > 0) "+" else ""}${"%.2f".format(Locale.US, pnlPercent)}%",
                            style = MaterialTheme.typography.titleMedium.copy(fontSize = 18.sp),
                            fontWeight = FontWeight.SemiBold,
                            color = pnlColor,
                        )
                    }
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalAlignment = Alignment.Top,
                ) {
                    StockTargetFact(
                        label = "现价",
                        value = "$currency${price.stockMoney()}",
                        modifier = Modifier.weight(1.25f),
                        badge = quote.stockFreshnessPresentation().label,
                    )
                    StockTargetFact(
                        label = "成本价",
                        value = "$currency${averageCost.stockMoney()}",
                        modifier = Modifier.weight(1f),
                    )
                    StockTargetFact(
                        label = "持仓数量",
                        value = quantity.stockQuantityText(),
                        modifier = Modifier.weight(1.05f),
                    )
                    StockTargetFact(
                        label = "可用卖出",
                        value = sellable?.stockQuantityText() ?: "--",
                        modifier = Modifier.weight(1.05f),
                    )
                    StockTargetFact(
                        label = lockLabel,
                        value = locked?.stockQuantityText() ?: "--",
                        modifier = Modifier.weight(1.05f),
                        alignEnd = true,
                    )
                }
            }
        } else {
            val changePercent = quote?.change_percent
            val changeColor = when {
                changePercent == null || changePercent == 0.0 -> colors.neutral
                changePercent > 0.0 -> colors.rise
                else -> colors.fall
            }
            Column(
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 14.dp),
                verticalArrangement = Arrangement.spacedBy(15.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.Bottom,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("最新价", style = CompactTypography.secondary, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(
                            currentPrice?.let { "$currency${it.stockMoney()}" } ?: "--",
                            style = MaterialTheme.typography.headlineLarge.copy(fontSize = 29.sp, lineHeight = 34.sp),
                            fontWeight = FontWeight.Bold,
                            color = changeColor,
                        )
                    }
                    Column(horizontalAlignment = Alignment.End) {
                        Text("今日涨跌", style = CompactTypography.secondary, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text(
                            "${quote?.change?.let { "%+.2f".format(Locale.US, it) } ?: "--"}  ${changePercent?.let { "%+.2f%%".format(Locale.US, it) } ?: "--"}",
                            style = MaterialTheme.typography.titleMedium.copy(fontSize = 18.sp),
                            fontWeight = FontWeight.SemiBold,
                            color = changeColor,
                        )
                    }
                }
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    StockTargetFact("现价", currentPrice?.let { "$currency${it.stockMoney()}" } ?: "--", Modifier.weight(1.2f), quote.stockFreshnessPresentation().label)
                    StockTargetFact("今开", quote?.open?.stockMoney() ?: "--", Modifier.weight(1f))
                    StockTargetFact("最高", quote?.high?.stockMoney() ?: "--", Modifier.weight(1f))
                    StockTargetFact("最低", quote?.low?.stockMoney() ?: "--", Modifier.weight(1f))
                    StockTargetFact("成交量", quote?.volume?.compactVolume() ?: "--", Modifier.weight(1.1f), alignEnd = true)
                }
            }
        }
    }
}

@Composable
private fun StockTargetFact(
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
                Spacer(Modifier.width(4.dp))
                Surface(
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.09f),
                    contentColor = MaterialTheme.colorScheme.primary,
                    shape = RoundedCornerShape(5.dp),
                ) {
                    Text(
                        badge,
                        modifier = Modifier.padding(horizontal = 5.dp, vertical = 2.dp),
                        style = CompactTypography.caption.copy(fontSize = 9.sp),
                        fontWeight = FontWeight.Medium,
                    )
                }
            }
        }
    }
}

@Composable
internal fun StockTechnicalSummaryCard(onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 8.dp)) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onClick)
                    .heightIn(min = 30.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "交易信号 / 技术摘要",
                    modifier = Modifier.weight(1f),
                    style = CompactTypography.sectionTitle,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    "查看详情",
                    style = CompactTypography.secondary,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Icon(
                    Icons.Default.ChevronRight,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(18.dp),
                )
            }
            Spacer(Modifier.height(6.dp))
            Surface(
                modifier = Modifier.fillMaxWidth(),
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.055f),
                shape = RoundedCornerShape(9.dp),
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Surface(
                        color = MaterialTheme.colorScheme.primary.copy(alpha = 0.10f),
                        contentColor = MaterialTheme.colorScheme.primary,
                        shape = RoundedCornerShape(5.dp),
                    ) {
                        Text(
                            "AI 分析",
                            modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.dp),
                            style = CompactTypography.caption,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "点击查看决策、量价与研究摘要",
                        style = CompactTypography.secondary,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun ResearchEntryRow(onClick: () -> Unit) {
    Column {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(onClick = onClick)
                .heightIn(min = AppSpacing.touchTarget)
                .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.rowVertical),
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
            Icon(Icons.Default.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        DenseRowDivider()
    }
}

@Composable
private fun StockDetailStatusMessage(message: String, retry: () -> Unit) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp),
        color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.62f),
        shape = RoundedCornerShape(10.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = AppSpacing.touchTarget)
                .padding(horizontal = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                message,
                modifier = Modifier.weight(1f),
                style = CompactTypography.secondary,
                color = MaterialTheme.colorScheme.onErrorContainer,
            )
            TextButton(onClick = retry) { Text("重试", style = CompactTypography.secondary) }
        }
    }
}

private fun stockDetailPrimaryItems() = listOf(
    CompactNavigationItem("首页", Icons.Default.Home, 0),
    CompactNavigationItem("行情", Icons.Default.AutoGraph, 1),
    CompactNavigationItem("组合", Icons.Default.Wallet, 2),
    CompactNavigationItem("策略", Icons.Default.AccountBalanceWallet, 3),
    CompactNavigationItem("自选", Icons.Default.Bookmark, 4),
)

private fun String.isCnSecuritySymbol(): Boolean {
    val normalized = uppercase(Locale.ROOT)
    return normalized.endsWith(".SZ") || normalized.endsWith(".SH") || Regex("\\d{6}").matches(normalized)
}

private fun Double.stockPositionMoney(): String = "%,.2f".format(Locale.US, this)
private fun Double.stockQuantityText(): String = if (this % 1.0 == 0.0) "%.0f股".format(Locale.US, this) else "%.2f股".format(Locale.US, this)

// Existing compact helpers are retained for the smaller component screenshot
// baselines; the actual stock-detail route above no longer uses this old detached
// header/facts hierarchy.
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
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.rowVertical),
    ) {
        Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.Bottom) {
            Text(
                text = quote?.price?.let { "$currency${it.stockMoney()}" } ?: "---",
                style = CompactTypography.pageTitle.copy(fontSize = 20.sp, lineHeight = 26.sp, fontWeight = FontWeight.Bold),
                color = valueColor,
            )
            Spacer(Modifier.weight(1f))
            membershipLabel?.let { DenseStateTag(it, MaterialTheme.colorScheme.primary) }
        }
        Row(
            modifier = Modifier.fillMaxWidth().padding(top = AppSpacing.xs),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(quote?.change?.let { "%+.2f".format(Locale.US, it) } ?: "--", style = CompactTypography.secondary, color = valueColor)
            Spacer(Modifier.width(AppSpacing.small))
            Text(changePercent?.let { "%+.2f%%".format(Locale.US, it) } ?: "--", style = CompactTypography.secondary, color = valueColor)
            Spacer(Modifier.width(AppSpacing.medium))
            DenseStateTag(freshness.label, freshness.color)
            Spacer(Modifier.weight(1f))
            quote?.as_of?.takeIf { it.isNotBlank() }?.let {
                Text(stockTimestamp(it), style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        if (averageCost != null || returnPercent != null) {
            DenseRowDivider(modifier = Modifier.padding(vertical = AppSpacing.small), inset = false)
            Row(Modifier.fillMaxWidth()) {
                StockHeaderMetric("参考成本", averageCost?.let { "$currency${it.stockMoney()}" } ?: "--", Modifier.weight(1f))
                val returnColor = when {
                    returnPercent == null || returnPercent == 0.0 -> marketColors.neutral
                    returnPercent > 0 -> marketColors.rise
                    else -> marketColors.fall
                }
                StockHeaderMetric(
                    "参考盈亏",
                    returnPercent?.let { "%+.2f%%".format(Locale.US, it) } ?: "--",
                    Modifier.weight(1f),
                    returnColor,
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
    Column(modifier = modifier, horizontalAlignment = if (alignEnd) Alignment.End else Alignment.Start) {
        Text(label, style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = CompactTypography.rowValue, color = valueColor, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
internal fun StockMarketFacts(quote: MarketQuoteDto?) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.rowVertical),
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
        modifier = Modifier.fillMaxWidth().padding(vertical = AppSpacing.xxs),
        horizontalArrangement = if (alignEnd) Arrangement.End else Arrangement.Start,
    ) {
        Text("$label ", style = CompactTypography.caption, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = CompactTypography.caption, fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.onSurface)
    }
}

private data class StockFreshnessPresentation(val label: String, val color: Color)

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
    value.replace('T', ' ').substringBefore('+').substringBefore('Z').take(16)
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
