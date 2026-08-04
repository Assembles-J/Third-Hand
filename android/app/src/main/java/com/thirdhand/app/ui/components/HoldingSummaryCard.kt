package com.thirdhand.app.ui.components

import android.content.res.Configuration
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import com.thirdhand.app.ThemeMode
import com.thirdhand.app.ThirdHandTheme
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors

@Composable
fun HoldingSummaryCard(
    holdingCount: Int,
    pendingCount: Int,
    marketValue: String?,
    totalPnl: String?,
    totalPnlIsPositive: Boolean,
    onAdd: () -> Unit,
    onImport: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(
            modifier = Modifier.padding(AppSpacing.large),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.medium),
        ) {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                Text(
                    text = "持仓概览",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    text = "$holdingCount 只持仓${if (pendingCount > 0) " · $pendingCount 条待补全" else ""}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
                Column(modifier = Modifier.weight(1f)) { Text("总市值", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant); Text(marketValue ?: "等待行情更新", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }
                Column(modifier = Modifier.weight(1f)) { Text("浮动盈亏", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant); Text(totalPnl ?: "--", style = MaterialTheme.typography.titleMedium, color = if (totalPnl == null) MaterialTheme.colorScheme.onSurfaceVariant else if (totalPnlIsPositive) MaterialTheme.marketColors.rise else MaterialTheme.marketColors.fall, fontWeight = FontWeight.SemiBold) }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
                TextButton(onClick = onAdd) {
                    Icon(Icons.Filled.Add, contentDescription = null)
                    Spacer(Modifier.width(AppSpacing.xs)); Text("添加持仓")
                }
                TextButton(onClick = onImport) {
                    Icon(Icons.Filled.CameraAlt, contentDescription = null)
                    Spacer(Modifier.width(AppSpacing.xs)); Text("导入截图")
                }
            }
        }
    }
}

@Preview(name = "Light", showBackground = true)
@Composable
private fun HoldingSummaryCardLightPreview() {
    ThirdHandTheme(ThemeMode.LIGHT) {
        HoldingSummaryCard(
            holdingCount = 3,
            pendingCount = 1,
            marketValue = "128,560.00",
            totalPnl = "+6,420.50",
            totalPnlIsPositive = true,
            onAdd = {},
            onImport = {},
            modifier = Modifier.padding(AppSpacing.large),
        )
    }
}

@Preview(name = "Dark", showBackground = true, uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
private fun HoldingSummaryCardDarkPreview() {
    ThirdHandTheme(ThemeMode.DARK) {
        HoldingSummaryCard(
            holdingCount = 2,
            pendingCount = 0,
            marketValue = "98,100.00",
            totalPnl = "-2,480.00",
            totalPnlIsPositive = false,
            onAdd = {},
            onImport = {},
            modifier = Modifier.padding(AppSpacing.large),
        )
    }
}
