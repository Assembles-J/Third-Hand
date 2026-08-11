package com.thirdhand.app

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import java.util.Locale

@Composable
fun PaperTradingScreen() {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var account by remember { mutableStateOf<PaperTradingAccountDto?>(null) }
    var logs by remember { mutableStateOf<List<PaperTradingLogDto>>(emptyList()) }
    var snapshots by remember { mutableStateOf<List<PaperEquitySnapshotDto>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    fun refresh() = scope.launch {
        runCatching { Triple(api.paperTradingAccount(), api.paperTradingLogs(), api.paperTradingEquitySnapshots()) }.onSuccess { (loaded, events, equityHistory) ->
            account = loaded; logs = events; snapshots = equityHistory; error = null
        }.onFailure { error = "无法读取模拟账本：${it.message ?: "请检查服务连接"}" }
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(vertical = 14.dp)) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { Text("模拟操盘", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); Text("仅模拟，不影响真实持仓与真实可用资金", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                IconButton(onClick = ::refresh) { Icon(Icons.Filled.Refresh, "刷新模拟账本") }
            }
        }
        item {
            Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("模拟资金", fontWeight = FontWeight.Bold)
                Text("可用现金 ¥${account?.available_cash?.let { "%.2f".format(Locale.US, it) } ?: "--"}", style = MaterialTheme.typography.titleLarge)
                Text("总资产 ¥${account?.total_equity?.let { "%.2f".format(Locale.US, it) } ?: "--"} · 浮动/累计 ¥${account?.total_pnl?.let { "%.2f".format(Locale.US, it) } ?: "--"} (${account?.total_return_percent?.let { "%.2f%%".format(Locale.US, it) } ?: "--"})", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                snapshots.lastOrNull()?.let { Text("最近净值快照：${it.recorded_at.take(16)} · ¥${"%.2f".format(Locale.US, it.total_equity)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                Text("资金由数据库的统一“可用资金”提供；请到系统管理页修改。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("自动执行：${if (account?.enabled == true) "已开启（开盘期间每小时）" else "已关闭，请在系统管理中开启"}", style = MaterialTheme.typography.labelMedium)
            } }
        }
        error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        item { Text("模拟持仓", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        if (account?.positions.isNullOrEmpty()) item { Text("暂无模拟持仓。开启后将只依据统一 AI 决策执行。", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(account?.positions.orEmpty(), key = { it.symbol }) { item -> ListItem(headlineContent = { Text("${item.name} · ${item.symbol}") }, supportingContent = { Text("数量 ${item.quantity} · 成本 ¥${"%.2f".format(Locale.US, item.average_cost)} · 现价 ¥${"%.2f".format(Locale.US, item.last_price)}\n市值 ¥${"%.2f".format(Locale.US, item.market_value)} · 浮盈亏 ¥${"%.2f".format(Locale.US, item.unrealized_pnl)} (${"%.2f%%".format(Locale.US, item.unrealized_return_percent)})") }) }
        item { Text("操作日志", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        if (logs.isEmpty()) item { Text("暂无模拟操作日志", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(logs, key = { it.id }) { log ->
            val action = when (log.side) { "BUY" -> "模拟买入 B"; "SELL" -> "模拟卖出 S"; else -> "规则跳过" }
            val detail = if (log.status == "skipped") "${log.executed_at.take(16)}\n未执行：${log.reason}" else "${log.executed_at.take(16)}  ${log.quantity} 股 × ¥${"%.2f".format(Locale.US, log.price)} · 费用 ¥${"%.2f".format(Locale.US, log.fee)}\n现金 ¥${"%.2f".format(Locale.US, log.cash_before)} → ¥${"%.2f".format(Locale.US, log.cash_after)}"
            ListItem(headlineContent = { Text("$action · ${log.name} ${log.symbol}", fontWeight = FontWeight.SemiBold) }, supportingContent = { Text(detail) }, trailingContent = { Text(if (log.side == "BUY") "B" else if (log.side == "SELL") "S" else "跳过", color = if (log.status == "skipped") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary) })
        }
    }
}
