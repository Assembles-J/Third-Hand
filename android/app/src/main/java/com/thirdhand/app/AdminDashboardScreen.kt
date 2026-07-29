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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
    var refreshIndex by remember { mutableIntStateOf(0) }
    var refreshInterval by remember { mutableStateOf("30 秒") }
    var safeMode by remember { mutableStateOf(true) }
    var savedMessage by remember { mutableStateOf<String?>(null) }
    var showMaintenanceWarning by remember { mutableStateOf(false) }

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
        ConsoleHeader(refreshIndex, { refreshIndex += 1; savedMessage = "监控数据已刷新" }, { showMaintenanceWarning = true })
        ConsoleMetricGrid()
        ThroughputPanel()
        AlertPanel()
        CapacityPanel()
        JobPanel()
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
private fun ConsoleHeader(refreshIndex: Int, onRefresh: () -> Unit, onMaintenance: () -> Unit) {
    Row(verticalAlignment = Alignment.Top) {
        Column(Modifier.weight(1f)) {
            Text("系统总览", color = ConsoleText, style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("REMOTE BACKEND  /  CN-SHANGHAI-01", color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(8.dp).background(ConsoleMint))
                Spacer(Modifier.width(7.dp))
                Text("全部服务正常 · 14:02:${44 + refreshIndex}", color = ConsoleMint, style = MaterialTheme.typography.labelMedium)
            }
        }
        IconButton(onClick = onRefresh) { Icon(Icons.Filled.Refresh, "刷新监控数据", tint = ConsoleText) }
        OutlinedButton(onClick = onMaintenance) { Text("维护模式", color = ConsoleCoral, style = MaterialTheme.typography.labelMedium) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ConsoleMetricGrid() {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        MetricCell("API 可用性", "99.98%", "+0.02%", ConsoleMint, Icons.Filled.Bolt)
        MetricCell("活跃用户", "1,284", "+12.4%", ConsoleMint, Icons.Filled.Security)
        MetricCell("任务吞吐", "18.6k/h", "-2.1%", ConsoleCoral, Icons.Filled.CloudSync)
        MetricCell("今日 LLM 成本", "¥426.80", "预计", ConsoleGold, Icons.Filled.Memory)
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
private fun ThroughputPanel() = ConsoleCard {
    SectionLabel("请求与任务吞吐", "24H · 每 30 秒更新")
    Spacer(Modifier.height(16.dp)); TopologyTrace(); Spacer(Modifier.height(18.dp))
    Text("过去 24 小时请求 / 完成任务", color = ConsoleQuiet, style = MaterialTheme.typography.labelSmall)
    Spacer(Modifier.height(8.dp))
    Row(Modifier.fillMaxWidth().height(88.dp), horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.Bottom) {
        listOf(28, 42, 35, 56, 49, 68, 60, 78, 63, 88, 72, 82).forEachIndexed { index, height ->
            Box(Modifier.weight(1f).height(height.dp).background(if (index == 8) ConsoleCoral else ConsoleTeal))
        }
    }
    Spacer(Modifier.height(8.dp))
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        Text("00:00", color = ConsoleQuiet, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
        Text("当前 1,482 req/min", color = ConsoleMint, fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.labelSmall)
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
private fun AlertPanel() = ConsoleCard {
    SectionLabel("需要处理", "2 条告警")
    AlertLine("Redis 延迟超过 80 ms", "3 分钟前 · 96 ms", ConsoleCoral, "查看日志")
    AlertLine("财新新闻源波动", "18 分钟前 · 可用性 92.4%", ConsoleGold, "查看数据源")
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
private fun CapacityPanel() = ConsoleCard {
    SectionLabel("资源容量", "当前 / 配额")
    CapacityRow("计算资源", "4.6 / 8 vCPU", 0.58f, ConsoleMint)
    CapacityRow("内存", "10.2 / 16 GB", 0.64f, ConsoleTeal)
    CapacityRow("PostgreSQL", "72 / 100 GB", 0.72f, ConsoleGold)
    CapacityRow("Redis", "1.4 / 2 GB", 0.70f, ConsoleGold)
    CapacityRow("对象存储", "403 / 500 GB", 0.81f, ConsoleCoral)
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
private fun JobPanel() = ConsoleCard {
    SectionLabel("任务队列", "12 个运行中")
    JobRow("JB-882103", "运行中", "420 ms", "SYS_SYNC", ConsoleMint)
    JobRow("JB-882104", "等待", "—", "USR_662", ConsoleTeal)
    JobRow("JB-882099", "重试 3/5", "8.2 s", "LLM_VAL", ConsoleCoral)
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
