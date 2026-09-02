package com.thirdhand.app.paperruntime

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PaperRuntimeControllerTest {
    @Test
    fun loadPublishesHumanReadableServerRuntimeState() = runBlocking {
        val runtime = runtimeState(
            status = "monitoring",
            headline = "空仓找机会",
            reason = "当前没有待执行 BUY/SELL；HOLD / WAIT / BLOCKED 不会形成成交任务。",
        )
        val gateway = FakePaperRuntimeGateway(
            loadResults = mutableListOf(PaperRuntimeLoadResult.Success(runtime)),
        )
        val controller = PaperRuntimeController(gateway)

        controller.load()

        val state = controller.state.value
        assertEquals(runtime, state.runtime)
        assertEquals("空仓找机会", state.runtime?.mode_label)
        assertEquals(0, state.runtime?.pending_execution_count)
        assertTrue(state.runtime?.no_trade_reason?.contains("HOLD / WAIT / BLOCKED") == true)
        assertEquals(null, state.errorMessage)
    }

    @Test
    fun restartSendsOnlyUserSelectedInitialCashThenReloadsAuthority() = runBlocking {
        val before = runtimeState(
            status = "monitoring",
            headline = "持仓优先",
            sequence = 1,
        )
        val after = runtimeState(
            status = "monitoring",
            headline = "空仓找机会",
            sequence = 2,
            initialCash = 50_000.0,
        )
        val restart = PaperSimulationRestartResponseDto(
            status = "restarted",
            archived_epoch_id = "paper-epoch-1",
            epoch = after.epoch,
        )
        val gateway = FakePaperRuntimeGateway(
            loadResults = mutableListOf(
                PaperRuntimeLoadResult.Success(before),
                PaperRuntimeLoadResult.Success(after),
            ),
            restartResults = mutableListOf(PaperRestartResult.Success(restart)),
        )
        val controller = PaperRuntimeController(gateway, restartIdProvider = { "restart-1" })
        controller.load()
        controller.openRestartDialog(defaultInitialCash = 50_000.0)

        val restarted = controller.restart()

        assertTrue(restarted)
        assertEquals(1, gateway.restarts.size)
        assertEquals("android-restart-restart-1", gateway.restarts.single().client_restart_id)
        assertEquals(50_000.0, gateway.restarts.single().initial_cash, 0.0)
        assertEquals(2, controller.state.value.runtime?.epoch?.sequence)
        assertEquals("空仓找机会", controller.state.value.runtime?.mode_label)
        assertFalse(controller.state.value.restartDialogVisible)
        assertTrue(controller.state.value.successMessage?.contains("第 2 轮模拟已开始") == true)
    }

    @Test
    fun ambiguousFailureRetriesTheSameRestartRequestId() = runBlocking {
        val after = runtimeState(
            status = "monitoring",
            headline = "空仓找机会",
            sequence = 2,
            initialCash = 50_000.0,
        )
        val gateway = FakePaperRuntimeGateway(
            loadResults = mutableListOf(PaperRuntimeLoadResult.Success(after)),
            restartResults = mutableListOf(
                PaperRestartResult.Failure("网络响应丢失"),
                PaperRestartResult.Success(
                    PaperSimulationRestartResponseDto(
                        status = "restarted",
                        idempotent_replay = true,
                        epoch = after.epoch,
                    ),
                ),
            ),
        )
        var idCalls = 0
        val controller = PaperRuntimeController(
            gateway,
            restartIdProvider = {
                idCalls += 1
                "retry-id-$idCalls"
            },
        )
        controller.openRestartDialog(defaultInitialCash = 50_000.0)

        assertFalse(controller.restart())
        assertTrue(controller.restart())

        assertEquals(2, gateway.restarts.size)
        assertEquals(gateway.restarts[0].client_restart_id, gateway.restarts[1].client_restart_id)
        assertEquals("android-restart-retry-id-1", gateway.restarts[0].client_restart_id)
        assertEquals(1, idCalls)
    }

    @Test
    fun editingInitialCashAfterFailureCreatesANewRestartRequestId() = runBlocking {
        val gateway = FakePaperRuntimeGateway(
            restartResults = mutableListOf(
                PaperRestartResult.Failure("网络响应丢失"),
                PaperRestartResult.Failure("仍然失败"),
            ),
        )
        var idCalls = 0
        val controller = PaperRuntimeController(
            gateway,
            restartIdProvider = {
                idCalls += 1
                "change-id-$idCalls"
            },
        )
        controller.openRestartDialog(defaultInitialCash = 50_000.0)

        assertFalse(controller.restart())
        controller.updateInitialCash("60000")
        assertFalse(controller.restart())

        assertEquals("android-restart-change-id-1", gateway.restarts[0].client_restart_id)
        assertEquals("android-restart-change-id-2", gateway.restarts[1].client_restart_id)
        assertEquals(50_000.0, gateway.restarts[0].initial_cash, 0.0)
        assertEquals(60_000.0, gateway.restarts[1].initial_cash, 0.0)
    }

    @Test
    fun invalidInitialCashCannotMutateServer() = runBlocking {
        val gateway = FakePaperRuntimeGateway()
        val controller = PaperRuntimeController(gateway)
        controller.openRestartDialog(defaultInitialCash = 100_000.0)
        controller.updateInitialCash("0")

        val restarted = controller.restart()

        assertFalse(restarted)
        assertTrue(gateway.restarts.isEmpty())
        assertEquals("请输入大于 0 的模拟初始资金。", controller.state.value.errorMessage)
    }

    @Test
    fun restartFailureKeepsDialogOpenAndDoesNotClaimSuccess() = runBlocking {
        val gateway = FakePaperRuntimeGateway(
            restartResults = mutableListOf(
                PaperRestartResult.Failure(
                    message = "重新开始模拟失败，请刷新后重试。",
                    reasonCode = "paper_simulation_epoch_missing",
                ),
            ),
        )
        val controller = PaperRuntimeController(gateway, restartIdProvider = { "restart-2" })
        controller.openRestartDialog(defaultInitialCash = 100_000.0)

        val restarted = controller.restart()

        assertFalse(restarted)
        assertTrue(controller.state.value.restartDialogVisible)
        assertEquals(null, controller.state.value.successMessage)
        assertEquals("重新开始模拟失败，请刷新后重试。", controller.state.value.errorMessage)
    }

    private fun runtimeState(
        status: String,
        headline: String,
        reason: String = "本轮没有新的 BUY/SELL。",
        sequence: Int = 1,
        initialCash: Double = 100_000.0,
    ) = PaperRuntimeStateDto(
        epoch = PaperSimulationEpochDto(
            epoch_id = "paper-epoch-$sequence",
            sequence = sequence,
            status = "active",
            started_at = "2026-09-02T09:30:00+08:00",
            initial_cash = initialCash,
        ),
        runtime_status = status,
        headline = headline,
        mode = "DISCOVERY",
        mode_label = headline,
        auto_execution_enabled = true,
        running = false,
        no_trade_reason = reason,
        pending_execution_count = 0,
        due_review_count = 0,
        seconds_until_review = 240,
        seconds_until_candidate_scan = 540,
        candidate_scan_enabled = true,
        generated_at = "2026-09-02T11:16:30+08:00",
    )
}

private class FakePaperRuntimeGateway(
    private val loadResults: MutableList<PaperRuntimeLoadResult> = mutableListOf(),
    private val restartResults: MutableList<PaperRestartResult> = mutableListOf(),
) : PaperRuntimeGateway {
    val restarts = mutableListOf<PaperSimulationRestartInputDto>()

    override suspend fun runtimeState(): PaperRuntimeLoadResult {
        check(loadResults.isNotEmpty()) { "no runtime-state result left" }
        return loadResults.removeAt(0)
    }

    override suspend fun restart(input: PaperSimulationRestartInputDto): PaperRestartResult {
        restarts += input
        check(restartResults.isNotEmpty()) { "no restart result left" }
        return restartResults.removeAt(0)
    }
}
