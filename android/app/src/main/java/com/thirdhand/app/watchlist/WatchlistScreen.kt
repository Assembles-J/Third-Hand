package com.thirdhand.app.watchlist

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.thirdhand.app.ResearchTargetDto
import com.thirdhand.app.SecurityCandidateDto
import com.thirdhand.app.StockSearchScreen
import com.thirdhand.app.ui.components.MarketTag
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.launch
import java.util.Locale

@Composable
fun WatchlistScreen(onOpenDetail: (ResearchTargetDto) -> Unit) {
    val context = LocalContext.current
    val controller = remember(context) { WatchlistController(NetworkWatchlistRepository(context.applicationContext)) }
    val state by controller.state.collectAsState()
    val scope = rememberCoroutineScope()
    var showAdd by remember { mutableStateOf(false) }
    var editingItem by remember { mutableStateOf<PersonalUniverseItemDto?>(null) }
    var deletingItem by remember { mutableStateOf<PersonalUniverseItemDto?>(null) }

    LaunchedEffect(Unit) { controller.load() }

    WatchlistScreenContent(
        state = state,
        onRefresh = { scope.launch { controller.refresh() } },
        onSelectTab = controller::selectTab,
        onAdd = { showAdd = true },
        onOpenDetail = { item ->
            onOpenDetail(
                ResearchTargetDto(
                    symbol = item.symbol,
                    name = item.name,
                    status = if (item.isPosition) "active_holding" else "watchlist",
                    last_activity_at = item.decision_updated_at ?: item.quote_as_of ?: "",
                ),
            )
        },
        onEdit = { editingItem = it },
        onDelete = { deletingItem = it },
    )

    if (showAdd) {
        WatchlistAddDialog(
            onDismiss = { showAdd = false },
            onSelect = { candidate ->
                showAdd = false
                scope.launch { controller.add(candidate.symbol, candidate.name) }
            },
        )
    }
    editingItem?.let { item ->
        WatchlistEditDialog(
            item = item,
            onDismiss = { editingItem = null },
            onSave = { priority, note ->
                editingItem = null
                scope.launch { controller.update(item.symbol, priority, note) }
            },
        )
    }
    deletingItem?.let { item ->
        AlertDialog(
            onDismissRequest = { deletingItem = null },
            title = { Text("移出自选？") },
            text = { Text("将 ${item.name} · ${item.symbol} 从自选中移除。持仓事实不会因此删除。") },
            confirmButton = {
                Button(onClick = {
                    deletingItem = null
                    scope.launch { controller.remove(item.symbol) }
                }) { Text("移出") }
            },
            dismissButton = { TextButton(onClick = { deletingItem = null }) { Text("取消") } },
        )
    }
}

@Composable
internal fun WatchlistScreenContent(
    state: WatchlistUiState,
    onRefresh: () -> Unit,
    onSelectTab: (PersonalUniverseTab) -> Unit,
    onAdd: () -> Unit,
    onOpenDetail: (PersonalUniverseItemDto) -> Unit,
    onEdit: (PersonalUniverseItemDto) -> Unit,
    onDelete: (PersonalUniverseItemDto) -> Unit,
) {
    val busy = state is WatchlistUiState.Loading || (state is WatchlistUiState.Ready && (state.refreshing || state.mutating))
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 28.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        item {
            TradingPageHeader(
                title = "自选与持仓",
                subtitle = "Personal Universe · 只读组合状态，不授予交易权限",
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onAdd, enabled = !busy) {
                        Icon(Icons.Filled.Add, contentDescription = "添加自选")
                    }
                    IconButton(onClick = onRefresh, enabled = !busy) {
                        if (busy) {
                            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Filled.Refresh, contentDescription = "刷新自选与持仓")
                        }
                    }
                }
            }
        }

        when (state) {
            WatchlistUiState.Loading -> item { WatchlistMessageCard("正在读取自选、持仓与缓存行情…") }
            is WatchlistUiState.Error -> item {
                WatchlistMessageCard(
                    text = "自选暂不可用：${state.message}",
                    error = true,
                    action = if (state.recoverable) "重试" else null,
                    onAction = onRefresh,
                )
            }
            is WatchlistUiState.Ready -> {
                item { WatchlistSummary(state) }
                item {
                    WatchlistTabs(
                        state = state,
                        onSelectTab = onSelectTab,
                    )
                }
                if (state.response.data_state != "ready" || state.response.warnings.isNotEmpty()) {
                    item {
                        WatchlistMessageCard(
                            text = state.response.warnings.joinToString("；").ifBlank { "部分数据暂不可用，仍显示已有事实。" },
                            warning = true,
                        )
                    }
                }
                val visible = state.visibleItems()
                if (visible.isEmpty()) {
                    item {
                        WatchlistMessageCard(
                            if (state.selectedTab == PersonalUniverseTab.WATCHLIST) {
                                "还没有自选标的。点击右上角 +，可按股票名称或代码添加。"
                            } else {
                                "当前没有持仓。持仓由交易/账户事实决定，不会因自选操作被删除。"
                            },
                        )
                    }
                } else {
                    visible.forEach { item ->
                        item(key = "${state.selectedTab}-${item.symbol}") {
                            PersonalUniverseRow(
                                item = item,
                                onOpen = { onOpenDetail(item) },
                                onEdit = if (item.isWatchlist) ({ onEdit(item) }) else null,
                                onDelete = if (item.isWatchlist) ({ onDelete(item) }) else null,
                            )
                        }
                    }
                }
                state.message?.let { item { WatchlistMessageCard(it) } }
                state.transientError?.let { item { WatchlistMessageCard("操作失败：$it", error = true) } }
            }
        }
    }
}

