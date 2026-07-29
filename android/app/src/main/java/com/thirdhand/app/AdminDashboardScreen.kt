package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.CloudSync
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Memory
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Save
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.TaskAlt
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp

private val ConsoleCanvas = Color(0xFF111614)
private val ConsolePanel = Color(0xFF171E1B)
private val ConsoleRaised = Color(0xFF1D2622)
private val ConsoleMint = Color(0xFF9EFFBF)
private val ConsoleTeal = Color(0xFF4ED6C2)
private val ConsoleGold = Color(0xFFF4D35E)
private val ConsoleCoral = Color(0xFFFF8C69)
private val ConsoleText = Color(0xFFE7EEE9)
private val ConsoleQuiet = Color(0xFF9DA9A3)

@Composable
fun AdminDashboardScreen() {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    var refreshIndex by remember { mutableIntStateOf(0) }
    var overview by remember { mutableStateOf<AdminOverviewDto?>(null) }
    var monitoringError by remember { mutableStateOf<String?>(null) }
    var refreshInterval by remember { mutableStateOf("30 秒") }
    var safeMode by remember { mutableStateOf(true) }
    var savedMessage by remember { mutableStateOf<String?>(null) }
    var showMaintenanceWarning by remember { mutableStateOf(false) }

    LaunchedEffect(refreshIndex) {
        monitoringError = null
        runCatching { api.adminOverview() }
            .onSuccess { overview = it }
            .onFailure { monitoringError = "无法读取后端监控数据：${it.message ?: "请检查服务地址"}" }
    }

    if (showMaintenanceWarning) AlertDialog(
        onDismissRequest = { showMaintenanceWarning = false },
        icon = { Icon(Icons.Filled.WarningAmber, null, tint = ConsoleCoral) },
        title = { Text("进入维护模式？") },
        text = { Text("新任务将暂停投递，正在运行的任务会继续完成。") },
        confirmButton = { Button(onClick = { showMaintenanceWarning = false; savedMessage = "维护模式已开启" }) { Text("确认开启") } },
        dismissButton = { TextButton(onClick = { showMaintenanceWarning = false }) { Text("取消") } },
    )

    Column(
        modifier = Modifier.background(ConsoleCanvas).verticalScroll(rememberScrollState()).padding(horizontal = 16.dp, vertical = 18.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        ConsoleHeader(refreshIndex, overview, { refreshIndex += 1; savedMessage = "正在刷新后端监控数据" }, { showMaintenanceWarning = true })
        monitoringError?.let { ConsoleCard { Text(it, color = ConsoleCoral, style = MaterialTheme.typography.bodySmall) } }
        ConsoleMetricGrid(overview)
        ThroughputPanel(overview)
        AlertPanel(overview)
        CapacityPanel(overview)
        JobPanel(overview)
        QuickConfigPanel(refreshInterval, { refreshInterval = it }, safeMode, { safeMode = it }) {
            savedMessage = "配置已保存，将在下一个刷新周期生效"
        }
        savedMessage?.let { message -> ConsoleCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.TaskAlt, null, tint = ConsoleMint)
                Spacer(Modifier.width(10.dp))
                Text(message, color = ConsoleText, style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.weight(1f))
                TextButton(onClick = { savedMessage = null }) { Text("关闭") }
            }
        } }
    }
}

