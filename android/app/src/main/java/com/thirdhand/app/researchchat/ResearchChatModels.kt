package com.thirdhand.app.researchchat

data class ResearchSseEvent(
    val protocol: String,
    val event: String,
    val data: Map<String, String>,
)

sealed interface ResearchChatUiState {
    data object Idle : ResearchChatUiState
    data class Streaming(
        val phase: String = "",
        val answer: String = "",
        val heartbeatSeen: Boolean = false,
        val activity: List<String> = emptyList(),
    ) : ResearchChatUiState
    data class Completed(val answer: String) : ResearchChatUiState
    data class Failed(val message: String) : ResearchChatUiState
}
