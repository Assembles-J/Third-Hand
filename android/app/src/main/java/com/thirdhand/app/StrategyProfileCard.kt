package com.thirdhand.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.util.Locale

/**
 * Read-only strategy identity for a frozen decision report.
 *
 * This component never infers trading authority from prose. Strategy identity,
 * timeframe roles and timeframe states come from structured backend fields.
 */
@Composable
fun StrategyProfileCard(
    report: DecisionReportDto?,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Text("策略与周期权限", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)

        if (report == null) {
            Text(
                "等待已保存的决策报告；生成后才能确认这次判断属于哪套策略。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            return@Column
        }

        val strategy = report.strategy
        if (strategy == null || strategy.strategy_id.isBlank()) {
            Text(
                "这是一份旧版决策报告，尚未记录 StrategyProfile。重新生成决策后可查看策略与周期权限。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            return@Column
        }

        Text(
            "${strategy.strategy_id} · v${strategy.strategy_version} · ${strategy.name.ifBlank { "Strategy" }}",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            "当前 ${strategyActionLabel(report.action)} 由这套策略产生 · 计划周期 ${strategy.holding_horizon}",
            style = MaterialTheme.typography.bodySmall,
        )

        val timeframe = report.timeframe_authority
        if (timeframe == null) {
            Text(
                "策略身份已记录，但该历史报告没有 TimeframeAuthority 快照。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        } else {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            StrategyTimeframeRow("周线", "weekly", strategy, timeframe.weekly_state, timeframe)
            StrategyTimeframeRow("日线", "daily", strategy, timeframe.daily_state, timeframe)
            StrategyTimeframeRow("60m", "60m", strategy, timeframe.state_60m, timeframe)
            StrategyTimeframeRow("15m", "15m", strategy, timeframe.state_15m, timeframe)
            StrategyTimeframeRow("5m", "5m", strategy, timeframe.state_5m, timeframe)

            if (timeframe.confirmation_state != "NOT_APPLIED" || timeframe.conflict_state != "NONE") {
                Text(
                    "多周期确认 ${strategyStateLabel(timeframe.confirmation_state)} · 冲突 ${strategyStateLabel(timeframe.conflict_state)}",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            if (timeframe.reason_codes.isNotEmpty()) {
                Text(
                    "规则原因：${timeframe.reason_codes.joinToString("、")}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        val actionPolicy = strategy.policy_versions["action_policy"]
        val timeframePolicy = strategy.policy_versions["timeframe_authority"]
        if (!actionPolicy.isNullOrBlank() || !timeframePolicy.isNullOrBlank()) {
            Text(
                "策略版本链：Action ${actionPolicy ?: "—"} · Timeframe ${timeframePolicy ?: "—"}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun StrategyTimeframeRow(
    label: String,
    key: String,
    strategy: StrategyProfileDto,
    rawState: String,
    timeframe: TimeframeAuthorityDto,
) {
    val unavailable = key in timeframe.unavailable_timeframes
    val role = strategy.authority_matrix[key]?.let(::strategyRoleLabel) ?: "仅记录"
    val state = if (unavailable) "不可用" else strategyStateLabel(rawState)

    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(label, modifier = Modifier.weight(0.55f), style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
        Text(role, modifier = Modifier.weight(1.25f), style = MaterialTheme.typography.bodySmall)
        Text(
            state,
            modifier = Modifier.weight(0.8f),
            style = MaterialTheme.typography.bodySmall,
            fontWeight = if (unavailable || rawState == "UNKNOWN" || rawState == "MISSING") FontWeight.SemiBold else FontWeight.Normal,
            color = if (unavailable || rawState == "UNKNOWN" || rawState == "MISSING") MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
        )
    }
}

private fun strategyRoleLabel(value: String): String = when (value.lowercase(Locale.ROOT)) {
    "strategic_structure" -> "战略结构"
    "setup_position_management" -> "Setup / 持仓管理"
    "execution_timing" -> "执行 Timing"
    "hard_risk_execution" -> "硬风险 / 执行"
    "quality_risk_context" -> "质量 / 风险背景"
    "quality_currentness" -> "质量 / 时效性"
    "deterministic_risk_gate" -> "确定性风险 Gate"
    "strategic_context" -> "战略环境"
    "research_context" -> "研究背景"
    "timing_evidence_only" -> "仅 Timing 证据"
    "research_explanation_only" -> "仅研究 / 解释"
    else -> value
}

private fun strategyStateLabel(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "UP", "BULLISH", "CONFIRMED" -> "向上 / 已确认"
    "DOWN", "BEARISH" -> "向下"
    "FLAT", "MIXED", "NEUTRAL" -> "震荡 / 中性"
    "AVAILABLE" -> "可用"
    "MISSING" -> "缺失"
    "UNKNOWN" -> "未知"
    "NONE" -> "无"
    "NOT_APPLIED" -> "未应用"
    "CONFLICT" -> "有冲突"
    else -> value.ifBlank { "未知" }
}

private fun strategyActionLabel(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "OPEN", "BUY" -> "买入候选"
    "ADD" -> "加仓"
    "HOLD" -> "持有"
    "REDUCE" -> "减仓"
    "EXIT", "SELL" -> "退出"
    "WATCH", "WAIT" -> "观察"
    "BLOCKED" -> "阻断"
    else -> value
}
