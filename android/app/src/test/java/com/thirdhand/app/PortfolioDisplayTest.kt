package com.thirdhand.app

import org.junit.Assert.assertEquals
import org.junit.Test

class PortfolioDisplayTest {
    @Test
    fun quantity_uses_integer_format_when_possible() {
        assertEquals("200股", portfolioQuantity(200.0))
        assertEquals("12.50股", portfolioQuantity(12.5))
    }

    @Test
    fun holding_days_include_the_opening_day() {
        assertEquals(1, portfolioHoldingDays(java.time.LocalDate.now(java.time.ZoneOffset.ofHours(8)).toString()))
    }

    @Test
    fun invalid_holding_date_does_not_invent_duration() {
        assertEquals(0, portfolioHoldingDays("unknown"))
    }
}
