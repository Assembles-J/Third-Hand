package com.thirdhand.app

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.DenseRowDivider
import com.thirdhand.app.ui.components.DenseStateTag
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.launch
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale

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

@Composable
internal fun DecisionWorkspaceContent(
    state: DecisionWorkspaceUiState,
    onRefresh: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val refreshing = state is DecisionWorkspaceUiState.Ready && state.refreshing
    val busy = state is DecisionWorkspaceUiState.Loading || refreshing
    val refreshEnabled = !busy && (state !is DecisionWorkspaceUiState.Error || state.recoverable)

    Column(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = AppSpacing.touchTarget),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text("正式决策", style = CompactTypography.sectionTitle)
                Text(
                    "服务端决策、变化与风险事实",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(
                onClick = onRefresh,
                enabled = refreshEnabled,
                modifier = Modifier.size(AppSpacing.touchTarget),
            ) {
                if (busy) {
                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                } else {
                    Icon(
                        Icons.Filled.Refresh,
                        contentDescription = "刷新正式决策",
                        tint = MaterialTheme.colorScheme.primary,
                    )
                }
            }
        }
        DenseRowDivider(inset = false)

        when (state) {
            DecisionWorkspaceUiState.Loading -> {
                Box(
                    Modifier
                        .fillMaxWidth()
                        .padding(vertical = AppSpacing.xLarge),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                }
            }

            is DecisionWorkspaceUiState.Empty -> {
                DecisionWorkspaceMessage(
                    text = state.message,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            is DecisionWorkspaceUiState.Error -> {
                DecisionWorkspaceMessage(
                    text = state.message,
                    color = MaterialTheme.colorScheme.error,
                )
            }

            is DecisionWorkspaceUiState.Ready -> {
                state.refreshError?.let { message ->
                    DecisionWorkspaceMessage(
                        text = message,
                        color = MaterialTheme.colorScheme.error,
                    )
                    DenseRowDivider(inset = false)
                }
                DecisionWorkspaceSummaryBody(state.workspace)
            }
        }
    }
}

@Composable
private fun DecisionWorkspaceMessage(text: String, color: Color) {
    Text(
        text,
        modifier = Modifier.padding(vertical = AppSpacing.rowVertical),
        style = CompactTypography.secondary,
        color = color,
    )
}

@Composable
private fun DecisionWorkspaceSummaryBody(workspace: DecisionWorkspaceDto) {
    val change = workspace.what_changed
    val risk = workspace.paper_risk
    val colors = MaterialTheme.marketColors

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = AppSpacing.rowVertical),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            DenseStateTag(
                text = workspaceActionLabel(workspace.formal_action),
                color = workspaceActionColor(workspace.formal_action),
            )
            Spacer(Modifier.width(AppSpacing.small))
            Text(
                workspace.generated_at
                    ?.takeIf { it.isNotBlank() }
                    ?.let(::workspaceTimestamp)
                    ?: "时间未知",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            workspace.summary.ifBlank { "暂无决策摘要" },
            modifier = Modifier.padding(top = AppSpacing.small),
            style = CompactTypography.body,
            color = MaterialTheme.colorScheme.onSurface,
        )
    }

    DenseRowDivider(inset = false)

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = AppSpacing.rowVertical),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("变化与复核", style = CompactTypography.rowTitle)
            Spacer(Modifier.weight(1f))
            DenseStateTag(
                text = if (change.material_change) "重要变化" else "无重要变化",
                color = if (change.material_change) colors.warning else MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (change.material_change) {
            Row(
                modifier = Modifier.padding(top = AppSpacing.small),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    workspaceActionLabel(change.prior_action),
                    style = CompactTypography.secondary,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Icon(
                    Icons.AutoMirrored.Filled.ArrowForward,
                    contentDescription = null,
                    modifier = Modifier
                        .padding(horizontal = AppSpacing.xs)
                        .size(14.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    workspaceActionLabel(change.current_action),
                    style = CompactTypography.secondary,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            if (change.material_change_components.isNotEmpty()) {
                Text(
                    change.material_change_components
                        .joinToString(" · ") { workspaceChangeComponentLabel(it) },
                    modifier = Modifier.padding(top = AppSpacing.xs),
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        } else {
            Text(
                "正式动作延续，当前没有足够重要的新变化。",
                modifier = Modifier.padding(top = AppSpacing.small),
                style = CompactTypography.secondary,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        change.review_after?.takeIf { it.isNotBlank() }?.let { reviewAfter ->
            Text(
                "下次复核 ${workspaceTimestamp(reviewAfter)}",
                modifier = Modifier.padding(top = AppSpacing.xs),
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }

    DenseRowDivider(inset = false)
    DecisionWorkspaceCompanyEventState(
        financial = workspace.financial_currentness,
        events = workspace.corporate_events,
    )

    if (risk.position_present) {
        DenseRowDivider(inset = false)
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = AppSpacing.rowVertical),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("持仓风控", style = CompactTypography.rowTitle)
                Spacer(Modifier.weight(1f))
                if ((risk.locked_quantity ?: 0.0) > 0.0) {
                    DenseStateTag("T+1 锁定", colors.warning)
                } else {
                    DenseStateTag("可用", colors.rise)
                }
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = AppSpacing.small),
            ) {
                WorkspaceMetric(
                    label = "持仓数量",
                    value = risk.quantity.workspaceQuantity(),
                    modifier = Modifier.weight(1f),
                )
                WorkspaceMetric(
                    label = "可卖数量",
                    value = risk.sellable_quantity.workspaceQuantity(),
                    modifier = Modifier.weight(1f),
                    alignEnd = true,
                )
            }

            val locked = risk.locked_quantity ?: 0.0
            if (locked > 0.0) {
                Text(
                    "锁定 ${locked.workspaceQuantity()}${risk.next_eligible_sell_at?.let { " · 最早 ${workspaceTimestamp(it)}" } ?: ""}",
                    modifier = Modifier.padding(top = AppSpacing.xs),
                    style = CompactTypography.caption,
                    color = colors.warning,
                )
            }
        }
    }
}

@Composable
private fun DecisionWorkspaceCompanyEventState(
    financial: DecisionWorkspaceFinancialCurrentnessDto?,
    events: DecisionWorkspaceCorporateEventsDto,
) {
    val colors = MaterialTheme.marketColors
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = AppSpacing.rowVertical),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("公司与事件", style = CompactTypography.rowTitle)
            Spacer(Modifier.weight(1f))
            when {
                events.status == "partial" || events.official_source_status == "stale_fallback" -> {
                    DenseStateTag("事件不完整", colors.warning)
                }
                events.status == "unavailable" -> {
                    DenseStateTag("事件不可用", MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        if (financial == null && events.active_events.isEmpty()) {
            Text(
                if (events.status == "unavailable") "当前没有结构化公司/事件快照" else "暂无重要公司事件",
                modifier = Modifier.padding(top = AppSpacing.small),
                style = CompactTypography.secondary,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            return@Column
        }

        financial?.let { currentness ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = AppSpacing.small),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    workspaceFinancialCurrentnessLabel(currentness),
                    modifier = Modifier.weight(1f),
                    style = CompactTypography.secondary,
                    color = if (currentness.current_confirmation == "CONFLICTED") {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.onSurface
                    },
                )
                Text(
                    currentness.latest_observed_period ?: "--",
                    style = CompactTypography.caption,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        events.active_events.firstOrNull()?.let { event ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = AppSpacing.small),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(
                        workspaceEventTitle(event),
                        style = CompactTypography.secondary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        event.scheduled_at ?: "时间待定",
                        style = CompactTypography.caption,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                DenseStateTag(
                    workspaceEventLifecycle(event.lifecycle_status),
                    MaterialTheme.colorScheme.primary,
                )
            }
        }
    }
}

@Composable
private fun WorkspaceMetric(
    label: String,
    value: String,
    modifier: Modifier,
    alignEnd: Boolean = false,
) {
    Column(
        modifier = modifier,
        horizontalAlignment = if (alignEnd) Alignment.End else Alignment.Start,
    ) {
        Text(
            label,
            style = CompactTypography.caption,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            value,
            style = CompactTypography.rowValue,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun workspaceActionColor(value: String?): Color = when (value?.uppercase(Locale.ROOT)) {
    "BUY", "OPEN", "ADD" -> MaterialTheme.marketColors.rise
    "REDUCE", "EXIT", "SELL" -> MaterialTheme.marketColors.fall
    "BLOCKED" -> MaterialTheme.colorScheme.error
    else -> MaterialTheme.colorScheme.primary
}

private fun workspaceFinancialCurrentnessLabel(value: DecisionWorkspaceFinancialCurrentnessDto): String = when {
    value.current_confirmation == "CONFIRMED" && value.latest_period_status == "CURRENT" -> "财报最新已同步"
    value.current_confirmation == "PENDING" -> "财报等待披露"
    value.current_confirmation == "CONFLICTED" -> "财报来源存在冲突"
    else -> "财报状态已同步"
}

private fun workspaceEventTitle(event: DecisionWorkspaceCorporateEventDto): String =
    event.title?.takeIf { it.isNotBlank() } ?: "定期报告披露"

private fun workspaceEventLifecycle(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "SCHEDULED" -> "已预约"
    "DUE" -> "今日披露"
    "RELEASED_UNVERIFIED" -> "待核验"
    "VERIFIED" -> "已验证"
    else -> "待定"
}

private fun workspaceActionLabel(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "BUY", "OPEN" -> "买入候选"
    "WAIT", "WATCH" -> "继续观察"
    "HOLD" -> "建议持有"
    "ADD" -> "择机加仓"
    "REDUCE" -> "逢高减仓"
    "EXIT", "SELL" -> "清仓退出"
    "BLOCKED" -> "策略阻断"
    else -> "状态未知"
}

private fun workspaceChangeComponentLabel(value: String): String = when (value) {
    "action_gates" -> "准入规则"
    "position_state" -> "仓位变动"
    "price_state" -> "价格触发"
    "technical_state" -> "技术指标"
    "risk_level" -> "风险等级"
    "market_regime" -> "市场环境"
    "event_state" -> "重大事件"
    "plan_contract_hash" -> "交易计划"
    else -> "数据因子"
}

private fun workspaceTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value)
        .withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
}.getOrElse {
    value.replace('T', ' ')
        .substringBefore('+')
        .substringBefore('Z')
        .take(16)
}

private fun Double?.workspaceQuantity(): String = when {
    this == null -> "--"
    this % 1.0 == 0.0 -> toLong().toString()
    else -> "%.2f".format(Locale.US, this)
}