@Composable
private fun WatchlistSummary(state: WatchlistUiState.Ready) {
    val counts = state.response.counts
    Card(
        Modifier.padding(horizontal = 20.dp, vertical = 8.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceContainerLow),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
            Text("关注范围", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
            Text("持仓 ${counts.positions} · 自选 ${counts.watchlist} · 合并 ${counts.combined}", style = MaterialTheme.typography.bodyMedium)
            Text("持仓永远优先保留；自选只是关注关系，不会改变 Formal Action。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun WatchlistTabs(state: WatchlistUiState.Ready, onSelectTab: (PersonalUniverseTab) -> Unit) {
    Row(
        Modifier.padding(horizontal = 20.dp, vertical = 4.dp).fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        FilterChip(
            selected = state.selectedTab == PersonalUniverseTab.WATCHLIST,
            onClick = { onSelectTab(PersonalUniverseTab.WATCHLIST) },
            label = { Text("自选 ${state.response.counts.watchlist}") },
        )
        FilterChip(
            selected = state.selectedTab == PersonalUniverseTab.POSITIONS,
            onClick = { onSelectTab(PersonalUniverseTab.POSITIONS) },
            label = { Text("持仓 ${state.response.counts.positions}") },
        )
    }
}

@Composable
private fun PersonalUniverseRow(
    item: PersonalUniverseItemDto,
    onOpen: () -> Unit,
    onEdit: (() -> Unit)?,
    onDelete: (() -> Unit)?,
) {
    val marketColors = MaterialTheme.marketColors
    val change = item.change_percent
    val changeColor = when {
        change == null || change == 0.0 -> marketColors.neutral
        change > 0 -> marketColors.rise
        else -> marketColors.fall
    }
    Column(Modifier.fillMaxWidth().clickable(onClick = onOpen)) {
        Row(
            Modifier.padding(horizontal = 20.dp, vertical = 11.dp).fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(item.name.ifBlank { item.symbol }, maxLines = 1, overflow = TextOverflow.Ellipsis, fontWeight = FontWeight.Bold)
                    item.market?.takeIf { it.isNotBlank() }?.let { MarketTag(it) }
                    if (item.isPosition) MarketTag("持仓")
                    item.watchlist_priority?.let { MarketTag(priorityLabel(it)) }
                }
                Text(item.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                item.watchlist_note?.takeIf { it.isNotBlank() }?.let {
                    Text(it, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (item.isPosition) {
                    Text(positionLine(item), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(item.last_price?.let { String.format(Locale.US, "%.2f", it) } ?: "—", fontWeight = FontWeight.Bold)
                Text(formatChange(change), color = changeColor, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                Text(quoteStateLabel(item.quote_display_state), style = MaterialTheme.typography.labelSmall, color = quoteStateColor(item.quote_display_state))
                item.quote_as_of?.takeIf { it.isNotBlank() }?.let {
                    Text(shortTime(it), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                item.formal_action?.takeIf { it.isNotBlank() }?.let {
                    Text("Formal $it", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
                }
            }
            if (onEdit != null || onDelete != null) {
                Spacer(Modifier.width(4.dp))
                Column {
                    onEdit?.let { action -> IconButton(onClick = action) { Icon(Icons.Filled.Edit, contentDescription = "编辑 ${item.name} 自选信息") } }
                    onDelete?.let { action -> IconButton(onClick = action) { Icon(Icons.Filled.Delete, contentDescription = "移出 ${item.name} 自选") } }
                }
            }
        }
        TradingRowDivider()
    }
}

@Composable
private fun quoteStateColor(state: String) = when (state.lowercase()) {
    "stale", "unavailable" -> MaterialTheme.marketColors.warning
    "refreshing" -> MaterialTheme.marketColors.information
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

private fun quoteStateLabel(state: String) = when (state.lowercase()) {
    "live" -> "实时"
    "refreshing" -> "刷新中"
    "session_close" -> "收盘价"
    "stale" -> "行情滞后"
    else -> "暂无行情"
}

private fun priorityLabel(priority: String) = when (priority.uppercase()) {
    "CORE" -> "核心"
    "FOCUS" -> "重点"
    else -> "普通"
}

private fun formatChange(value: Double?): String = when {
    value == null -> "—"
    value > 0 -> String.format(Locale.US, "+%.2f%%", value)
    else -> String.format(Locale.US, "%.2f%%", value)
}

private fun positionLine(item: PersonalUniverseItemDto): String {
    val quantity = item.position_quantity?.let { String.format(Locale.US, "%.0f", it) } ?: "—"
    val sellable = item.sellable_quantity?.let { String.format(Locale.US, "%.0f", it) } ?: "—"
    val locked = item.locked_quantity?.let { String.format(Locale.US, "%.0f", it) } ?: "—"
    return "持仓 $quantity · 可卖 $sellable · 锁定 $locked"
}

private fun shortTime(value: String): String = value.replace('T', ' ').take(16)

@Composable
private fun WatchlistMessageCard(
    text: String,
    error: Boolean = false,
    warning: Boolean = false,
    action: String? = null,
    onAction: () -> Unit = {},
) {
    val container = when {
        error -> MaterialTheme.colorScheme.errorContainer
        warning -> MaterialTheme.colorScheme.tertiaryContainer
        else -> MaterialTheme.colorScheme.surfaceContainerLow
    }
    Card(
        Modifier.padding(horizontal = 20.dp, vertical = 6.dp).fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = container),
    ) {
        Row(Modifier.padding(14.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(text, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
            action?.let { TextButton(onClick = onAction) { Text(it) } }
        }
    }
}

@Composable
private fun WatchlistAddDialog(onDismiss: () -> Unit, onSelect: (SecurityCandidateDto) -> Unit) {
    Dialog(onDismissRequest = onDismiss) {
        Card(Modifier.fillMaxWidth().heightIn(min = 420.dp, max = 680.dp)) {
            Column(Modifier.padding(vertical = 12.dp)) {
                Row(Modifier.padding(horizontal = 16.dp).fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("添加自选", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text("支持股票名称或代码，本地命中优先", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    TextButton(onClick = onDismiss) { Text("关闭") }
                }
                StockSearchScreen(onSelect = onSelect, modifier = Modifier.fillMaxWidth())
            }
        }
    }
}

@Composable
private fun WatchlistEditDialog(
    item: PersonalUniverseItemDto,
    onDismiss: () -> Unit,
    onSave: (priority: String, note: String) -> Unit,
) {
    var priority by remember(item.symbol) { mutableStateOf(item.watchlist_priority ?: "NORMAL") }
    var note by remember(item.symbol) { mutableStateOf(item.watchlist_note.orEmpty()) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("编辑 ${item.name}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("关注优先级", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    listOf("NORMAL" to "普通", "FOCUS" to "重点", "CORE" to "核心").forEach { (value, label) ->
                        FilterChip(selected = priority == value, onClick = { priority = value }, label = { Text(label) })
                    }
                }
                OutlinedTextField(
                    value = note,
                    onValueChange = { if (it.length <= 500) note = it },
                    label = { Text("关注备注") },
                    supportingText = { Text("${note.length}/500") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 2,
                    maxLines = 4,
                )
                Text("优先级只影响关注顺序，不会改变交易动作。", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        confirmButton = { Button(onClick = { onSave(priority, note.trim()) }) { Text("保存") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}
