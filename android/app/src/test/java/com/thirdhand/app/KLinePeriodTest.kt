package com.thirdhand.app

import org.junit.Assert.assertEquals
import org.junit.Test

class KLinePeriodTest {
    private val daily = listOf(
        bar("2026-07-31", 10.0, 11.0, 100.0),
        bar("2026-08-03", 11.0, 12.0, 150.0),
        bar("2026-08-04", 12.0, 13.0, 200.0),
    )

    @Test
    fun period_selection_is_deterministic() {
        val intraday = listOf(bar("2026-08-04T09:31:00", 12.0, 12.2, 10.0))
        assertEquals(intraday, chartBarsForPeriod("分时", daily, intraday))
        assertEquals(daily, chartBarsForPeriod("日线", daily, intraday))
    }

    @Test
    fun intraday_period_keeps_only_latest_trading_session() {
        val older = bar("2026-08-03T14:59:00", 11.8, 11.9, 9.0)
        val latestOpen = bar("2026-08-04T09:31:00", 12.0, 12.1, 10.0)
        val latestLater = bar("2026-08-04T10:30:00", 12.1, 12.3, 20.0)
        val mixed = listOf(older, latestOpen, latestLater)

        assertEquals(listOf(latestOpen, latestLater), latestIntradaySession(mixed))
        assertEquals(listOf(latestOpen, latestLater), chartBarsForPeriod("分时", daily, mixed))
    }

    @Test
    fun intraday_hint_identifies_the_single_session_without_assuming_market_hours() {
        val intraday = listOf(bar("2026-08-04T09:31:00", 12.0, 12.2, 10.0))
        assertEquals("分时仅展示 2026-08-04", intradaySessionHint(intraday))
    }

    @Test
    fun monthly_aggregation_preserves_open_close_and_volume() {
        val monthly = aggregateBars(daily, "月线")
        assertEquals(2, monthly.size)
        assertEquals(11.0, monthly.last().open ?: 0.0, 0.001)
        assertEquals(13.0, monthly.last().close, 0.001)
        assertEquals(350.0, monthly.last().volume ?: 0.0, 0.001)
    }

    @Test
    fun malformed_provider_wick_is_clamped_for_chart_without_mutating_raw_bar() {
        val previous = DailyPriceDto(
            trading_date = "2026-08-31",
            open = 5.04,
            close = 5.08,
            high = 5.12,
            low = 5.00,
        )
        val malformed = DailyPriceDto(
            trading_date = "2026-09-01",
            open = 5.08,
            close = 5.13,
            high = 7.72,
            low = 3.61,
        )

        val result = sanitizeBarsForChart(listOf(previous, malformed))

        assertEquals(1, result.anomalyCount)
        assertEquals(5.13, result.bars.last().high ?: 0.0, 0.001)
        assertEquals(5.08, result.bars.last().low ?: 0.0, 0.001)
        assertEquals(7.72, malformed.high ?: 0.0, 0.001)
        assertEquals(3.61, malformed.low ?: 0.0, 0.001)
    }

    @Test
    fun ordinary_large_candle_is_preserved() {
        val normal = DailyPriceDto(
            trading_date = "2026-09-01",
            open = 5.00,
            close = 5.48,
            high = 5.52,
            low = 4.96,
        )

        val result = sanitizeBarsForChart(listOf(normal))

        assertEquals(0, result.anomalyCount)
        assertEquals(normal, result.bars.single())
    }

    private fun bar(date: String, open: Double, close: Double, volume: Double) = DailyPriceDto(
        trading_date = date,
        open = open,
        close = close,
        high = maxOf(open, close),
        low = minOf(open, close),
        volume = volume,
    )
}