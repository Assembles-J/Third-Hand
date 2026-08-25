package com.thirdhand.app.ui.components

import android.content.res.Configuration
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.PieChart
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
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
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
        shape = MaterialTheme.shapes.large,
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Column(
            modifier = Modifier.padding(AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.large),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.PieChart,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(Modifier.width(AppSpacing.small))
                    Text(
                        text = "资产配置",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                }
                Text(
                    text = "$holdingCount 只证券${if (pendingCount > 0) " · $pendingCount 条待处理" else ""}",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(
                        MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
                        MaterialTheme.shapes.medium
                    )
                    .padding(AppSpacing.large),
                horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium)
            ) {
                SummaryItem(
                    label = "总市值",
                    value = marketValue ?: "---",
                    modifier = Modifier.weight(1f)
                )
                SummaryItem(
                    label = "浮动盈亏",
                    value = totalPnl ?: "--",
                    valueColor = if (totalPnl == null) {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    } else if (totalPnlIsPositive) {
                        MaterialTheme.marketColors.rise
                    } else {
                        MaterialTheme.marketColors.fall
                    },
                    modifier = Modifier.weight(1f)
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(AppSpacing.medium)
            ) {
                OutlinedButton(
                    onClick = onAdd,
                    modifier = Modifier.weight(1f),
                    shape = MaterialTheme.shapes.medium
                ) {
                    Icon(Icons.Filled.Add, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(AppSpacing.xs))
                    Text("手动记录")
                }
                OutlinedButton(
                    onClick = onImport,
                    modifier = Modifier.weight(1f),
                    shape = MaterialTheme.shapes.medium
                ) {
                    Icon(Icons.Filled.CameraAlt, contentDescription = null, modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(AppSpacing.xs))
                    Text("智能导入")
                }
            }
        }
    }
}

@Composable
private fun SummaryItem(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    valueColor: androidx.compose.ui.graphics.Color = MaterialTheme.colorScheme.onSurface
) {
    Column(modifier = modifier) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = FontWeight.Medium
        )
        Text(
            text = value,
            style = MaterialTheme.typography.titleLarge,
            color = valueColor,
            fontWeight = FontWeight.Bold
        )
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
