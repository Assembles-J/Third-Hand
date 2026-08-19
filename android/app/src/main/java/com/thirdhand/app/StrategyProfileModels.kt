package com.thirdhand.app

/** Structured strategy identity returned by the decision report. */
data class StrategyProfileDto(
    val strategy_id: String = "",
    val strategy_version: String = "",
    val name: String = "",
    val holding_horizon: String = "",
    val strategic_timeframes: List<String> = emptyList(),
    val setup_timeframes: List<String> = emptyList(),
    val timing_timeframes: List<String> = emptyList(),
    val risk_timeframes: List<String> = emptyList(),
    val authority_matrix: Map<String, String> = emptyMap(),
    val policy_versions: Map<String, String> = emptyMap(),
)

/** Deterministic timeframe policy state; UNKNOWN/MISSING is not rendered as neutral. */
data class TimeframeAuthorityDto(
    val strategic_timeframes: List<String> = emptyList(),
    val position_management_timeframes: List<String> = emptyList(),
    val execution_timing_timeframes: List<String> = emptyList(),
    val hard_risk_timeframes: List<String> = emptyList(),
    val formal_technical_timeframe: String? = null,
    val available_timeframes: List<String> = emptyList(),
    val unavailable_timeframes: List<String> = emptyList(),
    val weekly_state: String = "UNKNOWN",
    val daily_state: String = "UNKNOWN",
    val state_60m: String = "UNKNOWN",
    val state_15m: String = "UNKNOWN",
    val state_5m: String = "UNKNOWN",
    val confirmation_state: String = "NOT_APPLIED",
    val conflict_state: String = "NONE",
    val reason_codes: List<String> = emptyList(),
    val policy_version: String = "",
)
