package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

@Composable
fun UnifiedCenterScreen(onOpenSaleHistory: () -> Unit) {
    var selected by remember { mutableIntStateOf(0) }
    Column(Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FilterChip(
                selected = selected == 0,
                onClick = { selected = 0 },
                label = { Text("资产与复盘") },
                modifier = Modifier.weight(1f),
            )
            FilterChip(
                selected = selected == 1,
                onClick = { selected = 1 },
                label = { Text("系统管理") },
                modifier = Modifier.weight(1f),
            )
        }
        if (selected == 0) {
            Column {
                Card(Modifier.padding(horizontal = 20.dp, vertical = 4.dp).fillMaxWidth()) {
                    Row(Modifier.padding(horizontal = 14.dp, vertical = 8.dp).fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Column { Text("交易记录", fontWeight = FontWeight.SemiBold); Text("查询每笔出售与已实现盈亏", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        TextButton(onClick = onOpenSaleHistory) { Text("出售历史") }
                    }
                }
                ProfileScreen()
            }
        } else CompactAdminDashboardScreen()
    }
}

@Composable
fun AiLearningAnalysisCard(
    analysis: LearningCaseAnalysisDto?,
    hasCases: Boolean,
    loading: Boolean,
    onAnalyze: () -> Unit,
) = Card(
    modifier = Modifier.padding(horizontal = 20.dp).fillMaxWidth(),
    colors = CardDefaults.cardColors(
        containerColor = MaterialTheme.colorScheme.primaryContainer,
        contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
    ),
) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(Icons.Filled.AutoGraph, contentDescription = null)
                Text("AI 复盘分析", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
            }
            analysis?.let { Text("${confidenceLabel(it.confidence)}置信", style = MaterialTheme.typography.labelSmall) }
        }
        when {
            !hasCases -> Text("先记录一次判断、结果和教训；AI 会从你的记录中归纳重复模式。", style = MaterialTheme.typography.bodySmall)
            loading -> Text("正在梳理复盘记录中的重复模式…", style = MaterialTheme.typography.bodySmall)
            analysis != null -> {
                Text(analysis.summary, style = MaterialTheme.typography.bodySmall)
                analysis.recurring_patterns.take(2).forEach { Text("• $it", style = MaterialTheme.typography.labelMedium) }
                analysis.next_review_focus.take(2).forEach { Text("下一次关注：$it", style = MaterialTheme.typography.labelMedium) }
            }
            else -> Text("生成一份聚焦“重复模式与复盘重点”的总结，不提供买卖建议。", style = MaterialTheme.typography.bodySmall)
        }
        TextButton(onClick = onAnalyze, enabled = hasCases && !loading) {
            Icon(Icons.Filled.Refresh, contentDescription = null)
            Text(if (analysis == null) "生成 AI 分析" else "重新生成")
        }
    }
}

private fun confidenceLabel(value: String): String = when (value) {
    "high" -> "高"
    "medium" -> "中"
    else -> "低"
}
