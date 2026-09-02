package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.android.tools.screenshot.PreviewTest
import com.thirdhand.app.ui.components.KLineChart
import com.thirdhand.app.ui.theme.AppSpacing
import java.time.LocalDate

@PreviewTest
@Preview(
    name = "Holding detail chart V2",
    showBackground = true,
    widthDp = 420,
    heightDp = 900,
)
@Composable
fun HoldingDetailChartV2ScreenshotTest() {
    val bars = holdingDetailChartBars()
    val markers = listOf(
        PaperTradingLogDto(
            id = "buy-1",
            symbol = "002682.SZ",
            name = "龙洲股份",
            side = "BUY",
            quantity = 100.0,
            price = bars[62].close,
            cash_before = 10_000.0,
            cash_after = 9_500.0,
            reason = "screenshot-buy",
            executed_at = "${bars[62].trading_date}T10:12:00+08:00",
        ),
        PaperTradingLogDto(
            id = "sell-1",
            symbol = "002682.SZ",
            name = "龙洲股份",
            side = "SELL",
            quantity = 100.0,
            price = bars[80].close,
            cash_before = 9_500.0,
            cash_after = 10_020.0,
            reason = "screenshot-sell",
            executed_at = "${bars[80].trading_date}T14:18:00+08:00",
        ),
    )

    ThirdHandTheme(ThemeMode.LIGHT) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(vertical = AppSpacing.large),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.medium),
        ) {
            PositionHoldingSummaryCard(
                PositionDetailUiState(
                    loading = false,
                    resolvedName = "龙洲股份",
                    quote = MarketQuoteDto(
                        symbol = "002682.SZ",
                        name = "龙洲股份",
                        price = 5.13,
                        change_percent = 0.99,
                        change = 0.05,
                        open = 5.07,
                        high = 5.18,
                        low = 5.02,
                        previous_close = 5.08,
                        volume = 21_600_000.0,
                        amount = 110_000_000.0,
                        currency = "CNY",
                        source = "screenshot",
                        retrieved_at = "2026-09-02T14:30:00+08:00",
                        freshness_note = "fresh",
                        as_of = "2026-09-02T14:30:00+08:00",
                        is_realtime = true,
                        display_freshness = "live",
                    ),
                    holding = HoldingDto(
                        id = "holding-1",
                        symbol = "002682.SZ",
                        name = "龙洲股份",
                        quantity = 1100.0,
                        average_cost = 4.88,
                        created_at = "2026-08-01T09:00:00+08:00",
                    ),
                    paperPosition = PaperTradingPositionDto(
                        symbol = "002682.SZ",
                        name = "龙洲股份",
                        quantity = 1100.0,
                        average_cost = 4.88,
                        last_price = 5.13,
                        market_value = 5_643.0,
                        unrealized_pnl = 275.0,
                        unrealized_return_percent = 5.12,
                        sellable_quantity = 1100.0,
                        locked_quantity = 0.0,
                        updated_at = "2026-09-02T14:30:00+08:00",
                    ),
                ),
            )

            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = AppSpacing.contentHorizontal),
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                shape = MaterialTheme.shapes.large,
                elevation = CardDefaults.cardElevation(defaultElevation = 0.dp),
            ) {
                KLineChart(
                    bars = bars,
                    quote = MarketQuoteDto(
                        symbol = "002682.SZ",
                        name = "龙洲股份",
                        price = 5.13,
                        change_percent = 0.99,
                        currency = "CNY",
                        source = "screenshot",
                        retrieved_at = "2026-09-02T14:30:00+08:00",
                        freshness_note = "fresh",
                        display_freshness = "live",
                    ),
                    paperMarkers = markers,
                    modifier = Modifier.padding(AppSpacing.medium),
                )
            }
        }
    }
}

private fun holdingDetailChartBars(): List<DailyPriceDto> {
    val start = LocalDate.of(2026, 5, 1)
    return (0 until 96).map { index ->
        val trend = 6.72 - index * 0.0165
        val wave = ((index % 9) - 4) * 0.014
        val open = trend + wave
        val close = open + when (index % 4) {
            0 -> 0.045
            1 -> -0.032
            2 -> 0.022
            else -> -0.014
        }
        DailyPriceDto(
            trading_date = start.plusDays(index.toLong()).toString(),
            open = open,
            close = close,
            high = maxOf(open, close) + 0.060,
            low = minOf(open, close) - 0.055,
            volume = 8_000_000.0 + index * 170_000.0 + (index % 6) * 720_000.0,
            amount = 50_000_000.0 + index * 520_000.0,
            adjustment = "qfq",
            source = "screenshot",
        )
    }
}
