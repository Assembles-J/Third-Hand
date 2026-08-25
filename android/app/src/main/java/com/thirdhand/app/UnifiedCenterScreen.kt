package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoGraph
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.theme.AppSpacing

@Composable
fun UnifiedCenterScreen(onOpenSaleHistory: () -> Unit) {
    var selected by remember { mutableIntStateOf(0) }
    val scrollState = rememberScrollState()

    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        // 顶层选项卡
        Surface(
            modifier = Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
            shape = CircleShape
        ) {
            Row(Modifier.padding(4.dp)) {
                CenterTabItem(
                    text = "资产与复盘",
                    selected = selected == 0,
                    onClick = { selected = 0 },
                    modifier = Modifier.weight(1f)
                )
                CenterTabItem(
                    text = "系统管理",
                    selected = selected == 1,
                    onClick = { selected = 1 },
                    modifier = Modifier.weight(1f)
                )
            }
        }

        if (selected == 0) {
            Column(Modifier.verticalScroll(scrollState)) {
                Card(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    shape = MaterialTheme.shapes.large,
                    elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
                ) {
                    Row(
                        modifier = Modifier.padding(AppSpacing.large),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Surface(
                            color = MaterialTheme.colorScheme.primaryContainer,
                            shape = MaterialTheme.shapes.medium
                        ) {
                            Icon(
                                Icons.Default.History,
                                contentDescription = null,
                                modifier = Modifier.padding(10.dp),
                                tint = MaterialTheme.colorScheme.primary
                            )
                        }
                        Spacer(Modifier.width(AppSpacing.medium))
                        Column(Modifier.weight(1f)) {
                            Text("交易记录", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                            Text("追踪已实现盈亏与历史成交", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        TextButton(onClick = onOpenSaleHistory) {
                            Text("查看全部")
                        }
                    }
                }

                ExecutionReviewScreen()
            }
        } else {
            CompactAdminDashboardScreen()
        }
    }
}

@Composable
private fun CenterTabItem(text: String, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier
            .height(40.dp)
            .clip(CircleShape)
            .clickable(onClick = onClick),
        color = if (selected) MaterialTheme.colorScheme.primary else Color.Transparent,
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(
                text = text,
                style = MaterialTheme.typography.labelLarge,
                fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
fun AiLearningAnalysisCard(
    analysis: LearningCaseAnalysisDto?,
    caseCount: Int,
    loading: Boolean,
    onAnalyze: () -> Unit,
) = Card(
    modifier = Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium).fillMaxWidth(),
    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    shape = MaterialTheme.shapes.large
) {
    Column(Modifier.padding(AppSpacing.xxLarge), verticalArrangement = Arrangement.spacedBy(AppSpacing.medium)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.AutoGraph, null, modifier = Modifier.size(20.dp), tint = MaterialTheme.colorScheme.primary)
                Spacer(Modifier.width(AppSpacing.small))
                Text("AI 复盘深度洞察", fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onPrimaryContainer)
            }
            if (analysis != null) {
                Surface(color = MaterialTheme.colorScheme.primary.copy(alpha = 0.2f), shape = CircleShape) {
                    Text(
                        "${confidenceLabel(analysis.confidence)}置信度",
                        Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
        }

        Surface(
            color = Color.White.copy(alpha = 0.5f),
            shape = MaterialTheme.shapes.medium
        ) {
            Column(Modifier.padding(AppSpacing.large)) {
                when {
                    caseCount == 0 -> {
                        Text("当前尚未记录复盘案例。通过记录真实的交易教训，AI 能够学习并识别您的操作模式。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onPrimaryContainer)
                    }
                    loading -> {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(AppSpacing.medium))
                            Text("AI 正在归纳交易模式...", style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    analysis != null -> {
                        Text(analysis.summary, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
                        Spacer(Modifier.height(AppSpacing.small))
                        analysis.recurring_patterns.take(2).forEach { Text("• $it", style = MaterialTheme.typography.labelSmall) }
                    }
                    else -> {
                        Text("已有 $caseCount 条复盘，点击下方生成全局洞察。", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }

        Button(
            onClick = onAnalyze,
            enabled = caseCount > 0 && !loading,
            modifier = Modifier.fillMaxWidth(),
            shape = MaterialTheme.shapes.medium,
            colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.primary)
        ) {
            Icon(Icons.Filled.Refresh, null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(AppSpacing.small))
            Text(if (loading) "正在生成" else "生成 AI 全局复盘")
        }
    }
}

private fun confidenceLabel(value: String): String = when (value) {
    "high" -> "高"
    "medium" -> "中"
    else -> "低"
}
