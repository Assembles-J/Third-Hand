package com.thirdhand.app

import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.android.tools.screenshot.PreviewTest

private const val WORKSPACE_PREVIEW_WIDTH = 420
private const val WORKSPACE_PREVIEW_HEIGHT = 600

@PreviewTest
@Preview(
    name = "Decision Workspace - ready",
    showBackground = true,
    widthDp = WORKSPACE_PREVIEW_WIDTH,
    heightDp = WORKSPACE_PREVIEW_HEIGHT,
)
@Composable
fun DecisionWorkspaceReadyScreenshotTest() {
    DecisionWorkspaceScreenshotFrame(
        DecisionWorkspaceUiState.Ready(
            workspace = readyWorkspace(),
        ),
    )
}

@PreviewTest
@Preview(
    name = "Decision Workspace - partial stale event coverage",
    showBackground = true,
    widthDp = WORKSPACE_PREVIEW_WIDTH,
    heightDp = WORKSPACE_PREVIEW_HEIGHT,
)
@Composable
fun DecisionWorkspacePartialScreenshotTest() {
    DecisionWorkspaceScreenshotFrame(
        DecisionWorkspaceUiState.Ready(
            workspace = readyWorkspace().copy(
                formal_action = "WAIT",
                summary = "事件覆盖不完整，维持观察并等待权威来源补齐。",
                corporate_events = DecisionWorkspaceCorporateEventsDto(
                    status = "partial",
                    retrieved_at = "2026-08-19T19:45:00+08:00",
                    official_source_status = "stale_fallback",
                    unavailable_dates = listOf("2026-08-20", "2026-08-21"),
                ),
            ),
        ),
    )
}

@PreviewTest
@Preview(
    name = "Decision Workspace - unavailable legacy sections",
    showBackground = true,
    widthDp = WORKSPACE_PREVIEW_WIDTH,
    heightDp = WORKSPACE_PREVIEW_HEIGHT,
)
@Composable
fun DecisionWorkspaceUnavailableScreenshotTest() {
    DecisionWorkspaceScreenshotFrame(
        DecisionWorkspaceUiState.Ready(
            workspace = readyWorkspace().copy(
                summary = "旧版决策仍可读取，但财报当前性与事件生命周期缺少结构化快照。",
                financial_currentness = null,
                corporate_events = DecisionWorkspaceCorporateEventsDto(status = "unavailable"),
                data_quality = DecisionWorkspaceQualityDto(
                    status = "partial",
                    score_percent = 72,
                    missing_fields = listOf("financial_currentness", "corporate_events"),
                ),
            ),
        ),
    )
}

@PreviewTest
@Preview(
    name = "Decision Workspace - T+1 deferred exit",
    showBackground = true,
    widthDp = WORKSPACE_PREVIEW_WIDTH,
    heightDp = WORKSPACE_PREVIEW_HEIGHT,
)
@Composable
fun DecisionWorkspaceT1DeferredScreenshotTest() {
    DecisionWorkspaceScreenshotFrame(
        DecisionWorkspaceUiState.Ready(
            workspace = readyWorkspace().copy(
                formal_action = "EXIT",
                summary = "正式动作要求退出，但部分仓位仍受 A 股 T+1 约束。",
                what_changed = DecisionWorkspaceWhatChangedDto(
                    prior_action = "HOLD",
                    current_action = "EXIT",
                    input_changed = true,
                    material_change = true,
                    material_change_reason = "hard_gate_changed",
                    material_change_components = listOf("action_gates", "position_state"),
                    position_age = 1,
                    review_after = "2026-08-20T09:30:00+08:00",
                ),
                paper_risk = DecisionWorkspacePaperRiskDto(
                    position_present = true,
                    quantity = 1000.0,
                    sellable_quantity = 600.0,
                    locked_quantity = 400.0,
                    next_eligible_sell_at = "2026-08-20T09:30:00+08:00",
                    active_deferrals = listOf(
                        DecisionWorkspaceDeferralDto(
                            decision_id = "decision-t1",
                            action = "EXIT",
                            reason_code = "paper_t1_unsellable_quantity",
                            next_eligible_at = "2026-08-20T09:30:00+08:00",
                            state = "active",
                        ),
                    ),
                ),
            ),
        ),
    )
}

