package com.thirdhand.app.researchchat

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.OkHttpClient
import okhttp3.sse.EventSource
import java.util.UUID

/** Owns the page-bound stream and reuses a session while the selected holding is unchanged. */
class ResearchChatController(httpClient: OkHttpClient = OkHttpClient()) {
    private val repository = ResearchChatRepository(httpClient)
    private val mutableState = MutableStateFlow<ResearchChatUiState>(ResearchChatUiState.Idle)
    val state: StateFlow<ResearchChatUiState> = mutableState
    private var source: EventSource? = null
    private var activeSessionId: String? = null
    private var activeSymbol: String? = null

    fun send(baseUrl: String, message: String, symbol: String?) {
        if (activeSessionId != null && activeSymbol == symbol) {
            start(baseUrl, activeSessionId!!, message, symbol)
            return
        }
        mutableState.value = ResearchChatUiState.Streaming(phase = "正在创建研究会话")
        repository.createSession(baseUrl, symbol?.let { "$it 研究" } ?: "研究对话", symbol, { sessionId ->
            activeSessionId = sessionId
            activeSymbol = symbol
            start(baseUrl, sessionId, message, symbol)
        }) { error -> mutableState.value = ResearchChatUiState.Failed(error) }
    }

    private fun start(baseUrl: String, sessionId: String, message: String, symbol: String?) {
        source?.cancel()
        mutableState.value = ResearchChatUiState.Streaming()
        source = repository.stream(baseUrl, sessionId, message, symbol, UUID.randomUUID().toString(), ::handleEvent) { error ->
            mutableState.value = ResearchChatUiState.Failed(error)
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
            "tool_completed" -> mutableState.value = current.copy(activity = current.activity + "已完成：${event.data["tool_name"].orEmpty()}")
            "tool_failed" -> mutableState.value = current.copy(activity = current.activity + "读取失败：${event.data["tool_name"].orEmpty()}")
            "warning" -> mutableState.value = current.copy(activity = current.activity + (event.data["message"] ?: "研究警告"))
            "answer_delta" -> mutableState.value = current.copy(answer = current.answer + event.data["delta"].orEmpty())
            "usage" -> mutableState.value = current.copy(
                promptTokens = event.data["prompt_tokens"]?.toIntOrNull() ?: 0,
                completionTokens = event.data["completion_tokens"]?.toIntOrNull() ?: 0,
            )
            "done" -> mutableState.value = ResearchChatUiState.Completed(current.answer, event.data["can_continue"]?.toBoolean() == true, current.promptTokens, current.completionTokens)
            "error" -> mutableState.value = ResearchChatUiState.Failed(event.data["message"] ?: "研究流失败")
        }
    }
}
