package com.thirdhand.app.researchchat

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.interaction.collectIsDraggedAsState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
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
import com.thirdhand.app.ApiClient
import com.thirdhand.app.EndpointStore
import com.thirdhand.app.ResearchTargetDto
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.theme.AppSpacing
import com.thirdhand.app.ui.theme.marketColors
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
)

@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun ResearchChatScreen(
    controller: ResearchChatController,
    conversation: List<ResearchChatLine>,
    onConversationChange: (List<ResearchChatLine>) -> Unit,
    question: String,
    onQuestionChange: (String) -> Unit,
    initialTarget: ResearchTargetDto? = null,
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
            info.totalItemsCount == 0 || (last != null && last.index == info.totalItemsCount - 1)
        }
    }
    var followLatest by remember { mutableStateOf(true) }
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    var sessions by remember { mutableStateOf<List<ResearchSessionSummary>>(emptyList()) }
    var researchTargets by remember { mutableStateOf<List<ResearchTargetDto>>(emptyList()) }
    var selectedSymbol by remember(initialTarget?.symbol) { mutableStateOf(initialTarget?.symbol ?: controller.currentSymbol) }
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
        onConversationChange(conversation + ResearchChatLine(true, value))
        onQuestionChange("")
        recordedAnswer = null
        controller.send(EndpointStore.baseUrl(context), value, selectedSymbol) { sessionId ->
            controller.saveSources(EndpointStore.baseUrl(context), sessionId, attachedSources)
        }
        refreshSessions()
    }

    LaunchedEffect(Unit) {
        runCatching { ApiClient.service(context).researchTargets() }.onSuccess { researchTargets = it }
        refreshSessions()
    }

    LaunchedEffect(initialTarget?.symbol) {
        initialTarget?.let { target ->
            selectedSymbol = target.symbol
            controller.beginNewResearch(target.symbol)
            attachedSources = listOf(ResearchAttachedSource("target:${target.symbol}", "分析对象 · ${target.name}", target.symbol))
        }
    }

    LaunchedEffect(state) {
        when (val current = state) {
            is ResearchChatUiState.Completed -> if (current.answer.isNotBlank() && recordedAnswer != current.answer) {
                onConversationChange(conversation + ResearchChatLine(false, current.answer)); recordedAnswer = current.answer; refreshSessions()
            }
            is ResearchChatUiState.Failed -> if (recordedAnswer != current.message) {
                onConversationChange(conversation + ResearchChatLine(false, "研究中断：${current.message}")); recordedAnswer = current.message
            }
            else -> Unit
        }
    }

    LaunchedEffect(conversation.size, (state as? ResearchChatUiState.Streaming)?.answer?.length) {
        if (followLatest && chatListState.layoutInfo.totalItemsCount > 0) {
            chatListState.animateScrollToItem(chatListState.layoutInfo.totalItemsCount - 1)
        }
    }

    BackHandler(onBack = onClose)

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet(
                drawerContainerColor = MaterialTheme.colorScheme.surface,
                drawerShape = RoundedCornerShape(topEnd = 16.dp, bottomEnd = 16.dp)
            ) {
                Column(Modifier.fillMaxHeight().padding(AppSpacing.large)) {
                    Text("研究档案库", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.ExtraBold)
                    Spacer(Modifier.height(AppSpacing.large))
                    Button(
                        onClick = {
                            controller.beginNewResearch(); selectedSymbol = null; attachedSources = emptyList(); onConversationChange(emptyList()); onQuestionChange(""); scope.launch { drawerState.close() }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = MaterialTheme.shapes.medium
                    ) {
                        Icon(Icons.Default.Add, null)
                        Spacer(Modifier.width(AppSpacing.small))
                        Text("开启新深度研究")
                    }
                    Spacer(Modifier.height(AppSpacing.large))
                    HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant)

                    LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(vertical = AppSpacing.medium)) {
                        val grouped = sessions.sortedByDescending { it.updatedAt }.groupBy { it.symbol ?: "综合" }
                        grouped.forEach { (symbol, sessionList) ->
                            item {
                                Text(
                                    if(symbol=="综合") "全局研究" else "${targetNames[symbol] ?: symbol}",
                                    Modifier.padding(vertical = AppSpacing.small),
                                    style = MaterialTheme.typography.labelMedium,
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary
                                )
                            }
                            items(sessionList) { item ->
                                Surface(
                                    modifier = Modifier.fillMaxWidth().padding(vertical = 2.dp).clickable { restoreSession(item) },
                                    color = if (item.id == controller.currentSessionId) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f) else Color.Transparent,
                                    shape = MaterialTheme.shapes.small
                                ) {
                                    Column(Modifier.padding(AppSpacing.medium)) {
                                        Text(item.title, maxLines = 1, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodyMedium, fontWeight = if (item.id == controller.currentSessionId) FontWeight.Bold else FontWeight.Normal)
                                        Text(item.updatedAt.take(10), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        },
    ) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = {
                        Column {
                            Text("AI 研究室", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            Text(selectedSymbol ?: "准备就绪", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    },
                    navigationIcon = {
                        IconButton(onClick = onClose) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) }
                    },
                    actions = {
                        IconButton(onClick = { scope.launch { drawerState.open() } }) { Icon(Icons.Default.Menu, null) }
                    },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.surface)
                )
            },
            bottomBar = {
                InputArea(
                    question = question,
                    onQuestionChange = onQuestionChange,
                    attachedSources = attachedSources,
                    streaming = state is ResearchChatUiState.Streaming,
                    onAddSource = { sourcePicker = true },
                    onSend = ::send
                )
            }
        ) { padding ->
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(padding).background(MaterialTheme.colorScheme.background),
                state = chatListState,
                contentPadding = PaddingValues(AppSpacing.xxLarge),
                verticalArrangement = Arrangement.spacedBy(AppSpacing.large)
            ) {
                if (conversation.isEmpty()) {
                    item { EmptyHint(onChoose = { targetPicker = true }, onPreset = onQuestionChange) }
                }

                items(conversation) { line ->
                    ChatBubble(line)
                }

                if (state is ResearchChatUiState.Streaming) {
                    item { StreamingCard(state as ResearchChatUiState.Streaming) }
                }

                val completed = state as? ResearchChatUiState.Completed
                if (completed != null && completed.suggestedActions.isNotEmpty()) {
                    item {
                        ActionSuggestions(
                            actions = completed.suggestedActions,
                            onPreset = onQuestionChange,
                            onOpenPlan = onOpenTradePlan,
                            onOpenPortfolio = onOpenPortfolio,
                            onOpenRules = onOpenRules
                        )
                    }
                }

                if (dailyHistoryRefresh != null) {
                    item { DailyRefreshCard(dailyHistoryRefresh!!, onContinue = { dailyHistoryRefresh = null }) }
                }
            }
        }
    }

    if (sourcePicker) {
        ModalBottomSheet(onDismissRequest = { sourcePicker = false }) {
            Column(Modifier.padding(AppSpacing.xxLarge).padding(bottom = 32.dp)) {
                Text("深度研究：资料装载", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(AppSpacing.large))
                informationSources.forEach { (title, detail) ->
                    ListItem(
                        headlineContent = { Text(title, fontWeight = FontWeight.Bold) },
                        supportingContent = { Text(detail) },
                        modifier = Modifier.clickable {
                            if (title == "选择分析对象") targetPicker = true
                            else {
                                attachedSources = (attachedSources + ResearchAttachedSource(title, title, detail)).distinctBy { it.key }
                                sourcePicker = false
                            }
                        }
                    )
                }
            }
        }
    }

    if (targetPicker) {
        AlertDialog(
            onDismissRequest = { targetPicker = false },
            title = { Text("选择研究标的") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState())) {
                    researchTargets.forEach { target ->
                        ListItem(
                            headlineContent = { Text(target.name, fontWeight = FontWeight.Bold) },
                            supportingContent = { Text(target.symbol) },
                            leadingContent = { Icon(Icons.Default.Bookmark, null, tint = MaterialTheme.colorScheme.primary) },
                            modifier = Modifier.clickable {
                                selectedSymbol = target.symbol
                                controller.beginNewResearch(target.symbol)
                                onConversationChange(emptyList())
                                attachedSources = listOf(ResearchAttachedSource("target:${target.symbol}", "分析对象 · ${target.name}", target.symbol))
                                targetPicker = false
                                sourcePicker = false
                            }
                        )
                    }
                }
            },
            confirmButton = { TextButton(onClick = { targetPicker = false }) { Text("取消") } }
        )
    }
}

