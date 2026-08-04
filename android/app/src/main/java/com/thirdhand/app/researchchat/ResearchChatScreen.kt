package com.thirdhand.app.researchchat

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.interaction.collectIsDraggedAsState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.ShowChart
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDrawerState
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.withFrameNanos
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ApiClient
import com.thirdhand.app.EndpointStore
import com.thirdhand.app.ResearchTargetDto
import kotlinx.coroutines.launch

data class ResearchChatLine(val user: Boolean, val text: String)

private val informationSources = listOf(
    "选择分析对象" to "持仓、观察标的或组合",
    "账户与持仓" to "成本、数量、现金与盈亏快照",
    "行情与 K 线" to "行情、日线、技术指标与风险",
    "交易计划与规则" to "已启用计划、仓位上限与风险边界",
    "公司公告与业绩" to "财报、业绩预告、分红、减持与回购",
    "新闻、事件与时间线" to "新闻、公告时间和风险事件",
    "行业与市场环境" to "行业强弱、市场状态与相对表现",
    "个人研究备注" to "后续支持文字、截图 OCR 与文件材料",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ResearchChatScreen(
    controller: ResearchChatController,
    conversation: List<ResearchChatLine>,
    onConversationChange: (List<ResearchChatLine>) -> Unit,
    question: String,
    onQuestionChange: (String) -> Unit,
    onOpenTradePlan: () -> Unit,
    onOpenPortfolio: () -> Unit,
    onOpenRules: () -> Unit,
    onClose: () -> Unit,
) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    val state by controller.state.collectAsState()
    val chatListState = rememberLazyListState()
    val isDraggingChat by chatListState.interactionSource.collectIsDraggedAsState()
    val isAtLatest by remember {
        derivedStateOf {
            val info = chatListState.layoutInfo
            val last = info.visibleItemsInfo.lastOrNull()
            info.totalItemsCount == 0 || (last != null && last.index == info.totalItemsCount - 1 && last.offset + last.size <= info.viewportEndOffset + 12)
        }
    }
    var followLatest by remember { mutableStateOf(true) }
    var wasDraggingChat by remember { mutableStateOf(false) }
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    var sessions by remember { mutableStateOf<List<ResearchSessionSummary>>(emptyList()) }
    var researchTargets by remember { mutableStateOf<List<ResearchTargetDto>>(emptyList()) }
    var selectedSymbol by remember { mutableStateOf<String?>(controller.currentSymbol) }
    var sourcePicker by remember { mutableStateOf(false) }
    var targetPicker by remember { mutableStateOf(false) }
    var attachedSources by remember { mutableStateOf<List<ResearchAttachedSource>>(emptyList()) }
    var loadError by remember { mutableStateOf<String?>(null) }
    var recordedAnswer by remember { mutableStateOf<String?>(null) }
    val targetNames = researchTargets.associate { it.symbol to it.name }
    var dailyHistoryRefresh by remember { mutableStateOf<DailyHistoryRefreshStatus?>(null) }

    fun refreshSessions() = controller.loadSessions(EndpointStore.baseUrl(context), { sessions = it }, { loadError = it })
    fun restoreSession(item: ResearchSessionSummary) {
        controller.selectSession(item.id, item.symbol)
        selectedSymbol = item.symbol
        controller.loadMessages(EndpointStore.baseUrl(context), item.id, { messages ->
            onConversationChange(messages.map { ResearchChatLine(it.user, it.text) })
            scope.launch { drawerState.close() }
        }, { loadError = it })
        controller.loadSources(EndpointStore.baseUrl(context), item.id, { attachedSources = it }, { loadError = it })
        controller.loadDailyHistoryRefresh(EndpointStore.baseUrl(context), item.id, { dailyHistoryRefresh = it }, { loadError = it })
    }
    fun send() {
        val value = question.trim()
        if (value.isBlank() || selectedSymbol == null || state is ResearchChatUiState.Streaming) return
        if (dailyHistoryRefresh?.status == "completed") dailyHistoryRefresh = null
        onConversationChange(conversation + ResearchChatLine(true, value))
        onQuestionChange("")
        recordedAnswer = null
        controller.send(EndpointStore.baseUrl(context), value, selectedSymbol) { sessionId ->
            controller.saveSources(EndpointStore.baseUrl(context), sessionId, attachedSources)
        }
        refreshSessions()
    }
    fun refreshContent() {
        val symbol = selectedSymbol ?: return
        scope.launch {
            loadError = null
            val result = runCatching {
                api.announcements(listOf(symbol))
                api.feed(listOf(symbol))
            }
            loadError = result.fold(
                onSuccess = { "公告和新闻已刷新；现在可继续研究以使用最新证据。" },
                onFailure = { "刷新公告和新闻失败，请稍后重试。" },
            )
        }
    }

    LaunchedEffect(Unit) {
        runCatching { ApiClient.service(context).researchTargets() }.onSuccess { researchTargets = it }.onFailure { loadError = "无法读取研究标的，请检查服务连接。" }
        refreshSessions()
    }
    LaunchedEffect(state) {
        when (val current = state) {
            is ResearchChatUiState.Completed -> if (current.answer.isNotBlank() && recordedAnswer != current.answer) {
                onConversationChange(conversation + ResearchChatLine(false, current.answer)); recordedAnswer = current.answer; refreshSessions()
            }
            is ResearchChatUiState.Failed -> if (recordedAnswer != current.message) {
                onConversationChange(conversation + ResearchChatLine(false, "本次研究未完成：${current.message}")); recordedAnswer = current.message; refreshSessions()
            }
            else -> Unit
        }
    }
    LaunchedEffect(isDraggingChat) {
        // Stop following as soon as the reader takes control. It resumes only
        // after they intentionally return to the bottom of the latest card.
        if (isDraggingChat) followLatest = false
        if (wasDraggingChat && !isDraggingChat) followLatest = isAtLatest
        wasDraggingChat = isDraggingChat
    }
    LaunchedEffect(conversation.size, (state as? ResearchChatUiState.Streaming)?.answer?.length, state is ResearchChatUiState.Completed) {
        if (followLatest && chatListState.layoutInfo.totalItemsCount > 0) {
            withFrameNanos { }
            chatListState.scrollToItem(chatListState.layoutInfo.totalItemsCount - 1, Int.MAX_VALUE)
        }
    }
    BackHandler(onBack = onClose)

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet {
                Column(Modifier.padding(16.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("研究会话", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Button(onClick = {
                        controller.beginNewResearch(); selectedSymbol = null; attachedSources = emptyList(); onConversationChange(emptyList()); onQuestionChange(""); scope.launch { drawerState.close() }
                    }, modifier = Modifier.fillMaxWidth()) { Text("+ 新建研究") }
                    HorizontalDivider()
                    if (sessions.isEmpty()) Text("还没有已保存的研究会话。", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    sessions.sortedByDescending { it.updatedAt }.groupBy { it.symbol ?: "综合研究" }.forEach { (symbol, groupedSessions) ->
                        Text(if (symbol == "综合研究") symbol else "${targetNames[symbol] ?: symbol} · $symbol", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.primary)
                        groupedSessions.forEach { item ->
                        TextButton(onClick = { restoreSession(item) }, modifier = Modifier.fillMaxWidth()) {
                            Column(Modifier.fillMaxWidth()) {
                                Text(item.title, maxLines = 2, overflow = TextOverflow.Ellipsis, fontWeight = if (item.id == controller.currentSessionId) FontWeight.Bold else FontWeight.Normal)
                                Text("${item.symbol ?: "综合研究"} · ${item.updatedAt.replace("T", " ").take(16)}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        }
                    }
                }
            }
        },
    ) {
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 8.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onClose) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "暂时关闭研究") }
                Column(Modifier.weight(1f)) {
                    Text("研究", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(selectedSymbol ?: "新建会话", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = { scope.launch { drawerState.open() } }) { Icon(Icons.Filled.Menu, "管理历史会话") }
            }
            HorizontalDivider()
            loadError?.let { Text(it, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error) }
            LazyColumn(Modifier.weight(1f), state = chatListState, contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 12.dp, bottom = 112.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                if (conversation.isEmpty()) item { EmptyResearchHint(onChooseTarget = { targetPicker = true }, onPreset = onQuestionChange) }
                items(conversation) { ChatBubble(it) }
                if (state is ResearchChatUiState.Streaming) item { StreamingCard(state as ResearchChatUiState.Streaming) }
                (state as? ResearchChatUiState.Completed)?.takeIf { it.canContinue }?.let {
                    item { Button(onClick = { controller.continueLast(EndpointStore.baseUrl(context), selectedSymbol) }, modifier = Modifier.fillMaxWidth()) { Text("继续生成") } }
                }
                (state as? ResearchChatUiState.Completed)?.suggestedActions?.takeIf { it.isNotEmpty() }?.let { actions ->
                    item { SuggestedActionCard(actions, onQuestionChange, onOpenTradePlan, onOpenPortfolio, onOpenRules, ::refreshContent) {
                        controller.requestDailyHistoryRefresh(EndpointStore.baseUrl(context), { dailyHistoryRefresh = it }, { loadError = it })
                    } }
                }
                dailyHistoryRefresh?.let { refresh -> item {
                    DailyHistoryRefreshCard(refresh, onRequest = {
                        val onReady = { item: DailyHistoryRefreshStatus -> dailyHistoryRefresh = item }
                        if (refresh.status == "running" || refresh.status == "queued") controller.currentSessionId?.let { controller.loadDailyHistoryRefresh(EndpointStore.baseUrl(context), it, onReady, { loadError = it }) }
                        else controller.requestDailyHistoryRefresh(EndpointStore.baseUrl(context), onReady, { loadError = it })
                    }, onContinue = {
                        dailyHistoryRefresh = null
                        val continuation = "日线补齐任务已完成，请基于最新的 60 天日线继续上一次研究，不要重复已有内容。"
                        onConversationChange(conversation + ResearchChatLine(true, continuation))
                        controller.send(EndpointStore.baseUrl(context), continuation, selectedSymbol)
                    })
                } }
            }
            HorizontalDivider()
            Column(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (attachedSources.isNotEmpty()) LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(attachedSources) { source -> AssistChip(onClick = {}, label = { Text(source.title, maxLines = 1) }) }
                }
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    IconButton(onClick = { sourcePicker = true }, enabled = state !is ResearchChatUiState.Streaming) { Icon(Icons.Filled.Add, "添加分析信息源") }
                    OutlinedTextField(question, onQuestionChange, Modifier.weight(1f), label = { Text(if (selectedSymbol == null) "先用 + 选择分析对象" else "继续提问") }, maxLines = 3, enabled = selectedSymbol != null && state !is ResearchChatUiState.Streaming)
                    Button(onClick = ::send, enabled = question.isNotBlank() && selectedSymbol != null && state !is ResearchChatUiState.Streaming) { Text("发送") }
                }
            }
        }
    }
    if (sourcePicker) ModalBottomSheet(onDismissRequest = { sourcePicker = false }) {
        Column(Modifier.padding(horizontal = 20.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("添加分析信息", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            informationSources.forEach { (title, detail) ->
                TextButton(onClick = { if (title == "选择分析对象") targetPicker = true else { attachedSources = (attachedSources + ResearchAttachedSource(title, title, detail)).distinctBy { it.key }; controller.currentSessionId?.let { controller.saveSources(EndpointStore.baseUrl(context), it, attachedSources) }; sourcePicker = false } }, modifier = Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth()) { Text(title, fontWeight = FontWeight.SemiBold); Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
            }
        }
    }
    if (targetPicker) AlertDialog(onDismissRequest = { targetPicker = false }, title = { Text("选择分析对象") }, text = {
        Column { researchTargets.forEach { target ->
            TextButton(onClick = { selectedSymbol = target.symbol; controller.beginNewResearch(); onConversationChange(emptyList()); attachedSources = listOf(ResearchAttachedSource("target:${target.symbol}", "分析对象 · ${target.name}", target.symbol)); targetPicker = false }, modifier = Modifier.fillMaxWidth()) {
                Icon(researchTargetIcon(target.status), contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                Column(Modifier.padding(start = 12.dp).weight(1f)) {
                    Text(target.name, fontWeight = FontWeight.SemiBold)
                    Text("${target.symbol}${if (target.status == "closed_position") " · 已清仓跟踪" else ""}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        } }
    }, confirmButton = { TextButton(onClick = { targetPicker = false }) { Text("取消") } })
}

private fun researchTargetIcon(status: String) = when (status) {
    "active_holding" -> Icons.Filled.AccountBalanceWallet
    "closed_position" -> Icons.Filled.ShowChart
    else -> Icons.Filled.Bookmark
}

@OptIn(ExperimentalLayoutApi::class)
@Composable private fun EmptyResearchHint(onChooseTarget: () -> Unit, onPreset: (String) -> Unit) = Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { Text("从一个研究问题开始", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold); Text("点 + 选择分析对象和需要带入的资料。系统会自动带入行情、K 线、持仓、交易计划、规则、公告和事件证据。", style = MaterialTheme.typography.bodyMedium); FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { listOf("给出当前仓位与风险建议", "核验行业逻辑与业绩变化", "识别关键事件和时间窗口", "复盘交易计划是否仍成立").forEach { prompt -> AssistChip(onClick = { onPreset(prompt) }, label = { Text(prompt, maxLines = 1, overflow = TextOverflow.Ellipsis) }) } }; TextButton(onClick = onChooseTarget) { Text("选择分析对象") } } }
@Composable private fun StreamingCard(state: ResearchChatUiState.Streaming) = Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) { Text(state.phase.ifBlank { "正在后台分析…" }, fontWeight = FontWeight.SemiBold); state.activity.takeLast(1).forEach { Text(it, style = MaterialTheme.typography.labelSmall) }; if (state.answer.isNotBlank()) StreamingResearchText(state.answer) } }
@Composable private fun ChatBubble(line: ResearchChatLine) = Column(Modifier.fillMaxWidth(), horizontalAlignment = if (line.user) Alignment.End else Alignment.Start) { Card(colors = CardDefaults.cardColors(containerColor = if (line.user) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant), modifier = Modifier.fillMaxWidth(if (line.user) .9f else 1f)) { if (line.user) Text(line.text, Modifier.padding(14.dp), style = MaterialTheme.typography.bodySmall) else ResearchMarkdown(line.text, Modifier.padding(14.dp)) } }
@Composable private fun SuggestedActionCard(actions: List<ResearchSuggestedAction>, onQuestionChange: (String) -> Unit, onOpenTradePlan: () -> Unit, onOpenPortfolio: () -> Unit, onOpenRules: () -> Unit, onRefreshContent: () -> Unit, onRequestDailyHistory: () -> Unit) = Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { Text("下一步操作", fontWeight = FontWeight.SemiBold); Text("按钮由 AI 建议映射到受限操作；不会自动交易或直接修改持仓。", style = MaterialTheme.typography.bodySmall); actions.forEach { action -> Button(onClick = { when (action.id) { "trade_plan", "risk_rules" -> onOpenTradePlan(); "daily_history_refresh" -> onRequestDailyHistory(); "account_cash" -> onOpenPortfolio(); "personal_rules" -> onOpenRules(); "content_refresh" -> onRefreshContent(); else -> onQuestionChange(action.prompt) } }, modifier = Modifier.fillMaxWidth()) { Text(action.label) } } } }

@Composable private fun DailyHistoryRefreshCard(refresh: DailyHistoryRefreshStatus, onRequest: () -> Unit, onContinue: () -> Unit) = Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) { Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) { Text("60 天日线补齐", fontWeight = FontWeight.SemiBold); Text("${refresh.symbol}：${refresh.barCount}/${refresh.requiredDays} 条 · ${when (refresh.status) { "completed" -> "已完成"; "running", "queued" -> "后台处理中，可退出后稍后回来"; "failed" -> "拉取失败，可重试"; else -> "尚未请求" }}", style = MaterialTheme.typography.bodySmall); refresh.errorMessage?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.labelSmall) }; if (refresh.status == "completed") TextButton(onClick = onContinue) { Text("继续研究") } else TextButton(onClick = onRequest) { Text(if (refresh.status == "running" || refresh.status == "queued") "重新检查状态" else "拉取日线") } } }