@PreviewTest
@Preview(
    name = "Decision Workspace - refresh error keeps last good",
    showBackground = true,
    widthDp = WORKSPACE_PREVIEW_WIDTH,
    heightDp = WORKSPACE_PREVIEW_HEIGHT,
)
@Composable
fun DecisionWorkspaceRefreshErrorScreenshotTest() {
    DecisionWorkspaceScreenshotFrame(
        DecisionWorkspaceUiState.Ready(
            workspace = readyWorkspace(),
            refreshError = "行情服务暂时不可用；本页保留上次成功读取的正式决策。",
        ),
    )
}

@Composable
private fun DecisionWorkspaceScreenshotFrame(state: DecisionWorkspaceUiState) {
    ThirdHandTheme(ThemeMode.LIGHT) {
        DecisionWorkspaceContent(
            state = state,
            onRefresh = {},
            modifier = Modifier.padding(16.dp),
        )
    }
}

private fun readyWorkspace(): DecisionWorkspaceDto = DecisionWorkspaceDto(
    symbol = "600000",
    name = "浦发银行",
    decision_id = "decision-ready",
    generated_at = "2026-08-19T19:50:00+08:00",
    formal_action = "HOLD",
    summary = "日线结构仍有效，暂无足够重要的新变化。",
    what_changed = DecisionWorkspaceWhatChangedDto(
        prior_decision_id = "decision-prior",
        prior_action = "HOLD",
        current_action = "HOLD",
        input_changed = true,
        material_change = false,
        material_change_reason = "continuity_preserved_prior_action",
        position_age = 4,
        review_after = "2026-08-20T10:00:00+08:00",
        invalidation_conditions = listOf("close below support"),
        continuity_policy_version = "decision-continuity-v2",
    ),
    financial_currentness = DecisionWorkspaceFinancialCurrentnessDto(
        policy_version = "financial-currentness-v1",
        latest_observed_period = "2026-06-30",
        expected_report_at = "2026-10-30",
        latest_period_status = "CURRENT",
        current_confirmation = "CONFIRMED",
        reason_codes = listOf("verified_report_available_for_event:2026-08-18"),
    ),
    corporate_events = DecisionWorkspaceCorporateEventsDto(
        status = "ready",
        retrieved_at = "2026-08-19T19:45:00+08:00",
        official_source_status = "ready",
        active_events = listOf(
            DecisionWorkspaceCorporateEventDto(
                event_id = "event-q3",
                title = "三季度报告",
                event_type = "earnings_report",
                scheduled_at = "2026-10-30",
                period = "2026 Q3",
                lifecycle_status = "SCHEDULED",
                verification_level = "official",
                source = "exchange",
                source_rank = 10,
                conflict_status = "NONE",
                policy_eligible = true,
            ),
        ),
        decision_evidence = listOf(
            DecisionWorkspaceEventEvidenceDto(
                evidence_id = "event-q3",
                metric = "event.upcoming.earnings_report.event-q3",
                scheduled_at = "2026-10-30",
                source_name = "exchange",
                freshness_status = "fresh",
                polarity = "NEUTRAL_MATERIAL",
                confidence = 0.95,
            ),
        ),
    ),
    paper_risk = DecisionWorkspacePaperRiskDto(
        position_present = true,
        quantity = 1000.0,
        sellable_quantity = 1000.0,
        locked_quantity = 0.0,
    ),
    data_quality = DecisionWorkspaceQualityDto(
        status = "ready",
        score_percent = 100,
    ),
)
