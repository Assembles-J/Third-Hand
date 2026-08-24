package com.thirdhand.app.lab

internal fun labScreenshotDashboard(
    sampleQuality: String = "USABLE",
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
        experiment,
        LabOutcomeCountsDto(42, 38, 3, 1, pending_count_reason = "pending_outcomes_are_derived_not_materialized_n3_6"),
        LabStrategySummaryDto(true, sample_quality = sampleQuality),
        LabBenchmarkSummaryDto(benchmarkAvailable, benchmark_type = "MARKET_INDEX"),
    )
    val performance = LabPerformanceResponseDto(
        experiment,
        LabStrategyPerformanceDto(
            available = true,
            sample_quality = sampleQuality,
            resolved_decision_count = 38,
            completed_trade_count = 14,
            distinct_symbol_count = 9,
            win_rate = 0.57,
            payoff_ratio = 1.42,
            expectancy = 0.012,
            profit_factor = 1.35,
            average_holding_sessions = 7.5,
            average_episode_net_return = 0.018,
            total_fees = 128.4,
            max_consecutive_losses = 3,
            reason_codes = listOf("experiment_equity_curve_unavailable_n3_4"),
        ),
        LabBenchmarkPerformanceDto(
            available = benchmarkAvailable,
            benchmark_type = if (benchmarkAvailable) "MARKET_INDEX" else null,
            mean_strategy_forward_return = if (benchmarkAvailable) 0.026 else null,
            mean_benchmark_forward_return = if (benchmarkAvailable) 0.014 else null,
            mean_excess_forward_return = if (benchmarkAvailable) 0.012 else null,
            reason_codes = if (benchmarkAvailable) listOf("experiment_and_benchmark_equity_curves_unavailable_n3_5") else listOf("benchmark_evaluation_not_materialized"),
        ),
    )
    val breakdown = LabBreakdownResponseDto(
        experiment = experiment,
        action_breakdown = listOf(LabDecisionBreakdownItemDto(action = "BUY", horizon_sessions = 10, sample_count = 12, favorable_count = 7, unfavorable_count = 3, mixed_count = 1, neutral_count = 1, mean_forward_return = 0.031, mean_mfe = 0.052, mean_mae = -0.018)),
        regime_breakdown = listOf(LabDecisionBreakdownItemDto(market_regime = "RISK_ON", horizon_sessions = 10, sample_count = 16, favorable_count = 10, unfavorable_count = 4, mixed_count = 1, neutral_count = 1, mean_forward_return = 0.029, mean_mfe = 0.049, mean_mae = -0.017)),
        execution_attribution = listOf(LabExecutionBreakdownItemDto("EXECUTED", 14, 14, 0)),
        benchmark_horizon_breakdown = if (benchmarkAvailable) listOf(LabBenchmarkHorizonItemDto("CN", 10, 38, 0, 0.026, 0.014, 0.012)) else emptyList(),
    )
    return LabDashboardData(experiment, summary, performance, breakdown)
}
