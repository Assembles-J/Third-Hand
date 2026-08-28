package com.thirdhand.app

import android.content.Context
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import com.thirdhand.app.lab.LabScreen
import com.thirdhand.app.ui.components.StrategyWorkspaceNavigationProvider
import com.thirdhand.app.ui.components.StrategyWorkspaceSection

/**
 * Temporary explicit Strategy subroute used while the primary shell remains a
 * single-activity numeric-tab host. Back always returns to the existing
 * `策略 -> 模拟执行` screen; no trading or review authority lives here.
 */
class StrategyWorkspaceActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val initial = StrategyWorkspaceSection.fromKey(intent.getStringExtra(EXTRA_SECTION))
        setContent {
            ThirdHandTheme(ThemeStore.load(this@StrategyWorkspaceActivity)) {
                StrategyWorkspaceSubroute(initial = initial, onReturnToExecution = { finish() })
            }
        }
    }

    companion object {
        private const val EXTRA_SECTION = "strategy_workspace_section"

        fun intent(context: Context, section: StrategyWorkspaceSection): Intent =
            Intent(context, StrategyWorkspaceActivity::class.java)
                .putExtra(EXTRA_SECTION, section.key)
    }
}

@Composable
private fun StrategyWorkspaceSubroute(
    initial: StrategyWorkspaceSection,
    onReturnToExecution: () -> Unit,
) {
    var sectionKey by rememberSaveable { mutableStateOf(initial.key) }
    val section = StrategyWorkspaceSection.fromKey(sectionKey)

    StrategyWorkspaceNavigationProvider(
        selected = section,
        onSelect = { target ->
            if (target == StrategyWorkspaceSection.SIMULATED_EXECUTION) {
                onReturnToExecution()
            } else {
                sectionKey = target.key
            }
        },
    ) {
        when (section) {
            StrategyWorkspaceSection.SIMULATED_EXECUTION -> {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {}
            }
            StrategyWorkspaceSection.EXECUTION_REVIEW -> ExecutionReviewScreen()
            StrategyWorkspaceSection.STRATEGY_EVALUATION -> LabScreen(onBack = onReturnToExecution)
        }
    }
}
