package com.thirdhand.app

import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.android.tools.screenshot.PreviewTest
import java.time.LocalDate
import kotlin.math.sin

@PreviewTest
@Preview(
    name = "Stock detail - target fidelity",
    showBackground = true,
    widthDp = 420,
    heightDp = 900,
)
@Composable
fun StockDetailTargetFidelityScreenshotTest() {
    val target = ResearchTargetDto(
        symbol = "002682.SZ",
        name = "龙洲股份",
        status = "active_holding",
        last_activity_at = "2026-09-02T11:54:00+08:00",
    )
    val quote = MarketQuoteDto(
        symbol = "002682.SZ",
        name = "龙洲股份",
        price = 5.13,
        change_percent = 0.99,
        change = 0.05,
        open = 5.00,
        high = 5.13,
        low = 5.00,
        previous_close = 5.08,
        volume = 51_000.0,
        amount = 261_630.0,
        turnover_rate = 1.02,
        currency = "CNY",
        source = "screenshot-fixture",
        retrieved_at = "2026-09-02T11:54:00+08:00",
        freshness_note = "fresh",
        as_of = "2026-09-02T11:54:00+08:00",
        is_realtime = true,
        display_freshness = "live",
    )
    val holding = HoldingDto(
        id = "holding-002682",
        symbol = "002682.SZ",
        name = "龙洲股份",
        quantity = 1100.0,
        average_cost = 4.882172727,
        created_at = "2026-06-01T09:30:00+08:00",
    )
    val paperPosition = PaperTradingPositionDto(
        symbol = "002682.SZ",
        name = "龙洲股份",
        quantity = 1100.0,
        average_cost = 4.882172727,
        last_price = 5.13,
        market_value = 5643.0,
        unrealized_pnl = 272.61,
        unrealized_return_percent = 5.08,
        sellable_quantity = 1100.0,
        locked_quantity = 0.0,
        updated_at = "2026-09-02T11:54:00+08:00",
    )
    val bars = targetReferenceBars()
    val markers = listOf(
        PaperTradingLogDto(
            id = "sell-marker",
            symbol = "002682.SZ",
            name = "龙洲股份",
            side = "SELL",
            quantity = 100.0,
            price = bars[bars.lastIndex - 5].close,
            cash_before = 10_000.0,
            cash_after = 10_430.0,
            reason = "fixture",
            executed_at = "${bars[bars.lastIndex - 5].trading_date}T10:20:00+08:00",
        ),
        PaperTradingLogDto(
            id = "buy-marker",
            symbol = "002682.SZ",
            name = "龙洲股份",
            side = "BUY",
            quantity = 100.0,
            price = bars[bars.lastIndex - 2].close,
            cash_before = 10_430.0,
            cash_after = 9_960.0,
            reason = "fixture",
            executed_at = "${bars[bars.lastIndex - 2].trading_date}T14:10:00+08:00",
        ),
    )

    ThirdHandTheme(ThemeMode.LIGHT) {
        StockDetailVisualScaffold(
            target = target,
            quote = quote,
            holding = holding,
            paperPosition = paperPosition,
            loading = false,
            error = null,
            onBack = {},
            onDecision = {},
            onRefresh = {},
            chartContent = {
                TradingPeriodKLineContent(
                    period = "日线",
                    onPeriodChange = {},
                    dailyBars = bars,
                    intradayBars = emptyList(),
                    paperLogs = markers,
                    quote = quote,
                    loading = false,
                    loadingMessage = "",
                    loadingDetail = "",
                    intradayLoading = false,
                    error = null,
                    indicatorsVisible = true,
                    onIndicatorToggle = {},
                    onRetry = {},
                )
            },
            onPrimaryDestination = {},
        )
    }
}

private fun targetReferenceBars(): List<DailyPriceDto> {
    val start = LocalDate.of(2026, 6, 3)
    val days = generateSequence(start) { it.plusDays(1) }
        .filter { it.dayOfWeek.value <= 5 }
        .takeWhile { !it.isAfter(LocalDate.of(2026, 9, 2)) }
        .toList()

    return days.mapIndexed { index, date ->
        val progress = index.toDouble() / (days.lastIndex.coerceAtLeast(1))
        val base = when {
            progress < 0.30 -> 6.85 - progress / 0.30 * 1.60
            progress < 0.74 -> 5.25 - (progress - 0.30) / 0.44 * 1.18
            else -> 4.07 + (progress - 0.74) / 0.26 * 0.82
        }
        val wave = sin(index * 0.62) * 0.10
        val open = base + wave
        val close = if (index == days.lastIndex) 5.13 else open + sin(index * 1.31) * 0.08
        DailyPriceDto(
            trading_date = date.toString(),
            open = if (index == days.lastIndex) 5.00 else open,
            close = close,
            high = if (index == days.lastIndex) 5.13 else maxOf(open, close) + 0.07,
            low = if (index == days.lastIndex) 5.00 else minOf(open, close) - 0.06,
            volume = if (index >= days.lastIndex - 5) 42_000.0 + (index % 4) * 13_000.0 else 8_000.0 + (index % 9) * 2_600.0,
            amount = 200_000.0 + index * 1_300.0,
            turnover_rate = if (index == days.lastIndex) 1.02 else 0.3 + (index % 7) * 0.08,
            adjustment = "qfq",
            source = "screenshot-fixture",
        )
    }
}
