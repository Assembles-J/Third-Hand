package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import java.util.Locale

@Composable
fun StrategyProfileCard(
    report: DecisionReportDto?,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Column(
            modifier = Modifier.padding(AppSpacing.large),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)
        ) {
            if (report == null) {
                Text(
                    "策略与权限",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    "等待决策报告生成以加载策略周期权限...",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                return@Column
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    "策略权限快照",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary
                )
                Surface(
                    color = MaterialTheme.colorScheme.secondaryContainer,
                    shape = CircleShape
                ) {
                    Text(
                        report.strategy?.strategy_id ?: "STD-CORE",
                        Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            val strategy = report.strategy
            if (strategy == null || strategy.strategy_id.isBlank()) {
                Text("暂无详细策略身份记录", style = MaterialTheme.typography.bodySmall)
            } else {
                Column {
                    Text(
                        strategy.name.ifBlank { "默认交易策略" },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.ExtraBold
                    )
                    Text(
                        "版本 v${strategy.strategy_version} · 周期角色：${strategy.holding_horizon}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }

                HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))

                val timeframe = report.timeframe_authority
                if (timeframe != null) {
                    Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                        StrategyTimeframeRow("周线 Weekly", "weekly", strategy, timeframe.weekly_state, timeframe)
                        StrategyTimeframeRow("日线 Daily", "daily", strategy, timeframe.daily_state, timeframe)
                        StrategyTimeframeRow("60M 级别", "60m", strategy, timeframe.state_60m, timeframe)
                        StrategyTimeframeRow("15M 级别", "15m", strategy, timeframe.state_15m, timeframe)
                    }

                    if (timeframe.confirmation_state != "NOT_APPLIED" || timeframe.conflict_state != "NONE") {
                        Spacer(Modifier.height(AppSpacing.xs))
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                            shape = MaterialTheme.shapes.small,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Row(
                                Modifier.padding(AppSpacing.medium),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    "多周期确认：${strategyStateLabel(timeframe.confirmation_state)}",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold
                                )
                                if (timeframe.conflict_state != "NONE") {
                                    Text(
                                        "冲突状态：${strategyStateLabel(timeframe.conflict_state)}",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.marketColors.fall,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                    }
                }
            }
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
    val role = strategy.authority_matrix[key]?.let(::strategyRoleLabel) ?: "仅观察"
    val colors = MaterialTheme.marketColors

    val stateColor = when (rawState.uppercase(Locale.ROOT)) {
        "UP", "BULLISH", "CONFIRMED" -> colors.rise
        "DOWN", "BEARISH" -> colors.fall
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium)
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(if (unavailable) colors.neutral else stateColor)
        )
        Text(
            label,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Bold
        )
        Text(
            role,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            if (unavailable) "禁用" else strategyStateLabel(rawState),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
            color = if (unavailable) colors.neutral else stateColor,
            textAlign = TextAlign.End,
            modifier = Modifier.width(60.dp)
        )
    }
}

private fun strategyRoleLabel(value: String): String = when (value.lowercase(Locale.ROOT)) {
    "strategic_structure" -> "趋势结构"
    "setup_position_management" -> "仓位管理"
    "execution_timing" -> "入场时点"
    "hard_risk_execution" -> "风险风控"
    "quality_risk_context" -> "背景分析"
    else -> "数据参考"
}

private fun strategyStateLabel(value: String): String = when (value.uppercase(Locale.ROOT)) {
    "UP", "BULLISH", "CONFIRMED" -> "看多"
    "DOWN", "BEARISH" -> "看空"
    "FLAT", "MIXED", "NEUTRAL" -> "震荡"
    "AVAILABLE" -> "正常"
    "CONFLICT" -> "存在冲突"
    else -> "未知"
}
