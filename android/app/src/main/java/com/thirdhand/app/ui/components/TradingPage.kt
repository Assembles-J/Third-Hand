package com.thirdhand.app.ui.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
enum class StrategyWorkspaceSection(val label: String, val key: String) {
    SIMULATED_EXECUTION("模拟执行", "execution"),
    EXECUTION_REVIEW("收益复盘", "review"),
    STRATEGY_EVALUATION("策略评估", "evaluation");

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
 * UIX9 keeps the public header contract stable while adding the compact Strategy
 * section selector only to the real Strategy execution route or an explicitly
 * provided Strategy subroute. Other financial screens keep the UIX8 chrome.
 */
@Composable
fun TradingPageHeader(title: String, subtitle: String, action: @Composable (() -> Unit)? = null) {
    val providedNavigation = LocalStrategyWorkspaceNavigation.current
    val context = LocalContext.current
    val isStrategyRoot = title == "策略执行"
    val navigation = when {
        providedNavigation != null -> providedNavigation
        isStrategyRoot -> StrategyWorkspaceNavigation(
            selected = StrategyWorkspaceSection.SIMULATED_EXECUTION,
            onSelect = { target ->
                if (target != StrategyWorkspaceSection.SIMULATED_EXECUTION) {
                    context.startActivity(StrategyWorkspaceActivity.intent(context, target))
                }
            },
        )
        else -> null
    }

    val visibleTitle = if (isStrategyRoot) "策略" else title
    val visibleSubtitle = if (isStrategyRoot) "AI决策 · 模拟执行 · 风险控制" else subtitle

    Column {
        DensePageHeader(
            title = visibleTitle,
            subtitle = visibleSubtitle,
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
                    .height(AppSpacing.touchTarget),
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
                            fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                            color = if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (active) {
                            Surface(
                                modifier = Modifier
                                    .align(Alignment.BottomCenter)
                                    .fillMaxWidth(0.68f)
                                    .height(3.dp),
                                color = MaterialTheme.colorScheme.primary,
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
