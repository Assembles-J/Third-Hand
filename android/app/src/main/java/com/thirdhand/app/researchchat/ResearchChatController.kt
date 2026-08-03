package com.thirdhand.app.researchchat

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import okhttp3.OkHttpClient
import okhttp3.sse.EventSource
import java.util.UUID

/** Owns the page-bound stream; closing the page always closes its HTTP stream. */
class ResearchChatController(httpClient: OkHttpClient = OkHttpClient()) {
    private val repository = ResearchChatRepository(httpClient)
    private val mutableState = MutableStateFlow<ResearchChatUiState>(ResearchChatUiState.Idle)
    val state: StateFlow<ResearchChatUiState> = mutableState
    private var source: EventSource? = null

    fun start(baseUrl: String, sessionId: String, message: String, symbol: String?) {
        source?.cancel()
        mutableState.value = ResearchChatUiState.Streaming()
        source = repository.stream(baseUrl, sessionId, message, symbol, UUID.randomUUID().toString(), ::handleEvent) { error ->
            mutableState.value = ResearchChatUiState.Failed(error)
        }
    }

    fun createAndStart(baseUrl: String, message: String, symbol: String?) {
        mutableState.value = ResearchChatUiState.Streaming(phase = "正在创建研究会话")
        repository.createSession(baseUrl, symbol?.let { "$it 研究" } ?: "研究对话", symbol, { sessionId ->
            start(baseUrl, sessionId, message, symbol)
        }) { error -> mutableState.value = ResearchChatUiState.Failed(error) }
    }

    fun cancel() {
        source?.cancel()
        source = null
        mutableState.value = ResearchChatUiState.Idle
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
            "done" -> mutableState.value = ResearchChatUiState.Completed(current.answer)
            "error" -> mutableState.value = ResearchChatUiState.Failed(event.data["message"] ?: "研究流失败")
        }
    }
}
