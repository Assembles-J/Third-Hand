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
import kotlinx.coroutines.delay
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
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
    var runtimeStatus by remember { mutableStateOf<PaperTradingStatusDto?>(null) }
    var refreshing by remember { mutableStateOf(false) }
    var runningNow by remember { mutableStateOf(false) }
    var runMessage by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    fun refresh() {
        if (refreshing) return
        scope.launch {
        refreshing = true
        runCatching {
            api.paperTradingDashboard()
        }.onSuccess { loaded ->
            account = loaded.account; logs = loaded.logs; snapshots = loaded.snapshots; runtimeStatus = loaded.status; error = null
        }.onFailure { error = "无法读取模拟账本：${it.message ?: "请检查服务连接"}" }
        refreshing = false
        }
    }
    LaunchedEffect(Unit) {
        refresh()
        while (true) {
            delay(10_000)
            refresh()
        }
    }
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(vertical = 14.dp)) {
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) { Text("模拟操盘", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold); Text("不连接券商，仅在应用内按 AI 决策模拟记账", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                IconButton(enabled = !refreshing, onClick = ::refresh) {
                    if (refreshing) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, "刷新模拟账本")
                }
            }
        }
        item {
            FilledTonalButton(enabled = !runningNow, onClick = { scope.launch {
                runningNow = true
                runMessage = runCatching { api.runPaperTradingNow() }.fold(
                    onSuccess = { result -> "${result.message}：执行 ${result.executed} 笔，跳过 ${result.skipped} 笔" },
                    onFailure = { "立即模拟失败：${it.message ?: "请检查服务连接"}" },
                )
                runningNow = false
                refresh()
            } }) {
                if (runningNow) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                }
                Text(if (runningNow) "正在请求模拟判断…" else "立即模拟一次")
            }
        }
        runMessage?.let { message -> item { Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) } }
        item {
            val state = runtimeStatus
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("自动执行状态", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                        Text(
                            when {
                                state?.running == true -> "执行中"
                                state?.enabled == true -> "已开启"
                                else -> "已关闭"
                            },
                            color = if (state?.running == true) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                    if (state?.running == true || refreshing) LinearProgressIndicator(Modifier.fillMaxWidth())
                    Text(state?.last_message ?: "正在读取自动执行状态…", style = MaterialTheme.typography.bodyMedium)
                    state?.let {
                        val intervalMinutes = it.interval_seconds / 60
                        val nextHint = when {
                            !it.enabled -> "请在系统管理中开启后才会自动检查"
                            it.running -> "本次判断完成后将自动刷新"
                            it.seconds_until_next_run > 0 -> "下次自动检查约 ${maxOf(1, it.seconds_until_next_run / 60)} 分钟后"
                            else -> "下一轮行情刷新会触发检查"
                        }
                        Text("间隔 ${intervalMinutes} 分钟 · $nextHint", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        it.last_finished_at?.let { time -> Text("最近完成：${paperBeijingTimestamp(time)} · 执行 ${it.last_executed} 笔，跳过 ${it.last_skipped} 笔", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    }
                }
            }
        }
        item {
            Card(Modifier.fillMaxWidth()) { Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("模拟资金", fontWeight = FontWeight.Bold)
                Text("可用现金 ¥${account?.available_cash?.let { "%.2f".format(Locale.US, it) } ?: "--"}", style = MaterialTheme.typography.titleLarge)
                Text("总资产 ¥${account?.total_equity?.let { "%.2f".format(Locale.US, it) } ?: "--"} · 浮动/累计 ¥${account?.total_pnl?.let { "%.2f".format(Locale.US, it) } ?: "--"} (${account?.total_return_percent?.let { "%.2f%%".format(Locale.US, it) } ?: "--"})", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                snapshots.lastOrNull()?.let { Text("最近净值快照：${paperBeijingTimestamp(it.recorded_at)} · ¥${"%.2f".format(Locale.US, it.total_equity)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                Text("资金由数据库的统一“可用资金”提供；请到系统管理页修改。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("自动执行：${if (account?.enabled == true) "已开启（仅开盘期间，按已设定间隔）" else "已关闭，请在系统管理中开启"}", style = MaterialTheme.typography.labelMedium)
            } }
        }
        error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
        item { Text("模拟持仓", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        if (account?.positions.isNullOrEmpty()) item {
            Text("暂无模拟持仓。${runtimeStatus?.last_message ?: "正在等待首次状态返回"}", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        items(account?.positions.orEmpty(), key = { it.symbol }) { item -> ListItem(headlineContent = { Text("${item.name} · ${item.symbol}") }, supportingContent = { Text("数量 ${item.quantity} · 成本 ¥${"%.2f".format(Locale.US, item.average_cost)} · 现价 ¥${"%.2f".format(Locale.US, item.last_price)}\n市值 ¥${"%.2f".format(Locale.US, item.market_value)} · 浮盈亏 ¥${"%.2f".format(Locale.US, item.unrealized_pnl)} (${"%.2f%%".format(Locale.US, item.unrealized_return_percent)})") }) }
        item { Text("操作日志", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        if (logs.isEmpty()) item { Text("暂无模拟操作日志", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(logs, key = { it.id }) { log ->
            val action = when (log.side) { "BUY" -> "模拟买入 B"; "SELL" -> "模拟卖出 S"; else -> "规则跳过" }
            val time = paperBeijingTimestamp(log.executed_at)
            val detail = if (log.status == "skipped") "$time\n未执行：${paperSkipReason(log.reason)}" else "$time  ${log.quantity} 股 × ¥${"%.2f".format(Locale.US, log.price)} · 费用 ¥${"%.2f".format(Locale.US, log.fee)}\n现金 ¥${"%.2f".format(Locale.US, log.cash_before)} → ¥${"%.2f".format(Locale.US, log.cash_after)}"
            ListItem(headlineContent = { Text("$action · ${log.name} ${log.symbol}", fontWeight = FontWeight.SemiBold) }, supportingContent = { Text(detail) }, trailingContent = { Text(if (log.side == "BUY") "B" else if (log.side == "SELL") "S" else "跳过", color = if (log.status == "skipped") MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary) })
        }
    }
}

private fun paperBeijingTimestamp(value: String): String = runCatching {
    OffsetDateTime.parse(value).withOffsetSameInstant(ZoneOffset.ofHours(8))
        .format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss +08:00"))
}.getOrElse { value.replace('T', ' ').substringBefore("+").substringBefore("Z") + " +08:00" }

private fun paperSkipReason(reason: String): String = when {
    reason.contains("missing_saved_decision_report") -> "尚未完成该标的的决策数据准备"
    reason.contains("decision_has_no_executable") -> "当前没有满足条件的买卖信号"
    reason.contains("insufficient_paper_cash") -> "可用模拟资金不足，未买入"
    reason.contains("insufficient_paper_position") -> "模拟持仓数量不足，未卖出"
    reason.contains("paper_decision_already_executed") -> "该份决策已执行，避免重复交易"
    reason.contains("100_share_lot") -> "数量不符合 A 股 100 股一手规则"
    reason.contains("decision_status_") -> "决策数据尚未准备完成"
    else -> "本次条件未满足：$reason"
}
