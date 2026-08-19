package com.thirdhand.app

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

/**
 * Route-level container for the Decision Workspace summary.
 * Network access and mutable loading/error transitions live outside the pure content composable.
 */
@Composable
fun DecisionWorkspaceSummaryPanel(
    symbol: String,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val controller = remember(context) {
        DecisionWorkspaceController(NetworkDecisionWorkspaceRepository(context.applicationContext))
    }
    val state by controller.state.collectAsState()
    val scope = rememberCoroutineScope()

    LaunchedEffect(symbol) {
        controller.load(symbol)
    }

    DecisionWorkspaceContent(
        state = state,
        modifier = modifier,
        onRefresh = { scope.launch { controller.refresh(symbol) } },
    )
}

/**
 * Stateless renderer for Decision Workspace route state.
 * It is intentionally internal so screenshot/preview fixtures can render state without network I/O.
 */
@Composable
internal fun DecisionWorkspaceContent(
    state: DecisionWorkspaceUiState,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val refreshing = state is DecisionWorkspaceUiState.Ready && state.refreshing
    val busy = state is DecisionWorkspaceUiState.Loading || refreshing
    val refreshEnabled = !busy && (state !is DecisionWorkspaceUiState.Error || state.recoverable)

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("正式决策 · 发生了什么变化", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Text("只读 DecisionMemory / Atomic Evidence / Paper Ledger", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                TextButton(onClick = onRefresh, enabled = refreshEnabled) {
                    if (busy) CircularProgressIndicator(Modifier.width(15.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, contentDescription = "刷新决策变化")
                    Spacer(Modifier.width(4.dp))
                    Text(if (refreshing) "刷新中" else "刷新")
                }
            }

            when (state) {
                DecisionWorkspaceUiState.Loading -> Text(
                    "正在读取最新正式决策与连续性记录…",
                    style = MaterialTheme.typography.bodySmall,
                )
                is DecisionWorkspaceUiState.Empty -> Text(
                    state.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                is DecisionWorkspaceUiState.Error -> Text(
                    "工作区暂不可用：${state.message}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
                is DecisionWorkspaceUiState.Ready -> {
                    DecisionWorkspaceSummaryBody(state.workspace)
                    state.refreshError?.let {
                        Text(
                            "刷新失败，继续显示上次可用结果：$it",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.error,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DecisionWorkspaceSummaryBody(workspace: DecisionWorkspaceDto) {
    val change = workspace.what_changed
    val risk = workspace.paper_risk
    val quality = workspace.data_quality

    Text(
        "${workspaceActionLabel(workspace.formal_action)} · ${workspace.summary.ifBlank { "暂无摘要" }}",
        style = MaterialTheme.typography.bodyMedium,
        fontWeight = FontWeight.SemiBold,
    )

    if (change.material_change) {
        val before = workspaceActionLabel(change.prior_action)
        val after = workspaceActionLabel(change.current_action)
        Text(
            "有实质变化：$before → $after",
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.SemiBold,
            color = MaterialTheme.colorScheme.primary,
        )
        if (change.material_change_components.isNotEmpty()) {
            Text(
                "变化来源：${change.material_change_components.joinToString("、") { workspaceChangeComponentLabel(it) }}",
                style = MaterialTheme.typography.labelSmall,
            )
        }
    } else {
        Text(
            "没有足够重要的新变化；DecisionContinuity 继续维持 ${workspaceActionLabel(change.current_action)}。",
            style = MaterialTheme.typography.bodySmall,
        )
    }

    Text(
        "连续性原因：${workspaceContinuityReason(change.material_change_reason)}${change.position_age?.let { " · 持仓 $it 天" }.orEmpty()}",
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    change.review_after?.let {
        Text("下次计划复核：${workspaceTimestamp(it)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
    change.cooldown_until?.let {
        Text("冷却期至：${workspaceTimestamp(it)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
    DecisionWorkspaceCompanyEventState(workspace.financial_currentness, workspace.corporate_events)

    if (risk.position_present) {
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        val locked = risk.locked_quantity ?: 0.0
        Text(
            "仓位 ${risk.quantity.workspaceQuantity()} 股 · 可卖 ${risk.sellable_quantity.workspaceQuantity()} · T+1锁定 ${risk.locked_quantity.workspaceQuantity()}",
            style = MaterialTheme.typography.bodySmall,
            fontWeight = if (locked > 0.0) FontWeight.SemiBold else FontWeight.Normal,
        )
        if (locked > 0.0) {
            Text(
                risk.next_eligible_sell_at?.let { "下次可卖/复核：${workspaceTimestamp(it)}" }
                    ?: "存在锁定仓位，但服务没有提供下次可卖时间。",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
    risk.active_deferrals.forEach { deferral ->
        Text(
            "等待执行：${workspaceActionLabel(deferral.action)} · ${workspaceDeferralReason(deferral.reason_code)}${deferral.next_eligible_at?.let { " · ${workspaceTimestamp(it)}" }.orEmpty()}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.SemiBold,
        )
    }

    if (quality.status != null && quality.status != "ready") {
        Text(
            "数据状态 ${quality.status}${quality.score_percent?.let { " · $it%" }.orEmpty()}${quality.missing_fields.takeIf { it.isNotEmpty() }?.let { " · 缺少 ${it.joinToString()}" }.orEmpty()}${quality.stale_fields.takeIf { it.isNotEmpty() }?.let { " · 过期 ${it.joinToString()}" }.orEmpty()}",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.error,
        )
    }
}

@Composable
private fun DecisionWorkspaceCompanyEventState(
    financial: DecisionWorkspaceFinancialCurrentnessDto?,
    events: DecisionWorkspaceCorporateEventsDto,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("财报当前性 / CorporateEvent", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
        Text(
            "财报状态来自生成本次决策时冻结的 Atomic Evidence；事件 lifecycle 是当前持久化快照，两者不会混成一个时间点。",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (financial == null) {
            Text("旧版决策没有 FinancialCurrentness 快照；不能把最近抓取的数据当作当前财报确认。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        } else {
            val conflicted = financial.current_confirmation == "CONFLICTED"
            Text(
                workspaceFinancialCurrentnessLabel(financial),
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = if (conflicted) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
            )
            Text(
                "最新观察期 ${financial.latest_observed_period ?: "未知"} · 预期披露 ${financial.expected_report_at ?: "无权威日历信号"}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (financial.reason_codes.isNotEmpty()) {
                Text(
                    "当前性原因：${financial.reason_codes.joinToString("、") { workspaceFinancialReason(it) }}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        val partial = events.status == "partial"
        if (partial) {
            Text(
                buildString {
                    append("CorporateEvent 数据仅部分可用；不能据此断言“没有事件”。")
                    if (events.unavailable_dates.isNotEmpty()) {
                        append(" 缺失日期：").append(events.unavailable_dates.joinToString("、"))
                    }
                    if (events.official_source_status == "stale_fallback") {
                        append(" 官方源当前使用旧快照回退。")
                    }
                },
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.error,
            )
        }

        when {
            events.status == "unavailable" -> Text(
                "当前 CorporateEvent lifecycle 未提供；不会把“没有数据”显示成“没有事件”。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            partial && events.active_events.isEmpty() -> Text(
                "当前未返回活动财报事件，但事件覆盖不完整，因此本状态只能视为未知/待补齐。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            events.active_events.isEmpty() -> {
                val latest = events.recent_history.firstOrNull()
                if (latest != null) {
                    Text(
                        "当前无活动财报事件；最近记录：${workspaceEventTitle(latest)} · ${workspaceEventLifecycle(latest.lifecycle_status)}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                } else {
                    Text("当前持久化事件快照没有活动财报事件。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            else -> events.active_events.take(2).forEach { event ->
                val conflict = event.conflict_status == "CONFLICTED"
                Text(
                    "${workspaceEventTitle(event)} · ${workspaceEventLifecycle(event.lifecycle_status)} · ${workspaceEventVerification(event.verification_level)}",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                    color = if (conflict) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
                )
                Text(
                    buildString {
                        append("计划/事件日 ").append(event.scheduled_at ?: "未知")
                        event.period?.takeIf { it.isNotBlank() }?.let { append(" · ").append(it) }
                        event.source?.takeIf { it.isNotBlank() }?.let { append(" · 来源 ").append(it) }
                        if (conflict) append(" · 日期冲突 ").append(event.conflict_dates.joinToString(" / "))
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = if (conflict) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        if (events.decision_evidence.isNotEmpty()) {
            val frozen = events.decision_evidence.first()
            Text(
                "本次 Formal Decision 冻结事件证据：${frozen.scheduled_at ?: "日期未知"} · ${frozen.source_name ?: "来源未知"} · ${workspaceEventEvidencePolarity(frozen.polarity)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
            )
        }
        events.retrieved_at?.let {
            Text(
                "当前事件快照 ${workspaceTimestamp(it)} · 官方源 ${workspaceEventSourceStatus(events.official_source_status)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

private fun workspaceFinancialCurrentnessLabel(value: DecisionWorkspaceFinancialCurrentnessDto): String = when {
    value.current_confirmation == "CONFIRMED" && value.latest_period_status == "CURRENT" -> "当前财报确认：已确认"
    value.current_confirmation == "PENDING" || value.latest_period_status == "PENDING_EXPECTED_REPORT" -> "当前财报确认：等待预期报告"
    value.current_confirmation == "CONFLICTED" -> "当前财报确认：来源冲突，不能视为已确认"
    value.latest_period_status == "STALE_RELATIVE_TO_EXPECTED_REPORT" -> "当前财报确认：现有报告落后于预期报告"
    value.latest_period_status == "HISTORICAL_VALID" -> "当前财报确认：仅历史数据有效，当前状态未知"
    else -> "当前财报确认：未知"
}

private fun workspaceFinancialReason(value: String): String = when {
    value.startsWith("earnings_report_pending:") -> "预期财报尚未完成确认（${value.substringAfter(':')}）"
    value.startsWith("verified_report_available_for_event:") -> "预期事件后的新报告已验证（${value.substringAfter(':')}）"
    value == "financial_source_conflict" -> "财务来源冲突"
    value == "no_authoritative_expected_report_signal" -> "没有权威预期披露信号"
    value == "financial_report_period_unknown" -> "财报期间未知"
    else -> value
}

private fun workspaceEventTitle(event: DecisionWorkspaceCorporateEventDto): String =
    event.title?.takeIf { it.isNotBlank() } ?: "财报事件"

private fun workspaceEventLifecycle(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "SCHEDULED" -> "已计划"
    "DUE" -> "今日到期"
    "RELEASE_EXPECTED" -> "等待披露"
    "RELEASED_UNVERIFIED" -> "已披露待验证"
    "VERIFIED" -> "已验证"
    "CANCELLED" -> "已取消"
    "SUPERSEDED" -> "已被新事件替代"
    null, "" -> "状态未知"
    else -> value
}

private fun workspaceEventVerification(value: String?): String = when (value) {
    "official" -> "官方证据"
    "secondary_calendar" -> "次级日历"
    else -> "来源等级未知"
}

private fun workspaceEventSourceStatus(value: String?): String = when (value) {
    "ready" -> "可用"
    "stale_fallback" -> "旧快照回退"
    "unavailable", null -> "不可用"
    else -> value
}

private fun workspaceEventEvidencePolarity(value: String?): String = when (value) {
    "NEUTRAL_MATERIAL" -> "方向中性但重要"
    "SUPPORTIVE" -> "支持"
    "ADVERSE" -> "不利"
    "CONFLICT" -> "冲突"
    "MISSING" -> "缺失"
    else -> "方向未知"
}

private fun workspaceActionLabel(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "BUY", "OPEN" -> "买入候选"
    "WAIT", "WATCH" -> "观察"
    "HOLD" -> "持有"
    "ADD" -> "加仓"
    "REDUCE" -> "减仓"
    "EXIT", "SELL" -> "退出"
    "BLOCKED" -> "阻断"
    null, "" -> "未知"
    else -> value
}

private fun workspaceChangeComponentLabel(value: String): String = when (value) {
    "action_gates" -> "硬门禁"
    "position_state" -> "持仓状态"
    "price_state" -> "失效价状态"
    "technical_state" -> "日线技术状态"
    "risk_level" -> "风险等级"
    "market_regime" -> "市场环境"
    "event_state" -> "公司事件"
    "research_veto_state" -> "研究反证"
    "timeframe_policy_state" -> "多周期状态"
    "position_quantity" -> "持仓数量"
    "plan_contract_hash" -> "交易计划"
    else -> value
}

private fun workspaceContinuityReason(value: String): String = when (value) {
    "initial_decision" -> "首次正式决策"
    "hard_gate_changed" -> "硬门禁发生变化"
    "position_state_changed" -> "持仓状态发生变化"
    "material_fingerprint_changed" -> "策略相关状态发生变化"
    "continuity_preserved_prior_action" -> "新输入不足以推翻上一正式动作"
    "no_material_change" -> "没有策略级实质变化"
    "legacy_prior_input_changed" -> "旧版历史记录没有完整指纹，本次按输入变化迁移"
    else -> value.ifBlank { "不可用" }
}

private fun workspaceDeferralReason(value: String?): String = when {
    value.isNullOrBlank() -> "等待重新评估"
    value.contains("paper_t1_unsellable_quantity") -> "A 股 T+1 锁定"
    value.contains("execution_quote") -> "等待合格成交报价"
    value.contains("cooldown") -> "冷却期未结束"
    else -> value
}

private fun workspaceTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse { value.replace('T', ' ').substringBefore("+").substringBefore("Z") }

private fun Double?.workspaceQuantity(): String = when {
    this == null -> "未提供"
    this % 1.0 == 0.0 -> toLong().toString()
    else -> "%.2f".format(Locale.US, this)
}
