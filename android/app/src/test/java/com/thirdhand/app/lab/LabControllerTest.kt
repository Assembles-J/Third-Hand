package com.thirdhand.app.lab

import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LabControllerTest {
    @Test
    fun initialLoadPublishesReadyState() = runBlocking {
        val dashboard = sampleLabDashboard()
        val controller = LabController(FakeLabRepository(mutableListOf(LabLoadResult.Success(dashboard))))

        controller.load()

        val state = controller.state.value as LabUiState.Ready
        assertEquals(dashboard, state.dashboard)
        assertFalse(state.refreshing)
        assertEquals(null, state.refreshError)
    }

    @Test
    fun refreshFailureKeepsLastGoodEvaluationVisible() = runBlocking {
        val dashboard = sampleLabDashboard()
        val controller = LabController(
            FakeLabRepository(
                mutableListOf(
                    LabLoadResult.Success(dashboard),
                    LabLoadResult.Failure("temporary network failure"),
                ),
            ),
        )

        controller.load()
        controller.refresh()

        val state = controller.state.value as LabUiState.Ready
        assertEquals(dashboard, state.dashboard)
        assertFalse(state.refreshing)
        assertEquals("temporary network failure", state.refreshError)
    }

    @Test
    fun initialEmptyIsExplicit() = runBlocking {
        val controller = LabController(FakeLabRepository(mutableListOf(LabLoadResult.Empty)))
        controller.load()
        assertTrue(controller.state.value is LabUiState.Empty)
    }

    @Test
    fun initialFailurePreservesRecoverability() = runBlocking {
        val controller = LabController(FakeLabRepository(mutableListOf(LabLoadResult.Failure("bad config", recoverable = false))))
        controller.load()
        val state = controller.state.value as LabUiState.Error
        assertEquals("bad config", state.message)
        assertFalse(state.recoverable)
    }
}

private class FakeLabRepository(private val results: MutableList<LabLoadResult>) : LabRepository {
    override suspend fun latestFormalSwingV1(): LabLoadResult {
        check(results.isNotEmpty()) { "no fake Lab result left" }
        return results.removeAt(0)
    }
}

internal fun sampleLabDashboard(
    sampleQuality: String = "USABLE",
    strategyAvailable: Boolean = true,
    benchmarkAvailable: Boolean = true,
): LabDashboardData {
    val experiment = LabExperimentItemDto(
        experiment_id = "formal-swing-v1-forward",
        experiment_version = "1.0.0",
        experiment_type = "FORMAL_OBSERVATION",
        status = "ACTIVE",
        strategy_id = "SWING_V1",
        strategy_version = "1.0.0",
        started_at = "2026-08-01T09:30:00+08:00",
        created_at = "2026-08-01T09:30:00+08:00",
        universe_snapshot_id = "universe-1",
        universe_snapshot_hash = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        universe_policy_version = "1.0.0",
        outcome_policy_version = "1.0.0",
        benchmark_policy_version = "1.0.0",
        sample_quality_policy_version = "1.0.0",
        evaluation_policy_version = "1.0.0",
    )
    val summary = LabSummaryResponseDto(
        experiment = experiment,
        outcome_counts = LabOutcomeCountsDto(
            decision_terminal_count = 42,
            decision_resolved_count = 38,
            decision_insufficient_count = 3,
            decision_invalid_count = 1,
            pending_decision_count = null,
            pending_count_reason = "pending_outcomes_are_derived_not_materialized_n3_6",
        ),
        strategy = LabStrategySummaryDto(available = strategyAvailable, sample_quality = sampleQuality),
        benchmark = LabBenchmarkSummaryDto(available = benchmarkAvailable, benchmark_type = "MARKET_INDEX"),
    )
    val strategy = LabStrategyPerformanceDto(
        available = strategyAvailable,
        sample_quality = sampleQuality,
        resolved_decision_count = 38,
        completed_trade_count = 14,
        distinct_symbol_count = 9,
        win_rate = if (strategyAvailable) 0.57 else null,
        payoff_ratio = if (strategyAvailable) 1.42 else null,
        expectancy = if (strategyAvailable) 0.012 else null,
        profit_factor = if (strategyAvailable) 1.35 else null,
        average_holding_sessions = if (strategyAvailable) 7.5 else null,
        average_episode_net_return = if (strategyAvailable) 0.018 else null,
        total_fees = if (strategyAvailable) 128.4 else null,
        max_consecutive_losses = if (strategyAvailable) 3 else null,
        reason_codes = if (strategyAvailable) listOf("experiment_equity_curve_unavailable_n3_4") else listOf("strategy_evaluation_not_materialized"),
    )
    val benchmark = LabBenchmarkPerformanceDto(
        available = benchmarkAvailable,
        benchmark_type = "MARKET_INDEX",
        resolved_observation_count = 38,
        mean_strategy_forward_return = if (benchmarkAvailable) 0.026 else null,
        mean_benchmark_forward_return = if (benchmarkAvailable) 0.014 else null,
        mean_excess_forward_return = if (benchmarkAvailable) 0.012 else null,
        reason_codes = if (benchmarkAvailable) listOf("experiment_and_benchmark_equity_curves_unavailable_n3_5") else listOf("benchmark_evaluation_not_materialized"),
    )
    val performance = LabPerformanceResponseDto(experiment, strategy, benchmark)
    val breakdown = LabBreakdownResponseDto(
        experiment = experiment,
        action_breakdown = listOf(
            LabDecisionBreakdownItemDto(action = "BUY", horizon_sessions = 10, sample_count = 12, favorable_count = 7, unfavorable_count = 3, mixed_count = 1, neutral_count = 1, mean_forward_return = 0.031, mean_mfe = 0.052, mean_mae = -0.018),
            LabDecisionBreakdownItemDto(action = "WAIT", horizon_sessions = 10, sample_count = 8, favorable_count = 4, unfavorable_count = 2, mixed_count = 1, neutral_count = 1, mean_forward_return = 0.006, mean_mfe = 0.027, mean_mae = -0.022),
        ),
        regime_breakdown = listOf(
            LabDecisionBreakdownItemDto(market_regime = "RISK_ON", horizon_sessions = 10, sample_count = 16, favorable_count = 10, unfavorable_count = 4, mixed_count = 1, neutral_count = 1, mean_forward_return = 0.029, mean_mfe = 0.049, mean_mae = -0.017),
        ),
        execution_attribution = listOf(
            LabExecutionBreakdownItemDto("EXECUTED", count = 14, resolved_count = 14),
            LabExecutionBreakdownItemDto("DEFERRED", count = 2, resolved_count = 2),
        ),
        benchmark_horizon_breakdown = listOf(
            LabBenchmarkHorizonItemDto("CN", 3, 38, 0, 0.011, 0.008, 0.003),
            LabBenchmarkHorizonItemDto("CN", 10, 38, 0, 0.026, 0.014, 0.012),
        ),
    )
    return LabDashboardData(experiment, summary, performance, breakdown)
}
