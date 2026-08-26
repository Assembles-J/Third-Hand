package com.thirdhand.app.watchlist

import org.junit.Assert.assertEquals
import org.junit.Test

class ReviewPlanLabelsTest {
    @Test
    fun governed_modes_are_user_readable() {
        assertEquals("本轮无需复盘", reviewModeLabel("NO_REVIEW"))
        assertEquals("仅监控风险与事件", reviewModeLabel("GUARD_ONLY"))
        assertEquals("持仓复盘", reviewModeLabel("POSITION_REVIEW"))
        assertEquals("完整研究", reviewModeLabel("FULL_RESEARCH"))
    }

    @Test
    fun skip_reason_explains_quiet_behavior() {
        assertEquals(
            "原因：今日完整研究已执行",
            reviewReasonLabel("routine_full_research_budget_exhausted"),
        )
    }
}
