package com.thirdhand.app

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import com.thirdhand.app.ui.components.DenseRowDivider
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography

/**
 * UIX0 Home shell.
 *
 * The current first slice deliberately reuses the existing News capability as
 * the only composed Home feed. It does not fabricate a new AI brief, review
 * aggregate or portfolio statistic while those Home read models do not exist.
 */
@Composable
fun HomeScreen() {
    Column(modifier = Modifier.fillMaxSize()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = AppSpacing.contentHorizontal,
                    end = AppSpacing.contentHorizontal,
                    top = AppSpacing.large,
                    bottom = AppSpacing.small,
                ),
        ) {
            Text(
                text = "首页",
                style = CompactTypography.pageTitle,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Spacer(Modifier.height(AppSpacing.xs))
            Text(
                text = "聚合基线 · 当前先接入现有资讯，组合、策略与自选保留独立入口",
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(AppSpacing.small))
            Surface(
                color = Color(0xFFFFE0E3),
                shape = MaterialTheme.shapes.small,
            ) {
                Text(
                    text = "更多关注 / 复核聚合将在现有服务事实具备后接入，不生成本地推荐。",
                    modifier = Modifier.padding(horizontal = AppSpacing.medium, vertical = AppSpacing.small),
                    style = CompactTypography.caption,
                    color = Color(0xFF5C1017),
                )
            }
        }
        DenseRowDivider(inset = false)
        Box(modifier = Modifier.weight(1f)) {
            NewsScreen()
        }
    }
}