@Composable
private fun ConsoleHeader(refreshIndex: Int, overview: AdminOverviewDto?, onRefresh: () -> Unit, onMaintenance: () -> Unit) {
    Row(verticalAlignment = Alignment.Top) {
        Column(Modifier.weight(1f)) {
            Text("系统总览", color = ConsoleText, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("REMOTE BACKEND  /  CN-SHANGHAI-01", color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(8.dp).background(ConsoleMint))
                Spacer(Modifier.width(7.dp))
                Text(if (overview?.status == "ok") "后端服务正常 · 已刷新" else "正在读取后端状态… ${refreshIndex}", color = ConsoleMint, style = MaterialTheme.typography.labelMedium)
            }
        }
        IconButton(onClick = onRefresh) { Icon(Icons.Filled.Refresh, "刷新监控数据", tint = ConsoleText) }
        OutlinedButton(onClick = onMaintenance) { Text("维护模式", color = ConsoleCoral, style = MaterialTheme.typography.labelMedium) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ConsoleMetricGrid(overview: AdminOverviewDto?) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        MetricCell("API 状态", if (overview?.status == "ok") "在线" else "—", "实时后端", ConsoleMint, Icons.Filled.Bolt)
        MetricCell("已入库持仓", overview?.holdings_count?.toString() ?: "—", "聚合数量", ConsoleMint, Icons.Filled.Security)
        MetricCell("待处理草稿", overview?.pending_draft_count?.toString() ?: "—", "需人工核验", ConsoleGold, Icons.Filled.CloudSync)
        MetricCell("缓存行情", overview?.cached_quotes_count?.toString() ?: "—", "本地快照", ConsoleTeal, Icons.Filled.Memory)
    }
}

@Composable
private fun MetricCell(label: String, value: String, hint: String, accent: Color, icon: ImageVector) = Card(
    modifier = Modifier.width(168.dp), colors = CardDefaults.cardColors(containerColor = ConsolePanel), shape = MaterialTheme.shapes.extraSmall,
) {
    Column(Modifier.padding(14.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, null, tint = accent, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text(label, color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall, maxLines = 1)
        }
        Spacer(Modifier.height(10.dp))
        Text(value, color = ConsoleText, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
        Text(hint, color = accent, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun ThroughputPanel(overview: AdminOverviewDto?) = ConsoleCard {
    SectionLabel("系统数据链路", "后端实时概览")
    Spacer(Modifier.height(16.dp)); TopologyTrace(); Spacer(Modifier.height(18.dp))
    Text("每分钟吞吐需接入指标采集器；当前展示已连接的后端组件。", color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
    Spacer(Modifier.height(8.dp))
    Row(Modifier.fillMaxWidth().height(88.dp), horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.Bottom) {
        listOf(28, 42, 35, 56, 49, 68, 60, 78, 63, 88, 72, 82).forEach { height ->
            Box(Modifier.weight(1f).height(height.dp).background(ConsoleTeal))
        }
    }
    Spacer(Modifier.height(8.dp))
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text("00:00", color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
        Text("运行 ${overview?.uptime_seconds ?: 0} 秒", color = ConsoleMint, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
        Text("14:00", color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
    }
}

@Composable
private fun TopologyTrace() {
    val nodes = listOf("API" to ConsoleMint, "Worker" to ConsoleMint, "PostgreSQL" to ConsoleMint, "Redis" to ConsoleCoral, "LLM" to ConsoleMint)
    Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), verticalAlignment = Alignment.CenterVertically) {
        nodes.forEachIndexed { index, (name, color) ->
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Box(Modifier.size(40.dp).background(ConsoleRaised), contentAlignment = Alignment.Center) {
                    Icon(Icons.Filled.Storage, null, tint = color, modifier = Modifier.size(18.dp))
                }
                Text(name, color = ConsoleText, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
            }
            if (index < nodes.lastIndex) Box(Modifier.width(30.dp).height(2.dp).background(if (index == 2) ConsoleCoral else ConsoleMint))
        }
    }
}

@Composable
private fun AlertPanel(overview: AdminOverviewDto?) = ConsoleCard {
    val pending = overview?.pending_draft_count ?: 0
    SectionLabel("需要处理", if (pending > 0) "$pending 条待处理" else "暂无待处理项")
    if (pending > 0) AlertLine("有 $pending 条持仓草稿需要核验", "请在持仓页补全证券代码后确认入库", ConsoleGold, "查看持仓")
    else AlertLine("当前没有待处理草稿", "后端聚合数据已同步", ConsoleMint, "已完成")
}

@Composable
private fun AlertLine(title: String, detail: String, color: Color, action: String) {
    Row(Modifier.padding(top = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Filled.ErrorOutline, null, tint = color)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = ConsoleText, fontWeight = FontWeight.SemiBold)
            Text(detail, color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
        }
        TextButton(onClick = {}) { Text(action, color = color, style = MaterialTheme.typography.labelSmall) }
    }
}

@Composable
private fun CapacityPanel(overview: AdminOverviewDto?) = ConsoleCard {
    SectionLabel("资源容量", "当前 / 配额")
    CapacityRow("SQLite 数据库", formatBytes(overview?.database_bytes ?: 0), databaseProgress(overview?.database_bytes ?: 0), ConsoleTeal)
    CapacityRow("内容缓存", "${overview?.cached_content_count ?: 0} 条", 0f, ConsoleMint)
    CapacityRow("行情快照", "${overview?.cached_quotes_count ?: 0} 条", 0f, ConsoleMint)
}

@Composable
private fun CapacityRow(name: String, value: String, progress: Float, color: Color) {
    Column(Modifier.padding(top = 13.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text(name, color = ConsoleText, style = MaterialTheme.typography.bodySmall)
            Text(value, color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
        }
        Spacer(Modifier.height(5.dp))
        LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth(), color = color, trackColor = ConsoleRaised)
    }
}

@Composable
private fun JobPanel(overview: AdminOverviewDto?) = ConsoleCard {
    SectionLabel("应用数据状态", "聚合统计")
    JobRow("HOLDINGS", "已入库", "${overview?.holdings_count ?: 0} 条", "本地数据库", ConsoleMint)
    JobRow("DRAFTS", "草稿", "${overview?.draft_count ?: 0} 条", "待确认数据", ConsoleGold)
    JobRow("CONTENT", "缓存", "${overview?.cached_content_count ?: 0} 条", "新闻与公告", ConsoleTeal)
}

@Composable
private fun JobRow(id: String, status: String, duration: String, owner: String, color: Color) {
    Column(Modifier.padding(top = 12.dp)) {
        HorizontalDivider(color = ConsoleRaised)
        Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(id, Modifier.weight(1.15f), color = ConsoleText, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
            Text(status, Modifier.weight(1f), color = color, style = MaterialTheme.typography.labelSmall)
            Text(duration, Modifier.weight(.7f), color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
            Text(owner, Modifier.weight(1f), color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun QuickConfigPanel(interval: String, onIntervalChange: (String) -> Unit, safeMode: Boolean, onSafeModeChange: (Boolean) -> Unit, onSave: () -> Unit) = ConsoleCard {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Filled.Settings, null, tint = ConsoleMint); Spacer(Modifier.width(8.dp)); SectionLabel("快捷配置", "安全范围内的即时调整")
    }
    Spacer(Modifier.height(16.dp)); Text("刷新间隔", color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        listOf("30 秒", "1 分钟", "5 分钟").forEach { option -> FilterChip(selected = interval == option, onClick = { onIntervalChange(option) }, label = { Text(option) }) }
    }
    Spacer(Modifier.height(12.dp))
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("安全模式", color = ConsoleText, fontWeight = FontWeight.SemiBold)
            Text("拦截风险配置与高频数据拉取", color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
        }
        Switch(checked = safeMode, onCheckedChange = onSafeModeChange)
    }
    Spacer(Modifier.height(14.dp))
    Button(onClick = onSave, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = ConsoleMint, contentColor = ConsoleCanvas)) {
        Icon(Icons.Filled.Save, null); Spacer(Modifier.width(8.dp)); Text("保存更改", fontWeight = FontWeight.Bold)
    }
}

private fun formatBytes(bytes: Int): String = when {
    bytes >= 1_048_576 -> "%.1f MB".format(bytes / 1_048_576.0)
    bytes >= 1_024 -> "%.1f KB".format(bytes / 1_024.0)
    else -> "$bytes B"
}

private fun databaseProgress(bytes: Int): Float = (bytes / (100.0 * 1_048_576.0)).toFloat().coerceIn(0f, 1f)

@Composable
private fun ConsoleCard(content: @Composable ColumnScope.() -> Unit) = Card(
    modifier = Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = ConsolePanel), shape = MaterialTheme.shapes.extraSmall,
) { Column(Modifier.padding(16.dp), content = content) }

@Composable
private fun SectionLabel(title: String, meta: String) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(title, color = ConsoleText, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
        Text(meta, color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
    }
}
