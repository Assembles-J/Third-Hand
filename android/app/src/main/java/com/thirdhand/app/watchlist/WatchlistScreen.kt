package com.thirdhand.app.watchlist

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.StarOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.thirdhand.app.ResearchTargetDto
import com.thirdhand.app.SecurityCandidateDto
import com.thirdhand.app.StockSearchScreen
import com.thirdhand.app.ui.components.MarketTag
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.launch
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WatchlistScreen(
    onOpenDetail: (ResearchTargetDto) -> Unit,
    onOpenProfile: () -> Unit = {},
) {
    val context = LocalContext.current
    val controller = remember(context) { WatchlistController(NetworkWatchlistRepository(context.applicationContext)) }
    val state by controller.state.collectAsState()
    val scope = rememberCoroutineScope()
    var showAdd by remember { mutableStateOf(false) }
    var editingItem by remember { mutableStateOf<PersonalUniverseItemDto?>(null) }
    var deletingItem by remember { mutableStateOf<PersonalUniverseItemDto?>(null) }

    LaunchedEffect(Unit) { controller.load() }

    Scaffold(
        topBar = {
            TradingPageHeader(
                title = "自选关注",
                subtitle = " Personal Universe · 组合动态快照"
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onOpenProfile) {
                        Icon(Icons.Default.Person, contentDescription = "个人中心", tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = { showAdd = true }) {
                        Icon(Icons.Default.Add, null, tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = { scope.launch { controller.refresh() } }) {
                        val busy = state is WatchlistUiState.Loading || (state is WatchlistUiState.Ready && (state as WatchlistUiState.Ready).refreshing)
                        if (busy) CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                        else Icon(Icons.Default.Refresh, null, tint = MaterialTheme.colorScheme.primary)
                    }
                }
            }
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small)
        ) {
            when (state) {
                WatchlistUiState.Loading -> {
                    item {
                        Box(Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator()
                        }
                    }
                }
                is WatchlistUiState.Ready -> {
                    val readyState = state as WatchlistUiState.Ready

                    item {
                        WatchlistSummaryCard(readyState)
                    }

                    stickyHeader {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            color = MaterialTheme.colorScheme.background
                        ) {
                            Row(Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium)) {
                                FilterChip(
                                    selected = readyState.selectedTab == PersonalUniverseTab.WATCHLIST,
                                    onClick = { controller.selectTab(PersonalUniverseTab.WATCHLIST) },
                                    label = { Text("自选 ${readyState.response.counts.watchlist}") },
                                    modifier = Modifier.padding(end = 8.dp)
                                )
                                FilterChip(
                                    selected = readyState.selectedTab == PersonalUniverseTab.POSITIONS,
                                    onClick = { controller.selectTab(PersonalUniverseTab.POSITIONS) },
                                    label = { Text("持仓 ${readyState.response.counts.positions}") }
                                )
                            }
                        }
                    }

                    val visibleItems = readyState.visibleItems()
                    if (visibleItems.isEmpty()) {
                        item {
                            EmptyWatchlistPlaceholder(readyState.selectedTab)
                        }
                    } else {
                        items(visibleItems, key = { it.symbol }) { item ->
                            WatchlistItemCard(
                                item = item,
                                onClick = {
                                    onOpenDetail(
                                        ResearchTargetDto(
                                            symbol = item.symbol,
                                            name = item.name,
                                            status = if (item.isPosition) "active_holding" else "watchlist",
                                            last_activity_at = item.decision_updated_at ?: item.quote_as_of ?: ""
                                        )
                                    )
                                },
                                onEdit = { editingItem = item },
                                onDelete = { deletingItem = item }
                            )
                        }
                    }
                }
                is WatchlistUiState.Error -> {
                    item {
                        Surface(
                            color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.2f),
                            modifier = Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
                            shape = MaterialTheme.shapes.medium
                        ) {
                            Text((state as WatchlistUiState.Error).message, Modifier.padding(AppSpacing.large), color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }
        }
    }

    if (showAdd) {
        WatchlistAddDialog(onDismiss = { showAdd = false }) { candidate ->
            showAdd = false
            scope.launch { controller.add(candidate.symbol, candidate.name) }
        }
    }

    editingItem?.let { item ->
        WatchlistEditDialog(item, onDismiss = { editingItem = null }) { e, p, n ->
            editingItem = null
            scope.launch { controller.update(item.symbol, e, p, n) }
        }
    }

    deletingItem?.let { item ->
        AlertDialog(
            onDismissRequest = { deletingItem = null },
            title = { Text("移出自选") },
            text = { Text("确认不再关注 ${item.name}？持仓事实不会受影响。") },
            confirmButton = {
                TextButton(onClick = {
                    deletingItem = null
                    scope.launch { controller.remove(item.symbol) }
                }) { Text("移出", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { deletingItem = null }) { Text("取消") }
            }
        )
    }
}

/**
 * Stateless rendering boundary for preview/screenshot coverage. Runtime state and
 * mutations remain in [WatchlistScreen]; this function deliberately accepts all
 * interactions so screenshot tests never create a network-backed controller.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WatchlistScreenContent(
    state: WatchlistUiState,
    onRefresh: () -> Unit,
    onSelectTab: (PersonalUniverseTab) -> Unit,
    onAdd: () -> Unit,
    onOpenDetail: (ResearchTargetDto) -> Unit,
    onEdit: (PersonalUniverseItemDto) -> Unit,
    onDelete: (PersonalUniverseItemDto) -> Unit,
) {
    Scaffold(
        topBar = {
            TradingPageHeader(title = "自选关注", subtitle = " Personal Universe · 组合动态快照") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onAdd) { Icon(Icons.Default.Add, "添加自选") }
                    IconButton(onClick = onRefresh) { Icon(Icons.Default.Refresh, "刷新") }
                }
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
            verticalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            when (state) {
                WatchlistUiState.Loading -> item {
                    Box(Modifier.fillMaxWidth().padding(AppSpacing.xxLarge), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                }
                is WatchlistUiState.Error -> item {
                    Text(state.message, Modifier.padding(AppSpacing.xxLarge), color = MaterialTheme.colorScheme.error)
                }
                is WatchlistUiState.Ready -> {
                    item { WatchlistSummaryCard(state) }
                    item {
                        Row(Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium)) {
                            FilterChip(state.selectedTab == PersonalUniverseTab.WATCHLIST, { onSelectTab(PersonalUniverseTab.WATCHLIST) }, { Text("自选 ${state.response.counts.watchlist}") })
                            Spacer(Modifier.width(AppSpacing.small))
                            FilterChip(state.selectedTab == PersonalUniverseTab.POSITIONS, { onSelectTab(PersonalUniverseTab.POSITIONS) }, { Text("持仓 ${state.response.counts.positions}") })
                        }
                    }
                    val visibleItems = state.visibleItems()
                    if (visibleItems.isEmpty()) item { EmptyWatchlistPlaceholder(state.selectedTab) }
                    else items(visibleItems, key = { it.symbol }) { item ->
                        WatchlistItemCard(
                            item = item,
                            onClick = {
                                onOpenDetail(ResearchTargetDto(item.symbol, item.name, if (item.isPosition) "active_holding" else "watchlist", item.decision_updated_at ?: item.quote_as_of ?: ""))
                            },
                            onEdit = { onEdit(item) },
                            onDelete = { onDelete(item) },
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun WatchlistSummaryCard(state: WatchlistUiState.Ready) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)),
        shape = MaterialTheme.shapes.large
    ) {
        Row(Modifier.padding(AppSpacing.large), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("覆盖范围", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                Text(
                    "持仓 ${state.response.counts.positions} · 自选 ${state.response.counts.watchlist}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold
                )
            }
            Surface(color = MaterialTheme.colorScheme.primary, shape = CircleShape) {
                Icon(
                    Icons.Default.Star,
                    null,
                    modifier = Modifier.padding(8.dp).size(16.dp),
                    tint = Color.White
                )
            }
        }
    }
}

@Composable
private fun WatchlistItemCard(
    item: PersonalUniverseItemDto,
    onClick: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    val colors = MaterialTheme.marketColors
    val change = item.change_percent ?: 0.0
    val changeColor = if (change >= 0) colors.rise else colors.fall

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.xxLarge, vertical = 2.dp)
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = MaterialTheme.shapes.medium,
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp)
    ) {
        Row(
            modifier = Modifier.padding(AppSpacing.large),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(item.name.ifBlank { item.symbol }, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                    if (item.isPosition) {
                        Spacer(Modifier.width(8.dp))
                        Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = RoundedCornerShape(4.dp)) {
                            Text("持仓", Modifier.padding(horizontal = 4.dp, vertical = 1.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
                Text(item.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

                if (item.watchlist_priority == "CORE") {
                    Text("核心关注标的", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary.copy(alpha = 0.7f), fontWeight = FontWeight.Bold)
                }
            }

            Column(horizontalAlignment = Alignment.End) {
                Text(
                    text = item.last_price?.let { "%.2f".format(it) } ?: "---",
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.ExtraBold
                )
                Surface(
                    color = changeColor.copy(alpha = 0.1f),
                    shape = RoundedCornerShape(4.dp)
                ) {
                    Text(
                        text = (if(change>=0)"+" else "") + "%.2f%%".format(change),
                        modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = changeColor
                    )
                }
            }

            Spacer(Modifier.width(AppSpacing.medium))

            IconButton(onClick = onEdit, modifier = Modifier.size(24.dp)) {
                Icon(Icons.Default.Edit, null, modifier = Modifier.size(16.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.5f))
            }
        }
    }
}

@Composable
private fun EmptyWatchlistPlaceholder(tab: PersonalUniverseTab) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 60.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            if (tab == PersonalUniverseTab.WATCHLIST) Icons.Default.StarOutline else Icons.Default.StarOutline,
            null,
            modifier = Modifier.size(48.dp),
            tint = MaterialTheme.colorScheme.outlineVariant
        )
        Spacer(Modifier.height(AppSpacing.large))
        Text(
            if (tab == PersonalUniverseTab.WATCHLIST) "暂无自选关注，点击右上角 + 开始添加" else "当前账户无持仓事实",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun WatchlistAddDialog(onDismiss: () -> Unit, onSelect: (SecurityCandidateDto) -> Unit) {
    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier.fillMaxWidth().heightIn(max = 600.dp),
            shape = MaterialTheme.shapes.large
        ) {
            Column(Modifier.padding(vertical = AppSpacing.large)) {
                Row(Modifier.padding(horizontal = AppSpacing.xxLarge).fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                    Text("添加标的", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    TextButton(onClick = onDismiss) { Text("取消") }
                }
                StockSearchScreen(onSelect = onSelect)
            }
        }
    }
}

@Composable
private fun WatchlistEditDialog(
    item: PersonalUniverseItemDto,
    onDismiss: () -> Unit,
    onSave: (enabled: Boolean, priority: String, note: String) -> Unit
) {
    var enabled by remember { mutableStateOf(item.watchlist_enabled ?: true) }
    var priority by remember { mutableStateOf(item.watchlist_priority ?: "NORMAL") }
    var note by remember { mutableStateOf(item.watchlist_note.orEmpty()) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("配置关注：${item.name}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("活跃监控", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                        Text("关闭后将暂停该标的的日常分析", style = MaterialTheme.typography.labelSmall)
                    }
                    Switch(checked = enabled, onCheckedChange = { enabled = it })
                }

                Column {
                    Text("关注权重", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                    Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf("NORMAL" to "普通", "FOCUS" to "重点", "CORE" to "核心").forEach { (v, l) ->
                            FilterChip(
                                selected = priority == v,
                                onClick = { priority = v },
                                label = { Text(l) }
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("备忘信息") },
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            Button(onClick = { onSave(enabled, priority, note) }) {
                Text("保存配置")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}
