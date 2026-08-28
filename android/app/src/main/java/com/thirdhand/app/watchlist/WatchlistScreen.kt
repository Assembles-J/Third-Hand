package com.thirdhand.app.watchlist

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.StarOutline
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.thirdhand.app.ResearchTargetDto
import com.thirdhand.app.SecurityCandidateDto
import com.thirdhand.app.StockSearchScreen
import com.thirdhand.app.ui.components.DenseStateTag
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.CompactTypography
import com.thirdhand.app.ui.theme.marketColors
import kotlinx.coroutines.launch

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
                title = "自选",
                subtitle = "Personal Universe · 持仓与关注标的监控",
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onOpenProfile) {
                        Icon(Icons.Default.Person, contentDescription = "个人中心", tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = { showAdd = true }) {
                        Icon(Icons.Default.Add, contentDescription = "添加自选", tint = MaterialTheme.colorScheme.primary)
                    }
                    IconButton(onClick = { scope.launch { controller.refresh() } }) {
                        val busy = state is WatchlistUiState.Loading ||
                            (state is WatchlistUiState.Ready && (state as WatchlistUiState.Ready).refreshing)
                        if (busy) {
                            CircularProgressIndicator(Modifier.size(AppSpacing.xLarge), strokeWidth = 2.dp)
                        } else {
                            Icon(Icons.Default.Refresh, contentDescription = "刷新", tint = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
        ) {
            when (state) {
                WatchlistUiState.Loading -> {
                    item {
                        Box(
                            Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
                            contentAlignment = Alignment.Center,
                        ) {
                            CircularProgressIndicator()
                        }
                    }
                }

                is WatchlistUiState.Ready -> {
                    val readyState = state as WatchlistUiState.Ready

                    item { WatchlistSummaryStrip(readyState) }

                    readyState.response.warnings.forEach { warning ->
                        item { WatchlistNotice(warning, isError = false) }
                    }
                    readyState.transientError?.let { message ->
                        item {
                            WatchlistNotice(
                                message,
                                isError = true,
                                onRetry = { scope.launch { controller.refresh() } },
                            )
                        }
                    }
                    readyState.message?.let { message ->
                        item { WatchlistNotice(message, isError = false) }
                    }

                    stickyHeader {
                        WatchlistTabs(
                            selectedTab = readyState.selectedTab,
                            watchlistCount = readyState.response.counts.watchlist,
                            positionCount = readyState.response.counts.positions,
                            onSelect = controller::selectTab,
                        )
                    }

                    val visibleItems = readyState.visibleItems()
                    if (visibleItems.isEmpty()) {
                        item { EmptyWatchlistPlaceholder(readyState.selectedTab) }
                    } else {
                        items(visibleItems, key = { it.symbol }) { item ->
                            WatchlistItemRow(
                                item = item,
                                onClick = {
                                    onOpenDetail(
                                        ResearchTargetDto(
                                            symbol = item.symbol,
                                            name = item.name,
                                            status = if (item.isPosition) "active_holding" else "watchlist",
                                            last_activity_at = item.decision_updated_at ?: item.quote_as_of ?: "",
                                        )
                                    )
                                },
                                onEdit = { editingItem = item },
                                onDelete = { deletingItem = item },
                            )
                        }
                    }
                }

                is WatchlistUiState.Error -> {
                    item {
                        WatchlistNotice(
                            message = (state as WatchlistUiState.Error).message,
                            isError = true,
                            onRetry = { scope.launch { controller.load() } },
                        )
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
        WatchlistEditDialog(item, onDismiss = { editingItem = null }) { enabled, priority, note ->
            editingItem = null
            scope.launch { controller.update(item.symbol, enabled, priority, note) }
        }
    }

    deletingItem?.let { item ->
        AlertDialog(
            onDismissRequest = { deletingItem = null },
            title = { Text("移出自选") },
            text = { Text("确认不再关注 ${item.name}？持仓事实不会受影响。") },
            confirmButton = {
                TextButton(
                    onClick = {
                        deletingItem = null
                        scope.launch { controller.remove(item.symbol) }
                    },
                ) {
                    Text("移出", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { deletingItem = null }) { Text("取消") }
            },
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
            TradingPageHeader(title = "自选", subtitle = "Personal Universe · 持仓与关注标的监控") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    IconButton(onClick = onAdd) { Icon(Icons.Default.Add, "添加自选") }
                    IconButton(onClick = onRefresh) { Icon(Icons.Default.Refresh, "刷新") }
                }
            }
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(MaterialTheme.colorScheme.background),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge),
        ) {
            when (state) {
                WatchlistUiState.Loading -> item {
                    Box(
                        Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
                        contentAlignment = Alignment.Center,
                    ) {
                        CircularProgressIndicator()
                    }
                }

                is WatchlistUiState.Error -> item {
                    WatchlistNotice(state.message, isError = true)
                }

                is WatchlistUiState.Ready -> {
                    item { WatchlistSummaryStrip(state) }
                    state.response.warnings.forEach { warning ->
                        item { WatchlistNotice(warning, isError = false) }
                    }
                    state.transientError?.let { message ->
                        item { WatchlistNotice(message, isError = true, onRetry = onRefresh) }
                    }
                    state.message?.let { message ->
                        item { WatchlistNotice(message, isError = false) }
                    }
                    item {
                        WatchlistTabs(
                            selectedTab = state.selectedTab,
                            watchlistCount = state.response.counts.watchlist,
                            positionCount = state.response.counts.positions,
                            onSelect = onSelectTab,
                        )
                    }

                    val visibleItems = state.visibleItems()
                    if (visibleItems.isEmpty()) {
                        item { EmptyWatchlistPlaceholder(state.selectedTab) }
                    } else {
                        items(visibleItems, key = { it.symbol }) { item ->
                            WatchlistItemRow(
                                item = item,
                                onClick = {
                                    onOpenDetail(
                                        ResearchTargetDto(
                                            item.symbol,
                                            item.name,
                                            if (item.isPosition) "active_holding" else "watchlist",
                                            item.decision_updated_at ?: item.quote_as_of ?: "",
                                        )
                                    )
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
}

@Composable
private fun WatchlistSummaryStrip(state: WatchlistUiState.Ready) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .heightIn(min = AppSpacing.touchTarget)
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.rowVertical),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "监控范围",
            style = CompactTypography.sectionTitle,
            color = MaterialTheme.colorScheme.onSurface,
        )
        Spacer(Modifier.weight(1f))
        Text(
            "自选 ${state.response.counts.watchlist} · 持仓 ${state.response.counts.positions} · 共 ${state.response.counts.combined}",
            style = CompactTypography.secondary,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
    TradingRowDivider(inset = false)
}

@Composable
private fun WatchlistTabs(
    selectedTab: PersonalUniverseTab,
    watchlistCount: Int,
    positionCount: Int,
    onSelect: (PersonalUniverseTab) -> Unit,
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        color = MaterialTheme.colorScheme.background,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs),
            horizontalArrangement = Arrangement.spacedBy(AppSpacing.small),
        ) {
            FilterChip(
                selected = selectedTab == PersonalUniverseTab.WATCHLIST,
                onClick = { onSelect(PersonalUniverseTab.WATCHLIST) },
                label = { Text("自选股 $watchlistCount", style = CompactTypography.secondary) },
                modifier = Modifier.heightIn(min = AppSpacing.touchTarget),
                shape = MaterialTheme.shapes.small,
            )
            FilterChip(
                selected = selectedTab == PersonalUniverseTab.POSITIONS,
                onClick = { onSelect(PersonalUniverseTab.POSITIONS) },
                label = { Text("持仓股 $positionCount", style = CompactTypography.secondary) },
                modifier = Modifier.heightIn(min = AppSpacing.touchTarget),
                shape = MaterialTheme.shapes.small,
            )
        }
    }
    TradingRowDivider(inset = false)
}

@Composable
private fun WatchlistNotice(message: String, isError: Boolean, onRetry: (() -> Unit)? = null) {
    Surface(
        color = if (isError) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.secondaryContainer,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = AppSpacing.contentHorizontal, vertical = AppSpacing.xs),
        shape = MaterialTheme.shapes.small,
    ) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(horizontal = AppSpacing.medium, vertical = AppSpacing.small),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                message,
                Modifier.weight(1f),
                style = CompactTypography.secondary,
                color = if (isError) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSecondaryContainer,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            onRetry?.let {
                TextButton(
                    onClick = it,
                    modifier = Modifier.heightIn(min = AppSpacing.touchTarget),
                ) {
                    Text("重试", style = CompactTypography.secondary)
                }
            }
        }
    }
}

@Composable
internal fun WatchlistItemRow(
    item: PersonalUniverseItemDto,
    onClick: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    val colors = MaterialTheme.marketColors
    val change = item.change_percent
    val changeColor = when {
        change == null -> colors.neutral
        change > 0 -> colors.rise
        change < 0 -> colors.fall
        else -> colors.neutral
    }
    var menuExpanded by remember(item.symbol) { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = AppSpacing.rowHorizontal, vertical = AppSpacing.rowVertical),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        item.name.ifBlank { item.symbol },
                        style = CompactTypography.rowTitle,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (item.isPosition) {
                        Spacer(Modifier.width(AppSpacing.small))
                        DenseStateTag("持仓", MaterialTheme.colorScheme.primary)
                    }
                    priorityTag(item)?.let { (label, color) ->
                        Spacer(Modifier.width(AppSpacing.xs))
                        DenseStateTag(label, color)
                    }
                }
            }

            Text(
                text = item.last_price?.let { "%.2f".format(it) } ?: "--",
                style = CompactTypography.rowValue,
                textAlign = TextAlign.End,
                modifier = Modifier.width(72.dp),
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
            )

            Text(
                text = item.change_percent?.let {
                    "${if (it > 0) "+" else ""}${"%.2f".format(it)}%"
                } ?: "--",
                style = CompactTypography.rowValue,
                textAlign = TextAlign.End,
                modifier = Modifier.width(68.dp),
                color = changeColor,
                maxLines = 1,
            )

            Box(Modifier.size(AppSpacing.touchTarget), contentAlignment = Alignment.Center) {
                if (item.isWatchlist) {
                    IconButton(
                        onClick = { menuExpanded = true },
                        modifier = Modifier.size(AppSpacing.touchTarget),
                    ) {
                        Icon(
                            Icons.Default.MoreVert,
                            contentDescription = "管理${item.name}",
                            modifier = Modifier.size(AppSpacing.xLarge),
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    DropdownMenu(
                        expanded = menuExpanded,
                        onDismissRequest = { menuExpanded = false },
                    ) {
                        DropdownMenuItem(
                            text = { Text("编辑关注") },
                            leadingIcon = { Icon(Icons.Default.Edit, contentDescription = null) },
                            onClick = {
                                menuExpanded = false
                                onEdit()
                            },
                        )
                        DropdownMenuItem(
                            text = { Text("移出自选", color = MaterialTheme.colorScheme.error) },
                            leadingIcon = {
                                Icon(Icons.Default.Delete, contentDescription = null, tint = MaterialTheme.colorScheme.error)
                            },
                            onClick = {
                                menuExpanded = false
                                onDelete()
                            },
                        )
                    }
                }
            }
        }

        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = buildList {
                    add(item.symbol)
                    item.market?.takeIf { it.isNotBlank() }?.let(::add)
                    add(quoteDisplayLabel(item.quote_display_state))
                }.joinToString(" · "),
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )

            val reviewText = compactReviewText(item)
            if (reviewText.isNotBlank()) {
                Spacer(Modifier.width(AppSpacing.small))
                Text(
                    text = reviewText,
                    style = CompactTypography.caption,
                    color = reviewColor(item),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    textAlign = TextAlign.End,
                    modifier = Modifier.widthIn(max = 180.dp),
                )
            }
            Spacer(Modifier.width(AppSpacing.touchTarget))
        }

        val reason = item.review_reason_codes.firstOrNull()?.let(::compactReviewReasonLabel)
        val note = item.watchlist_note?.takeIf { it.isNotBlank() }
        val supporting = listOfNotNull(reason, note).joinToString(" · ")
        if (supporting.isNotBlank()) {
            Text(
                text = supporting,
                style = CompactTypography.caption,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.padding(top = AppSpacing.xxs, end = AppSpacing.touchTarget),
            )
        }
    }
    TradingRowDivider()
}

