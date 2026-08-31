package com.thirdhand.app.paperorder

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PaperManualOrderControllerTest {
    @Test
    fun capabilityLoadPublishesServerOwnedTradingFacts() = runBlocking {
        val capability = cnCapability()
        val gateway = FakeGateway(
            capabilityResults = mutableListOf(PaperManualOrderLoadResult.Success(capability)),
        )
        val controller = PaperManualOrderController(gateway, orderIdProvider = { "order-1" })
        controller.updateSymbol("002594")

        controller.loadCapability()

        val state = controller.state.value
        assertEquals(capability, state.capability)
        assertTrue(state.capability?.executable == true)
        assertEquals(800.0, state.serverMaximum, 0.0)
        assertEquals(null, state.errorMessage)
    }

    @Test
    fun hongKongCapabilityRemainsExplicitlyBlocked() = runBlocking {
        val capability = cnCapability().copy(
            symbol = "9863.HK",
            market = "HK",
            currency = "HKD",
            executable = false,
            reason_codes = listOf("paper_hk_execution_not_configured"),
            max_buy_quantity = 0.0,
            max_sell_quantity = 0.0,
        )
        val gateway = FakeGateway(
            capabilityResults = mutableListOf(PaperManualOrderLoadResult.Success(capability)),
        )
        val controller = PaperManualOrderController(gateway)
        controller.updateSymbol("9863.hk")

        controller.loadCapability()

        val state = controller.state.value
        assertEquals("9863.HK", state.symbol)
        assertFalse(state.canSubmit)
        assertEquals(
            "港股模拟成交暂未开放：HKD/CNY 资金与费用规则尚未完成。",
            state.errorMessage,
        )
    }

    @Test
    fun submitUsesUserIntentAndRefreshesCapabilityAfterFill() = runBlocking {
        val before = cnCapability()
        val after = before.copy(
            available_cash = 67524.4,
            held_quantity = 200.0,
            sellable_quantity = 100.0,
            locked_quantity = 100.0,
            max_buy_quantity = 700.0,
        )
        val response = PaperManualOrderResponseDto(
            status = "executed",
            fill = PaperManualOrderFillDto(
                id = "manual:android-order-1",
                symbol = "002594",
                name = "比亚迪",
                side = "BUY",
                quantity = 100.0,
                price = 87.92,
                fee = 5.0,
                cash_before = 76321.4,
                cash_after = 67524.4,
                reason = "user_manual_paper_order:android-order-1",
                fill_price_mode = "USER_MANUAL_LATEST_ELIGIBLE_OBSERVED_QUOTE",
                executed_at = "2026-08-31T14:58:03+08:00",
            ),
        )
        val gateway = FakeGateway(
            capabilityResults = mutableListOf(
                PaperManualOrderLoadResult.Success(before),
                PaperManualOrderLoadResult.Success(after),
            ),
            submitResults = mutableListOf(PaperManualOrderSubmitResult.Success(response)),
        )
        val controller = PaperManualOrderController(gateway, orderIdProvider = { "order-1" })
        controller.updateSymbol("002594")
        controller.loadCapability()
        controller.updateQuantity("100")

        val executed = controller.submit()

        assertTrue(executed)
        assertEquals("android-order-1", gateway.submitted.single().client_order_id)
        assertEquals("BUY", gateway.submitted.single().side)
        assertEquals(100.0, gateway.submitted.single().quantity, 0.0)
        assertEquals(after, controller.state.value.capability)
        assertTrue(controller.state.value.successMessage?.contains("模拟买入已成交") == true)
    }

    @Test
    fun serverRejectionKeepsServerCapabilityAndDoesNotClaimExecution() = runBlocking {
        val capability = cnCapability().copy(
            held_quantity = 100.0,
            sellable_quantity = 0.0,
            locked_quantity = 100.0,
            max_sell_quantity = 0.0,
            next_eligible_sell_at = "2026-09-01T09:30:00+08:00",
        )
        val gateway = FakeGateway(
            capabilityResults = mutableListOf(PaperManualOrderLoadResult.Success(capability)),
            submitResults = mutableListOf(
                PaperManualOrderSubmitResult.Failure(
                    message = "A 股当日买入数量受 T+1 限制，当前不可卖出。",
                    reasonCode = "paper_manual_order_t1_locked",
                    capability = capability,
                ),
            ),
        )
        val controller = PaperManualOrderController(gateway, orderIdProvider = { "order-2" })
        controller.updateSymbol("002594")
        controller.loadCapability()
        controller.updateSide(PaperManualOrderSide.SELL)
        controller.updateQuantity("100")

        val executed = controller.submit()

        assertFalse(executed)
        assertEquals(capability, controller.state.value.capability)
        assertEquals(null, controller.state.value.successMessage)
        assertEquals(
            "A 股当日买入数量受 T+1 限制，当前不可卖出。",
            controller.state.value.errorMessage,
        )
    }

    @Test
    fun useMaximumCopiesServerMaximumWithoutRecalculatingIt() = runBlocking {
        val gateway = FakeGateway(
            capabilityResults = mutableListOf(PaperManualOrderLoadResult.Success(cnCapability())),
        )
        val controller = PaperManualOrderController(gateway)
        controller.updateSymbol("002594")
        controller.loadCapability()

        controller.useServerMaximum()
        assertEquals("800", controller.state.value.quantityText)

        controller.updateSide(PaperManualOrderSide.SELL)
        controller.useServerMaximum()
        assertEquals("100", controller.state.value.quantityText)
    }

    private fun cnCapability() = PaperManualOrderCapabilityDto(
        symbol = "002594",
        market = "CN",
        currency = "CNY",
        executable = true,
        lot_size = 100,
        market_open = true,
        quote_price = 87.92,
        quote_observed_at = "2026-08-31T14:58:00+08:00",
        available_cash = 76321.4,
        held_quantity = 100.0,
        sellable_quantity = 100.0,
        locked_quantity = 0.0,
        max_buy_quantity = 800.0,
        max_sell_quantity = 100.0,
    )
}

private class FakeGateway(
    private val capabilityResults: MutableList<PaperManualOrderLoadResult> = mutableListOf(),
    private val submitResults: MutableList<PaperManualOrderSubmitResult> = mutableListOf(),
) : PaperManualOrderGateway {
    val submitted = mutableListOf<PaperManualOrderInputDto>()

    override suspend fun capability(symbol: String): PaperManualOrderLoadResult {
        check(capabilityResults.isNotEmpty()) { "no capability result left for $symbol" }
        return capabilityResults.removeAt(0)
    }

    override suspend fun submit(input: PaperManualOrderInputDto): PaperManualOrderSubmitResult {
        submitted += input
        check(submitResults.isNotEmpty()) { "no submit result left for ${input.symbol}" }
        return submitResults.removeAt(0)
    }
}
