package com.thirdhand.app.researchchat

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.OkHttpClient
import okhttp3.sse.EventSource
import java.util.UUID
import java.util.concurrent.TimeUnit
import org.json.JSONObject

/** Owns the page-bound stream and reuses a session while the selected holding is unchanged. */
class ResearchChatController(httpClient: OkHttpClient = OkHttpClient.Builder()
    .readTimeout(0, TimeUnit.MILLISECONDS)
    .writeTimeout(60, TimeUnit.SECONDS)
    .connectTimeout(20, TimeUnit.SECONDS)
    .build()) {
    private val repository = ResearchChatRepository(httpClient)
    private val mutableState = MutableStateFlow<ResearchChatUiState>(ResearchChatUiState.Idle)
    val state: StateFlow<ResearchChatUiState> = mutableState
    private var source: EventSource? = null
    private val answerBuffer = StringBuilder()
    private var lastAnswerPublishAt = 0L
    private var activeSessionId: String? = null
    private var activeSymbol: String? = null
    val currentSessionId: String? get() = activeSessionId
    val currentSymbol: String? get() = activeSymbol

    fun loadSessions(baseUrl: String, onReady: (List<ResearchSessionSummary>) -> Unit, onFailure: (String) -> Unit) = repository.sessions(baseUrl, onReady, onFailure)

    fun loadMessages(baseUrl: String, sessionId: String, onReady: (List<ResearchStoredMessage>) -> Unit, onFailure: (String) -> Unit) = repository.messages(baseUrl, sessionId, onReady, onFailure)
    fun loadSources(baseUrl: String, sessionId: String, onReady: (List<ResearchAttachedSource>) -> Unit, onFailure: (String) -> Unit) = repository.sources(baseUrl, sessionId, onReady, onFailure)
    fun saveSources(baseUrl: String, sessionId: String, sources: List<ResearchAttachedSource>) = repository.saveSources(baseUrl, sessionId, sources)
    fun loadDailyHistoryRefresh(baseUrl: String, sessionId: String, onReady: (DailyHistoryRefreshStatus) -> Unit, onFailure: (String) -> Unit) = repository.dailyHistoryRefresh(baseUrl, sessionId, onReady, onFailure)
    fun requestDailyHistoryRefresh(baseUrl: String, onReady: (DailyHistoryRefreshStatus) -> Unit, onFailure: (String) -> Unit) { activeSessionId?.let { repository.requestDailyHistoryRefresh(baseUrl, it, onReady, onFailure) } }

    fun selectSession(sessionId: String, symbol: String?) {
        activeSessionId = sessionId
        activeSymbol = symbol
        mutableState.value = ResearchChatUiState.Idle
    }

    fun beginNewResearch(symbol: String? = null) {
        activeSessionId = null
        activeSymbol = symbol
        mutableState.value = ResearchChatUiState.Idle
    }

    fun send(baseUrl: String, message: String, symbol: String?, onSessionReady: ((String) -> Unit)? = null) {
        if (activeSessionId != null && activeSymbol == symbol) {
            onSessionReady?.invoke(activeSessionId!!)
            start(baseUrl, activeSessionId!!, message, symbol)
            return
        }
        mutableState.value = ResearchChatUiState.Streaming(phase = "正在创建研究会话")
        repository.createSession(baseUrl, symbol?.let { "$it 研究" } ?: "研究对话", symbol, { sessionId ->
            activeSessionId = sessionId
            activeSymbol = symbol
            onSessionReady?.invoke(sessionId)
            start(baseUrl, sessionId, message, symbol)
        }) { error -> mutableState.value = ResearchChatUiState.Failed(error) }
    }

    private fun start(baseUrl: String, sessionId: String, message: String, symbol: String?) {
        source?.cancel()
        answerBuffer.clear()
        lastAnswerPublishAt = 0L
        mutableState.value = ResearchChatUiState.Streaming()
        source = repository.stream(baseUrl, sessionId, message, symbol, UUID.randomUUID().toString(), ::handleEvent) { error ->
            // OkHttp can report a socket close after the server has already sent `done`.
            // Do not overwrite a completed answer with that late transport callback.
            if (mutableState.value is ResearchChatUiState.Streaming) mutableState.value = ResearchChatUiState.Failed(error)
        }
    }

    fun cancel() {
        source?.cancel()
        source = null
        mutableState.value = ResearchChatUiState.Idle
    }

    fun reset() {
        cancel()
        activeSessionId = null
        activeSymbol = null
    }

    fun continueLast(baseUrl: String, symbol: String?) {
        val sessionId = activeSessionId ?: return
        if (activeSymbol != symbol) return
        start(baseUrl, sessionId, "请从上一段结束处继续，不要重复已经输出的内容。", symbol)
    }

    private fun handleEvent(event: ResearchSseEvent) {
        val current = mutableState.value as? ResearchChatUiState.Streaming ?: return
        when (event.event) {
            "phase" -> mutableState.value = current.copy(phase = event.data["label"].orEmpty())
            "heartbeat" -> mutableState.value = current.copy(heartbeatSeen = true)
            "tool_started" -> mutableState.value = current.copy(activity = current.activity + "正在读取：${event.data["tool_name"].orEmpty()}")
            "tool_completed" -> {
                val result = runCatching { JSONObject(event.data["result"].orEmpty()) }.getOrNull()
                val proposed = if (result?.optBoolean("confirmation_required") == true) {
                    if (result.optString("action") == "daily_history_refresh") ResearchSuggestedAction("daily_history_refresh", "拉取 60 天日线后继续", "") else {
                    val entity = result.optString("entity")
                    ResearchSuggestedAction("proposal:$entity", "确认${result.optString("operation")}：${result.optString("summary")}", "请继续说明该${entity}变更的确认条件和影响。")
                    }
                } else null
                mutableState.value = current.copy(activity = current.activity + "已完成：${event.data["tool_name"].orEmpty()}", suggestedActions = (current.suggestedActions + listOfNotNull(proposed)).distinctBy { it.id })
            }
            "tool_failed" -> mutableState.value = current.copy(activity = current.activity + "读取失败：${event.data["tool_name"].orEmpty()}")
            "warning" -> mutableState.value = current.copy(activity = current.activity + (event.data["message"] ?: "研究警告"))
            "answer_delta" -> {
                answerBuffer.append(event.data["delta"].orEmpty())
                val now = System.currentTimeMillis()
                // Markdown parsing is intentionally batched. Rendering every token causes
                // repeated full-layout passes that look like flickering on mobile.
                if (now - lastAnswerPublishAt >= 90L) {
                    lastAnswerPublishAt = now
                    mutableState.value = current.copy(answer = answerBuffer.toString())
                }
            }
            "usage" -> mutableState.value = current.copy(
                promptTokens = event.data["prompt_tokens"]?.toIntOrNull() ?: 0,
                completionTokens = event.data["completion_tokens"]?.toIntOrNull() ?: 0,
            )
            "decision" -> {
                val report = runCatching { JSONObject(event.data["decision_report"].orEmpty()) }.getOrNull()
                val action = report?.optString("action").orEmpty()
                val suggestions = buildList {
                    add(ResearchSuggestedAction("trade_plan", "查看并确认交易计划", "请依据本次研究结论，列出交易计划中需要我确认或补全的项目。"))
                    if (action in setOf("OPEN", "ADD", "REDUCE", "EXIT")) add(ResearchSuggestedAction("risk_rules", "核验仓位与风险约束", "请核验当前仓位、风险预算和计划上限；只列出需要我确认的修改项。"))
                }
                mutableState.value = current.copy(suggestedActions = suggestions)
            }
            "done" -> {
                source = null
                mutableState.value = ResearchChatUiState.Completed(answerBuffer.toString(), event.data["can_continue"]?.toBoolean() == true, current.promptTokens, current.completionTokens, current.suggestedActions)
            }
            "error" -> mutableState.value = ResearchChatUiState.Failed(event.data["message"] ?: "研究流失败")
        }
    }
}