@Composable
private fun priorityTag(item: PersonalUniverseItemDto): Pair<String, androidx.compose.ui.graphics.Color>? {
    if (item.watchlist_enabled == false) {
        return "暂停" to MaterialTheme.colorScheme.outline
    }
    return when (item.watchlist_priority) {
        "CORE" -> "核心" to MaterialTheme.colorScheme.primary
        "FOCUS" -> "重点" to MaterialTheme.colorScheme.tertiary
        else -> null
    }
}

@Composable
private fun reviewColor(item: PersonalUniverseItemDto) = when (item.review_mode) {
    "FULL_RESEARCH" -> MaterialTheme.colorScheme.primary
    "POSITION_REVIEW" -> MaterialTheme.colorScheme.tertiary
    "GUARD_ONLY" -> MaterialTheme.colorScheme.onSurfaceVariant
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

private fun compactReviewText(item: PersonalUniverseItemDto): String {
    val mode = item.review_mode?.let(::compactReviewModeLabel) ?: "待生成复盘"
    val next = item.next_review_at?.let(::compactReviewTime)
    return listOfNotNull(mode, next).joinToString(" · ")
}

private fun compactReviewTime(value: String): String {
    val normalized = value.replace('T', ' ')
    return when {
        normalized.length >= 16 && normalized.getOrNull(4) == '-' -> normalized.substring(5, 16)
        normalized.length > 16 -> normalized.take(16)
        else -> normalized
    }
}

private fun quoteDisplayLabel(state: String): String = when (state) {
    "realtime" -> "实时"
    "close" -> "收盘"
    "stale" -> "延迟"
    "estimated" -> "暂估"
    "loading" -> "刷新中"
    "unavailable" -> "行情待同步"
    else -> state.ifBlank { "行情待同步" }
}

private fun compactReviewModeLabel(mode: String): String = when (mode) {
    "NO_REVIEW" -> "无需复盘"
    "GUARD_ONLY" -> "风险守护"
    "POSITION_REVIEW" -> "持仓复盘"
    "FULL_RESEARCH" -> "完整研究"
    else -> mode
}

private fun compactReviewReasonLabel(reason: String): String = when (reason) {
    "position_guard_monitoring" -> "持仓持续监控，无重大变化"
    "no_material_change" -> "没有重要变化"
    "position_review_due" -> "已到持仓复盘时间"
    "routine_full_research_budget_exhausted" -> "今日完整研究已执行"
    "material_change" -> "出现重要变化"
    "explicit_user_request" -> "用户主动请求"
    "hard_guard_obligation" -> "存在风险、事件或交易约束"
    else -> reason
}

internal fun reviewModeLabel(mode: String): String = when (mode) {
    "NO_REVIEW" -> "本轮无需复盘"
    "GUARD_ONLY" -> "仅监控风险与事件"
    "POSITION_REVIEW" -> "持仓复盘"
    "FULL_RESEARCH" -> "完整研究"
    else -> "复盘状态 $mode"
}

internal fun reviewReasonLabel(reason: String): String = when (reason) {
    "position_guard_monitoring" -> "原因：持仓持续监控，无重大变化"
    "no_material_change" -> "原因：没有重要变化"
    "position_review_due" -> "原因：已到持仓复盘时间"
    "routine_full_research_budget_exhausted" -> "原因：今日完整研究已执行"
    "material_change" -> "原因：出现重要变化"
    "explicit_user_request" -> "原因：用户主动请求"
    "hard_guard_obligation" -> "原因：存在风险、事件或交易约束"
    else -> "原因：$reason"
}

@Composable
private fun EmptyWatchlistPlaceholder(tab: PersonalUniverseTab) {
    Column(
        Modifier.fillMaxWidth().padding(vertical = 48.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            Icons.Default.StarOutline,
            contentDescription = null,
            modifier = Modifier.size(36.dp),
            tint = MaterialTheme.colorScheme.outlineVariant,
        )
        Spacer(Modifier.height(AppSpacing.medium))
        Text(
            if (tab == PersonalUniverseTab.WATCHLIST) {
                "暂无自选关注，点击右上角 + 开始添加"
            } else {
                "当前账户无持仓事实"
            },
            style = CompactTypography.secondary,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun WatchlistAddDialog(onDismiss: () -> Unit, onSelect: (SecurityCandidateDto) -> Unit) {
    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier.fillMaxWidth().heightIn(max = 600.dp),
            shape = MaterialTheme.shapes.large,
        ) {
            Column(Modifier.padding(vertical = AppSpacing.large)) {
                Row(
                    Modifier.padding(horizontal = AppSpacing.xxLarge).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
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
    onSave: (enabled: Boolean, priority: String, note: String) -> Unit,
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
                    Row(
                        Modifier.padding(top = AppSpacing.small),
                        horizontalArrangement = Arrangement.spacedBy(AppSpacing.small),
                    ) {
                        listOf("NORMAL" to "普通", "FOCUS" to "重点", "CORE" to "核心").forEach { (value, label) ->
                            FilterChip(
                                selected = priority == value,
                                onClick = { priority = value },
                                label = { Text(label) },
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("备忘信息") },
                    modifier = Modifier.fillMaxWidth(),
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
        },
    )
}
