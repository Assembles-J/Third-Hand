package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CloudSync
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

private val CompactCanvas = Color(0xFF111614)
private val CompactPanel = Color(0xFF171E1B)
private val CompactMint = Color(0xFF9EFFBF)
private val CompactTeal = Color(0xFF4ED6C2)
private val CompactGold = Color(0xFFF4D35E)
private val CompactCoral = Color(0xFFFF8C69)
private val CompactText = Color(0xFFE7EEE9)
private val CompactQuiet = Color(0xFF9DA9A3)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun CompactAdminDashboardScreen() {
    val context = androidx.compose.ui.platform.LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    var refreshKey by remember { mutableIntStateOf(0) }
    var overview by remember { mutableStateOf<AdminOverviewDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var interval by remember { mutableStateOf("30 秒") }
    LaunchedEffect(refreshKey) {
        error = null
        runCatching { api.adminOverview() }
            .onSuccess { overview = it }
            .onFailure { error = "无法读取系统状态，请检查服务连接。" }
    }
    Column(
        Modifier.fillMaxWidth().background(CompactCanvas).verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("系统管理", color = CompactText, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Text("数据状态与安全配置", color = CompactQuiet, style = MaterialTheme.typography.labelSmall, fontFamily = FontFamily.Monospace)
            }
            IconButton(onClick = { refreshKey += 1 }) { Icon(Icons.Filled.Refresh, "刷新系统状态", tint = CompactMint) }
        }
        error?.let { CompactConsoleCard { Text(it, color = CompactCoral, style = MaterialTheme.typography.bodySmall) } }
        CompactMetricGrid(overview)
        PendingReviewCard(overview)
        ApplicationDataGrid(overview)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            CompactConsoleCard(Modifier.weight(1f).widthIn(min = 150.dp)) {
                Text("资源容量", color = CompactText, fontWeight = FontWeight.Bold)
                Text("SQLite ${compactBytes(overview?.database_bytes ?: 0)}", color = CompactTeal, style = MaterialTheme.typography.labelMedium)
                Text("内容 ${overview?.cached_content_count ?: 0} 条", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
            }
            CompactConsoleCard(Modifier.weight(1f).widthIn(min = 150.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Filled.Settings, null, tint = CompactMint)
                    Text(" 快捷配置", color = CompactText, fontWeight = FontWeight.Bold)
                }
                FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    listOf("30 秒", "1 分钟", "5 分钟").forEach { value ->
                        FilterChip(selected = interval == value, onClick = { interval = value }, label = { Text(value) })
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun CompactMetricGrid(overview: AdminOverviewDto?) = FlowRow(
    horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp),
) {
    CompactMetric("API", if (overview?.status == "ok") "在线" else "—", "服务状态", CompactMint, Modifier.weight(1f))
    CompactMetric("待核验", "${overview?.pending_draft_count ?: 0}", "持仓草稿", CompactGold, Modifier.weight(1f))
    CompactMetric("持仓", "${overview?.holdings_count ?: 0}", "已入库", CompactMint, Modifier.weight(1f))
    CompactMetric("行情", "${overview?.cached_quotes_count ?: 0}", "缓存快照", CompactTeal, Modifier.weight(1f))
}

@Composable
private fun PendingReviewCard(overview: AdminOverviewDto?) = CompactConsoleCard {
    val pending = overview?.pending_draft_count ?: 0
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Filled.WarningAmber, null, tint = if (pending > 0) CompactGold else CompactMint)
        Column(Modifier.weight(1f).padding(start = 10.dp)) {
            Text(if (pending > 0) "$pending 条持仓草稿待核验" else "没有待核验项目", color = CompactText, fontWeight = FontWeight.SemiBold)
            Text("补全证券代码后即可确认入库。", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
        }
        TextButton(onClick = {}) { Text("查看", color = CompactMint) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ApplicationDataGrid(overview: AdminOverviewDto?) = CompactConsoleCard {
    Text("应用数据状态", color = CompactText, fontWeight = FontWeight.Bold)
    Text("数量与最新缓存状态", color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 10.dp)) {
        CompactMetric("持仓", "${overview?.holdings_count ?: 0}", "已入库", CompactMint, Modifier.weight(1f), Icons.Filled.Security)
        CompactMetric("行情", "${overview?.cached_quotes_count ?: 0}", "本地快照", CompactTeal, Modifier.weight(1f), Icons.Filled.Memory)
        CompactMetric("草稿", "${overview?.draft_count ?: 0}", "${overview?.pending_draft_count ?: 0} 待处理", CompactGold, Modifier.weight(1f), Icons.Filled.CloudSync)
        CompactMetric("内容", "${overview?.cached_content_count ?: 0}", "已缓存", CompactMint, Modifier.weight(1f))
    }
}

@Composable
private fun CompactMetric(label: String, value: String, hint: String, accent: Color, modifier: Modifier, icon: androidx.compose.ui.graphics.vector.ImageVector? = null) = CompactConsoleCard(modifier.widthIn(min = 140.dp)) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        icon?.let { Icon(it, null, tint = accent) }
        Text(label, color = CompactQuiet, style = MaterialTheme.typography.labelSmall)
    }
    Text(value, color = CompactText, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
    Text(hint, color = accent, style = MaterialTheme.typography.labelSmall)
}

@Composable
private fun CompactConsoleCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) = Card(
    modifier = modifier,
    colors = CardDefaults.cardColors(containerColor = CompactPanel),
    shape = MaterialTheme.shapes.extraSmall,
) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { content() } }

private fun compactBytes(bytes: Int): String = when {
    bytes >= 1_048_576 -> "%.1f MB".format(bytes / 1_048_576.0)
    bytes >= 1_024 -> "%.1f KB".format(bytes / 1_024.0)
    else -> "$bytes B"
}
