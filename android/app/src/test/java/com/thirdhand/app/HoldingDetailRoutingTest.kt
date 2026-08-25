package com.thirdhand.app

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class HoldingDetailRoutingTest {
    @Test
    fun active_holding_uses_fact_first_holding_detail() {
        assertTrue(opensHoldingDetail(ResearchTargetDto("01810", "小米集团-W", "active_holding", "")))
    }

    @Test
    fun watchlist_only_symbol_keeps_stock_detail_route() {
        assertFalse(opensHoldingDetail(ResearchTargetDto("00700", "腾讯控股", "watchlist", "")))
    }
}
