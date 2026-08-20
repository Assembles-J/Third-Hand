package com.thirdhand.app

/**
 * Small migration adapter for paper-position navigation.
 *
 * Paper positions expose their last ledger update as `updated_at`, while the
 * shared ResearchTarget contract calls the same navigation timestamp
 * `last_activity_at`. The paper screen historically used an `added_at`-shaped
 * named argument, so this adapter keeps that call site isolated until the wider
 * MainActivity/ResearchTarget navigation model is extracted under N9.
 *
 * This function does not infer market or trading state; it only maps the
 * timestamp field name onto the canonical ResearchTargetDto constructor.
 */
@Suppress("FunctionName", "UNUSED_PARAMETER")
internal fun ResearchTargetDto(
    symbol: String,
    name: String,
    status: String,
    added_at: String,
    namedArgumentCompatibility: Unit = Unit,
): ResearchTargetDto = ResearchTargetDto(
    symbol = symbol,
    name = name,
    status = status,
    last_activity_at = added_at,
)
