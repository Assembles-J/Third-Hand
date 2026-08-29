package com.thirdhand.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.thirdhand.app.StrategyWorkspaceActivity
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography

/** Existing Strategy surfaces grouped under one authority-safe mobile workspace. */
enum class StrategyWorkspaceSection(
    val label: String,
    val key: String,
    val subtitle: String,
) {
    SIMULATED_EXECUTION("模拟执行", "execution", "模拟账户 · 决策驱动 · 风控执行"),
    EXECUTION_REVIEW("收益复盘", "review", "每日建议 · 收益复盘 · 执行结果"),
    STRATEGY_EVALUATION("策略评估", "evaluation", "SWING_V1 · 仿真评估 · 只读实验室");

    companion object {
        fun fromKey(value: String?): StrategyWorkspaceSection =
            entries.firstOrNull { it.key == value } ?: SIMULATED_EXECUTION
    }
}

@Immutable
data class StrategyWorkspaceNavigation(
    val selected: StrategyWorkspaceSection,
    val onSelect: (StrategyWorkspaceSection) -> Unit,
)

private val LocalStrategyWorkspaceNavigation =
    staticCompositionLocalOf<StrategyWorkspaceNavigation?> { null }

@Composable
fun StrategyWorkspaceNavigationProvider(
    selected: StrategyWorkspaceSection,
    onSelect: (StrategyWorkspaceSection) -> Unit,
    content: @Composable () -> Unit,
) {
    CompositionLocalProvider(
        LocalStrategyWorkspaceNavigation provides StrategyWorkspaceNavigation(selected, onSelect),
        content = content,
    )
}

/**
 * Compatibility wrapper for existing financial screens.
 *
 * The public header contract stays stable. Strategy routes are rendered as one
 * dedicated workspace with a shared `策略` title and section-specific, factual
 * subtitle. Other financial screens keep the shared dense page chrome.
 */
@Composable
fun TradingPageHeader(title: String, subtitle: String, action: @Composable (() -> Unit)? = null) {
    val providedNavigation = LocalStrategyWorkspaceNavigation.current
    val context = LocalContext.current
    val navigation = when {
        providedNavigation != null -> providedNavigation
        title == "策略执行" -> StrategyWorkspaceNavigation(
            selected = StrategyWorkspaceSection.SIMULATED_EXECUTION,
            onSelect = { target ->
                if (target != StrategyWorkspaceSection.SIMULATED_EXECUTION) {
                    context.startActivity(StrategyWorkspaceActivity.intent(context, target))
                }
            },
        )
        else -> null
    }

    Column {
        DensePageHeader(
            title = if (navigation != null) "策略" else title,
            subtitle = navigation?.selected?.subtitle ?: subtitle,
            action = action,
        )
        navigation?.let { StrategyWorkspaceSectionBar(it.selected, it.onSelect) }
    }
}

@Composable
fun StrategyWorkspaceSectionBar(
    selected: StrategyWorkspaceSection,
    onSelect: (StrategyWorkspaceSection) -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 0.dp,
    ) {
        Column {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(AppSpacing.touchTarget)
                    .padding(horizontal = AppSpacing.contentHorizontal),
            ) {
                StrategyWorkspaceSection.entries.forEach { section ->
                    val active = section == selected
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .clickable(enabled = !active) { onSelect(section) },
                    ) {
                        Text(
                            text = section.label,
                            modifier = Modifier.align(Alignment.Center),
                            style = if (active) CompactTypography.rowTitle else CompactTypography.secondary,
                            fontWeight = if (active) FontWeight.SemiBold else FontWeight.Medium,
                            color = if (active) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            },
                        )
                        if (active) {
                            Surface(
                                modifier = Modifier
                                    .align(Alignment.BottomCenter)
                                    .width(30.dp)
                                    .height(3.dp),
                                color = MaterialTheme.colorScheme.primary,
                                shape = RoundedCornerShape(3.dp),
                            ) {}
                        }
                    }
                }
            }
            HorizontalDivider(
                thickness = 0.5.dp,
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.45f),
            )
        }
    }
}

@Composable
fun TradingSection(title: String, detail: String? = null, modifier: Modifier = Modifier) {
    DenseSectionHeader(
        title = title,
        detail = detail,
        modifier = modifier,
    )
}

@Composable
fun TradingRowDivider(inset: Boolean = true) = DenseRowDivider(inset = inset)
