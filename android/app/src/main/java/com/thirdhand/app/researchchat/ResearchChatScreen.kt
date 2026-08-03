package com.thirdhand.app.researchchat

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ApiClient
import com.thirdhand.app.EndpointStore
import com.thirdhand.app.HoldingDto
import kotlinx.coroutines.launch

private data class ChatLine(val user: Boolean, val text: String)

private val researchPresets = listOf(
    "分析当前行情、持仓成本、技术面和风险，说明现状与下一步关注点。",
    "这只票当前趋势如何？请列出支持与削弱判断的关键证据。",
    "我的持仓目前主要风险是什么？什么情况需要重新复核？",
    "结合近期事件和市场环境，哪些变化最值得跟踪？",
)

@Composable
private fun ResearchChatStreamStatus(controller: ResearchChatController) {
    val state by controller.state.collectAsState()
    BackHandler(enabled = state is ResearchChatUiState.Streaming) { controller.cancel() }
    val current = state as? ResearchChatUiState.Streaming ?: return
    Text(current.phase.ifBlank { "正在进行研究分析" }, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
    current.activity.takeLast(3).forEach { Text(it, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
    if (current.answer.isNotBlank()) ResearchMarkdown(current.answer)
    TextButton(onClick = controller::cancel) { Text("取消") }
}

@Composable
fun ResearchChatScreen() {
    val context = LocalContext.current
    val controller = remember { ResearchChatController() }
    val state by controller.state.collectAsState()
    val scope = rememberCoroutineScope()
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var selectedSymbol by remember { mutableStateOf<String?>(null) }
    var question by remember { mutableStateOf("") }
    var loadError by remember { mutableStateOf<String?>(null) }
    var conversation by remember { mutableStateOf<List<ChatLine>>(emptyList()) }
    var recordedAnswer by remember { mutableStateOf<String?>(null) }

    fun loadHoldings() = scope.launch {
        loadError = null
        runCatching { ApiClient.service(context).holdings() }
            .onSuccess { loaded ->
                holdings = loaded
                if (selectedSymbol !in loaded.map { it.symbol }) selectedSymbol = loaded.firstOrNull()?.symbol
            }
            .onFailure { loadError = "无法读取持仓，请检查服务连接后重试。" }
    }
    fun send(text: String) {
        val value = text.trim()
        if (value.isBlank() || selectedSymbol == null || state is ResearchChatUiState.Streaming) return
        conversation = conversation + ChatLine(true, value)
        question = ""
        recordedAnswer = null
        controller.send(EndpointStore.baseUrl(context), value, selectedSymbol)
    }

    LaunchedEffect(Unit) { loadHoldings() }
    LaunchedEffect(state) {
        when (val current = state) {
            is ResearchChatUiState.Completed -> if (current.answer.isNotBlank() && recordedAnswer != current.answer) {
                conversation = conversation + ChatLine(false, current.answer)
                recordedAnswer = current.answer
            }
            is ResearchChatUiState.Failed -> if (recordedAnswer != current.message) {
                conversation = conversation + ChatLine(false, "本次研究未完成：${current.message}")
                recordedAnswer = current.message
            }
            else -> Unit
        }
    }

    val selectedHolding = holdings.firstOrNull { it.symbol == selectedSymbol }
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface)) {
        Column(Modifier.padding(horizontal = 20.dp, vertical = 16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("持仓研究", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                    Text("从你的持仓与当下行情出发，逐步问清一只票。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                TextButton(onClick = { controller.reset(); conversation = emptyList(); loadHoldings() }) { Text("刷新") }
            }
            if (holdings.isNotEmpty()) {
                Text("选择持仓", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(vertical = 2.dp)) {
                    items(holdings, key = { it.id }) { holding ->
                        FilterChip(
                            selected = holding.symbol == selectedSymbol,
                            onClick = { selectedSymbol = holding.symbol; controller.reset(); conversation = emptyList() },
                            label = { Text("${holding.name} · ${holding.symbol}") },
                        )
                    }
                }
                selectedHolding?.let { Text("已选 ${it.name}，成本 ${it.average_cost}，持有 ${it.quantity} 股", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary) }
            } else {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                    Text("尚未读取到持仓。请先在“持仓”页添加证券，研究页会自动列出可分析对象。", Modifier.padding(12.dp), style = MaterialTheme.typography.bodySmall)
                }
            }
            loadError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        }
        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)

        LazyColumn(Modifier.weight(1f), contentPadding = PaddingValues(20.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (conversation.isEmpty()) {
                item {
                    Text("从一个具体问题开始", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text("默认问题围绕已选持仓的行情、风险、事件和持仓状态，无需再输入证券代码。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                items(researchPresets) { preset ->
                    AssistChip(onClick = { question = preset }, label = { Text(preset) }, colors = AssistChipDefaults.assistChipColors(containerColor = MaterialTheme.colorScheme.surfaceVariant))
                }
            }
            items(conversation) { line -> ChatBubble(line) }
            val completed = state as? ResearchChatUiState.Completed
            if (completed != null && (completed.promptTokens > 0 || completed.completionTokens > 0)) item {
                Text("本段用量：输入 ${completed.promptTokens} · 输出 ${completed.completionTokens} tokens", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (completed?.canContinue == true) item {
                Button(
                    onClick = { controller.continueLast(EndpointStore.baseUrl(context), selectedSymbol) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("继续生成下一段") }
            }
            if (state is ResearchChatUiState.Streaming) item {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) { ResearchChatStreamStatus(controller) }
                }
            }
        }

        HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = question,
                onValueChange = { question = it },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
                maxLines = 4,
                label = { Text(if (selectedHolding == null) "请先选择一只持仓" else "问问 ${selectedHolding.name} 的现状") },
                enabled = selectedHolding != null && state !is ResearchChatUiState.Streaming,
            )
            Button(onClick = { send(question) }, enabled = question.isNotBlank() && selectedHolding != null && state !is ResearchChatUiState.Streaming, modifier = Modifier.fillMaxWidth()) { Text("发送研究问题") }
            Text("研究仅用于解释和复核，不会自动交易。", modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ChatBubble(line: ChatLine) {
    val alignment = if (line.user) Alignment.End else Alignment.Start
    val color = if (line.user) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant
    Column(Modifier.fillMaxWidth(), horizontalAlignment = alignment) {
        Card(colors = CardDefaults.cardColors(containerColor = color), modifier = Modifier.fillMaxWidth(0.88f)) {
            if (line.user) Text(line.text, Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium)
            else ResearchMarkdown(line.text, Modifier.padding(12.dp))
        }
    }
}
