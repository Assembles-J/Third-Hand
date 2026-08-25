package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.theme.AppSpacing
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

    Card(
        modifier = modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(AppSpacing.large),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("决策工作台", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.ExtraBold)
                    Text("DECISION WORKSPACE", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.6f))
                }
                IconButton(
                    onClick = onRefresh,
                    enabled = refreshEnabled,
                    colors = IconButtonDefaults.iconButtonColors(contentColor = MaterialTheme.colorScheme.primary)
                ) {
                    if (busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, "刷新")
                }
            }

            when (state) {
                DecisionWorkspaceUiState.Loading -> {
                    Box(Modifier.fillMaxWidth().padding(vertical = AppSpacing.xxLarge), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(Modifier.size(24.dp))
                    }
                }
                is DecisionWorkspaceUiState.Empty -> {
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
                        shape = MaterialTheme.shapes.medium,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text(state.message, Modifier.padding(AppSpacing.large), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                is DecisionWorkspaceUiState.Error -> {
                    Surface(
                        color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.2f),
                        shape = MaterialTheme.shapes.medium,
                        modifier = Modifier.fillMaxWidth(),
                        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.2f))
                    ) {
                        Text(state.message, Modifier.padding(AppSpacing.large), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    }
                }
                is DecisionWorkspaceUiState.Ready -> {
                    DecisionWorkspaceSummaryBody(state.workspace)
                }
            }
        }
    }
}

@Composable
private fun DecisionWorkspaceSummaryBody(workspace: DecisionWorkspaceDto) {
    val change = workspace.what_changed
    val risk = workspace.paper_risk
    val colors = MaterialTheme.marketColors

    // Formal Action Section
    Surface(
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f),
        shape = MaterialTheme.shapes.medium,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.padding(AppSpacing.medium)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Surface(
                    color = MaterialTheme.colorScheme.primary,
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        workspaceActionLabel(workspace.formal_action),
                        Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = Color.White
                    )
                }
                Spacer(Modifier.width(AppSpacing.medium))
                Text(
                    workspace.summary.ifBlank { "决策系统运行正常" },
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
            }
        }
    }

    // Material Change Section
    if (change.material_change) {
        Column(Modifier.padding(vertical = AppSpacing.small)) {
            Text("显著变化探测", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = colors.rise)
            Spacer(Modifier.height(AppSpacing.xs))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(workspaceActionLabel(change.prior_action), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Icon(Icons.AutoMirrored.Filled.ArrowForward, null, Modifier.size(12.dp).padding(horizontal = 4.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(workspaceActionLabel(change.current_action), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold, color = colors.rise)
            }
            if (change.material_change_components.isNotEmpty()) {
                Text(
                    "触发因子：${change.material_change_components.joinToString(" / ") { workspaceChangeComponentLabel(it) }}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }

    HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))

    // Events Section
    DecisionWorkspaceCompanyEventState(workspace.financial_currentness, workspace.corporate_events)

    // Position State Section
    if (risk.position_present) {
        HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))
        Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.xs)) {
            Text("账本实时状态", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("持仓数量", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(risk.quantity.workspaceQuantity(), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("可卖数量", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(risk.sellable_quantity.workspaceQuantity(), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.Bold)
                }
            }
            if ((risk.locked_quantity ?: 0.0) > 0.0) {
                Surface(color = colors.warning.copy(alpha = 0.1f), shape = RoundedCornerShape(4.dp)) {
                    Row(Modifier.padding(horizontal = 6.dp, vertical = 2.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Warning, null, Modifier.size(10.dp), tint = colors.warning)
                        Spacer(Modifier.width(4.dp))
                        Text("T+1 锁定: ${risk.locked_quantity.workspaceQuantity()}", style = MaterialTheme.typography.labelSmall, color = colors.warning, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}

@Composable
private fun DecisionWorkspaceCompanyEventState(
    financial: DecisionWorkspaceFinancialCurrentnessDto?,
    events: DecisionWorkspaceCorporateEventsDto,
) {
    Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("公司事件时效", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            Spacer(Modifier.width(AppSpacing.small))
            if (events.official_source_status == "ready") {
                Icon(Icons.Default.CheckCircle, null, Modifier.size(12.dp), tint = MaterialTheme.marketColors.rise)
            }
        }

        if (financial != null) {
            val conflicted = financial.current_confirmation == "CONFLICTED"
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.2f), MaterialTheme.shapes.small)
                    .padding(AppSpacing.medium)
            ) {
                Text(
                    workspaceFinancialCurrentnessLabel(financial),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = if (conflicted) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface
                )
                Text(
                    "最新季报：${financial.latest_observed_period ?: "---"}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        if (events.active_events.isNotEmpty()) {
            events.active_events.take(1).forEach { event ->
                Surface(
                    color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.3f),
                    shape = MaterialTheme.shapes.small,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(Modifier.padding(AppSpacing.medium)) {
                        Text(
                            workspaceEventTitle(event),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold
                        )
                        Text(
                            "预计披露：${event.scheduled_at ?: "---"} · ${workspaceEventLifecycle(event.lifecycle_status)}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }
    }
}

private fun workspaceFinancialCurrentnessLabel(value: DecisionWorkspaceFinancialCurrentnessDto): String = when {
    value.current_confirmation == "CONFIRMED" && value.latest_period_status == "CURRENT" -> "财报状态：最新已同步"
    value.current_confirmation == "PENDING" -> "财报状态：等待披露中"
    value.current_confirmation == "CONFLICTED" -> "财报状态：存在来源冲突"
    else -> "财报状态：已同步"
}

private fun workspaceEventTitle(event: DecisionWorkspaceCorporateEventDto): String =
    event.title?.takeIf { it.isNotBlank() } ?: "定期报告披露"

private fun workspaceEventLifecycle(value: String?): String = when (value?.uppercase(Locale.ROOT)) {
    "SCHEDULED" -> "已预约"
    "DUE" -> "今日披露"
    "RELEASED_UNVERIFIED" -> "已发布待核验"
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
}.getOrElse { value.take(10) }

private fun Double?.workspaceQuantity(): String = when {
    this == null -> "--"
    this % 1.0 == 0.0 -> toLong().toString()
    else -> "%.2f".format(Locale.US, this)
}
