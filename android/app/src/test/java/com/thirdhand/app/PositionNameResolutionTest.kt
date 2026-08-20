package com.thirdhand.app

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PositionNameResolutionTest {
    @Test
    fun symbolIsNeverAcceptedAsDisplayName() {
        assertNull(firstValidSecurityName("603553", "603553", " 603553 ", null))
    }

    @Test
    fun firstRealNameWinsAcrossQuoteLedgerAndTargetSources() {
        assertEquals(
            "安利股份",
            firstValidSecurityName("300218", "300218", "安利股份", "旧名称"),
        )
    }
}
