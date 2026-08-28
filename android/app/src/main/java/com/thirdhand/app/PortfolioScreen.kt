package com.thirdhand.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.CompactHoldingRow
import com.thirdhand.app.ui.components.CompactHoldingsHeader
import com.thirdhand.app.ui.components.CompactPortfolioSummary
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.temporal.ChronoUnit

/** UIX4 fact-first portfolio surface. */
@Composable
fun CompactHoldingsScreen(onOpenDetail: (HoldingDto) -> Unit) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var availableCash by remember { mutableStateOf<AvailableCashDto?>(null) }
    var quotes by remember { mutableStateOf<Map<String, MarketQuoteDto>>(emptyMap()) }
    var loading by remember { mutableStateOf(true) }
    var errorMessage by remember { mutableStateOf<String?>(null) }

    fun refresh() = scope.launch {
        loading = true
        errorMessage = null
        runCatching {
            val nextHoldings = api.holdings()
            val cash = api.availableCash()
            val nextQuotes = if (nextHoldings.isNotEmpty()) {
                loadLatestDisplayQuotes(api, nextHoldings.map { it.symbol }).associateBy { it.symbol }
            } else {
                emptyMap()
            }
            Triple(nextHoldings, cash, nextQuotes)
        }.onSuccess { (nextHoldings, cash, nextQuotes) ->
            holdings = nextHoldings
            availableCash = cash
            quotes = nextQuotes
        }.onFailure {
            errorMessage = "暂时无法同步持仓与行情，请稍后重试"
        }
        loading = false
    }

    LaunchedEffect(Unit) { refresh() }

    val valuedHoldings = holdings.map { holding ->
        holding to (quotes[holding.symbol]?.price ?: holding.average_cost)
    }
    val totalMarketValue = valuedHoldings.sumOf { (holding, price) -> holding.quantity * price }
    val totalPnl = valuedHoldings.sumOf { (holding, price) -> holding.quantity * (price - holding.average_cost) }

    CompactPortfolioContent(
        holdings = holdings,
        availableCash = availableCash?.available_cash ?: 0.0,
        quotes = quotes,
        totalMarketValue = totalMarketValue,
        totalPnl = totalPnl,
        loading = loading,
        errorMessage = errorMessage,
        onRefresh = { refresh() },
        onOpenDetail = onOpenDetail,
    )
}

@Composable
internal fun CompactPortfolioContent(
    holdings: List<HoldingDto>,
    availableCash: Double,
    quotes: Map<String, MarketQuoteDto>,
    totalMarketValue: Double,
    totalPnl: Double,
    loading: Boolean,
    errorMessage: String?,
    onRefresh: () -> Unit,
    onOpenDetail: (HoldingDto) -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
    ) {
        item {
            TradingPageHeader("持仓", "资产、成本与盈亏事实") {
                IconButton(onClick = onRefresh, enabled = !loading) {
                    if (loading) {
                        CircularProgressIndicator(Modifier.size(AppSpacing.xLarge), strokeWidth = 2.dp)
                    } else {
                        Icon(Icons.Default.Refresh, contentDescription = "刷新持仓")
                    }
                }
            }
        }

        item {
            CompactPortfolioSummary(
                availableCash = availableCash,
                marketValue = totalMarketValue,
                totalPnl = totalPnl,
                holdingCount = holdings.size,
            )
        }

        errorMessage?.let { message ->
            item { CompactPortfolioStatus(message, isError = true) }
        } ?: run {
            if (holdings.isNotEmpty() && quotes.size < holdings.size) {
                item { CompactPortfolioStatus("部分行情缺失，相关市值与盈亏暂按成本价估算。", isError = false) }
            } else if (holdings.isNotEmpty() && quotes.values.any { it.display_freshness !in setOf("live", "session_close") }) {
                item { CompactPortfolioStatus("部分行情正在刷新或存在延迟，请结合行内状态查看。", isError = false) }
            }
        }

        item { CompactHoldingsHeader() }

        if (holdings.isEmpty() && !loading) {
            item {
                Text(
                    "暂无持仓记录",
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = AppSpacing.contentHorizontal, vertical = 48.dp),
                    textAlign = TextAlign.Center,
                    style = CompactTypography.secondary,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        items(holdings, key = { it.id }) { holding ->
            val quote = quotes[holding.symbol]
            val price = quote?.price ?: holding.average_cost
            CompactHoldingRow(
                holding = holding,
                quote = quote,
                positionWeight = if (totalMarketValue > 0) {
                    holding.quantity * price / totalMarketValue
                } else {
                    null
                },
                holdingDays = compactHoldingDays(holding.created_at),
                onClick = { onOpenDetail(holding) },
            )
        }
    }
}

@Composable
private fun CompactPortfolioStatus(message: String, isError: Boolean) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs),
        color = if (isError) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            message,
            modifier = Modifier.padding(horizontal = AppSpacing.medium, vertical = AppSpacing.small),
            style = CompactTypography.secondary,
            color = if (isError) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSecondaryContainer,
        )
    }
}

private fun compactHoldingDays(value: String): Long {
    val start = runCatching {
        OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8)).toLocalDate()
    }.getOrElse {
        runCatching { LocalDate.parse(value.take(10)) }.getOrNull()
    } ?: return 0
    return ChronoUnit.DAYS.between(start, LocalDate.now(ZoneOffset.ofHours(8))).coerceAtLeast(0) + 1
}
