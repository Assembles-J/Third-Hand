package com.thirdhand.app.researchchat

data class ResearchSseEvent(
    val protocol: String,
    val event: String,
    val data: Map<String, String>,
)

data class ResearchSessionSummary(
    val id: String,
    val title: String,
    val symbol: String?,
    val updatedAt: String,
)

data class ResearchStoredMessage(val user: Boolean, val text: String)

sealed interface ResearchChatUiState {
    data object Idle : ResearchChatUiState
    data class Streaming(
        val phase: String = "",
        val answer: String = "",
        val heartbeatSeen: Boolean = false,
        val activity: List<String> = emptyList(),
        val promptTokens: Int = 0,
        val completionTokens: Int = 0,
    ) : ResearchChatUiState
    data class Completed(val answer: String, val canContinue: Boolean = false, val promptTokens: Int = 0, val completionTokens: Int = 0) : ResearchChatUiState
    data class Failed(val message: String) : ResearchChatUiState
}