@Composable
private fun ChatBubble(line: ResearchChatLine) {
    val isUser = line.user
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        Surface(
            color = if (isUser) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
            shape = RoundedCornerShape(
                topStart = 16.dp,
                topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 2.dp,
                bottomEnd = if (isUser) 2.dp else 16.dp
            ),
            tonalElevation = if (isUser) 0.dp else 1.dp,
            modifier = Modifier.fillMaxWidth(if (isUser) 0.85f else 1f)
        ) {
            Box(Modifier.padding(AppSpacing.large)) {
                if (isUser) {
                    Text(line.text, color = Color.White, style = MaterialTheme.typography.bodyMedium)
                } else {
                    ResearchMarkdown(line.text)
                }
            }
        }
    }
}

@Composable
private fun StreamingCard(state: ResearchChatUiState.Streaming) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f)),
        shape = MaterialTheme.shapes.large
    ) {
        Column(Modifier.padding(AppSpacing.large)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(AppSpacing.medium))
                Text(state.phase.ifBlank { "思考中..." }, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
            }
            if (state.answer.isNotBlank()) {
                Spacer(Modifier.height(AppSpacing.medium))
                StreamingResearchText(state.answer)
            }
        }
    }
}

@Composable
private fun InputArea(
    question: String,
    onQuestionChange: (String) -> Unit,
    attachedSources: List<ResearchAttachedSource>,
    streaming: Boolean,
    onAddSource: () -> Unit,
    onSend: () -> Unit
) {
    Surface(
        tonalElevation = 8.dp,
        color = MaterialTheme.colorScheme.surface,
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(Modifier.padding(AppSpacing.large)) {
            if (attachedSources.isNotEmpty()) {
                LazyRow(
                    modifier = Modifier.padding(bottom = AppSpacing.small),
                    horizontalArrangement = Arrangement.spacedBy(AppSpacing.small)
                ) {
                    items(attachedSources) { source ->
                        AssistChip(
                            onClick = {},
                            label = { Text(source.title, style = MaterialTheme.typography.labelSmall) },
                            shape = CircleShape
                        )
                    }
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onAddSource, enabled = !streaming) {
                    Icon(Icons.Default.AddCircleOutline, null, tint = MaterialTheme.colorScheme.primary)
                }
                TextField(
                    value = question,
                    onValueChange = onQuestionChange,
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("追问、要求核验或下结论...", style = MaterialTheme.typography.bodyMedium) },
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = Color.Transparent,
                        unfocusedContainerColor = Color.Transparent,
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent
                    ),
                    maxLines = 4,
                    enabled = !streaming
                )
                IconButton(onClick = onSend, enabled = question.isNotBlank() && !streaming) {
                    Icon(Icons.Default.Send, null, tint = if(question.isNotBlank()) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun EmptyHint(onChoose: () -> Unit, onPreset: (String) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(AppSpacing.large)) {
        Text("AI 深度研究框架", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
        Text("在这里，AI 将调取真实的行情、研报和个人规则进行交叉核验。请先选择一个研究对象：", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)

        Button(onClick = onChoose, modifier = Modifier.fillMaxWidth(), shape = MaterialTheme.shapes.medium) {
            Text("选择分析标的")
        }

        Text("或尝试这些研究入口：", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(AppSpacing.small), verticalArrangement = Arrangement.spacedBy(AppSpacing.small)) {
            listOf("给出当前仓位与风险建议", "核验行业逻辑与业绩变化", "识别关键事件和时间窗口").forEach { prompt ->
                AssistChip(onClick = { onPreset(prompt) }, label = { Text(prompt) })
            }
        }
    }
}

@Composable
private fun ActionSuggestions(
    actions: List<ResearchSuggestedAction>,
    onPreset: (String) -> Unit,
    onOpenPlan: () -> Unit,
    onOpenPortfolio: () -> Unit,
    onOpenRules: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.3f), MaterialTheme.shapes.large)
            .padding(AppSpacing.large),
        verticalArrangement = Arrangement.spacedBy(AppSpacing.small)
    ) {
        Text("AI 建议的后续操作", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold, color = MaterialTheme.colorScheme.secondary)
        actions.forEach { action ->
            OutlinedButton(
                onClick = {
                    when(action.id) {
                        "trade_plan" -> onOpenPlan()
                        "account_cash" -> onOpenPortfolio()
                        "personal_rules" -> onOpenRules()
                        else -> onPreset(action.prompt)
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                shape = MaterialTheme.shapes.small
            ) {
                Text(action.label, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun DailyRefreshCard(refresh: DailyHistoryRefreshStatus, onContinue: () -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.5f),
        shape = MaterialTheme.shapes.large,
        modifier = Modifier.fillMaxWidth()
    ) {
        Row(Modifier.padding(AppSpacing.large), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.CheckCircle, null, tint = MaterialTheme.marketColors.rise)
            Spacer(Modifier.width(AppSpacing.medium))
            Column(Modifier.weight(1f)) {
                Text("日线数据补齐成功", style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Bold)
                Text("已获取最新的 60 天 K 线数据", style = MaterialTheme.typography.labelSmall)
            }
            TextButton(onClick = onContinue) { Text("继续分析") }
        }
    }
}
