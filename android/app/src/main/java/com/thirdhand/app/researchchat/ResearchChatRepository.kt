package com.thirdhand.app.researchchat

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Callback
import okhttp3.Call
import okhttp3.Response
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import org.json.JSONObject

class ResearchChatRepository(private val httpClient: OkHttpClient) {
    fun createSession(baseUrl: String, title: String, symbol: String?, onReady: (String) -> Unit, onFailure: (String) -> Unit) {
        val payload = JSONObject().put("title", title)
        if (!symbol.isNullOrBlank()) payload.put("primary_symbol", symbol)
        val request = Request.Builder().url("${baseUrl.trimEnd('/')}/v1/research-chat/sessions")
            .post(payload.toString().toRequestBody("application/json".toMediaType())).build()
        httpClient.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: java.io.IOException) = onFailure(e.message ?: "无法创建研究会话")
            override fun onResponse(call: Call, response: Response) {
                response.use {
                    val body = it.body?.string().orEmpty()
                    if (!it.isSuccessful) {
                        val detail = runCatching { JSONObject(body).opt("detail")?.toString() }.getOrNull()
                        return onFailure("研究功能暂不可用（HTTP ${it.code}${detail?.let { value -> "：$value" } ?: ""}）")
                    }
                    val id = runCatching { JSONObject(body).getString("id") }.getOrNull()
                    if (id == null) onFailure("研究会话响应无效") else onReady(id)
                }
            }
        })
    }
    fun stream(
        baseUrl: String,
        sessionId: String,
        message: String,
        symbol: String?,
        clientRequestId: String,
        onEvent: (ResearchSseEvent) -> Unit,
        onFailure: (String) -> Unit,
    ): EventSource {
        val payload = JSONObject().put("message", message).put("client_request_id", clientRequestId)
        if (!symbol.isNullOrBlank()) payload.put("symbol", symbol)
        val request = Request.Builder()
            .url("${baseUrl.trimEnd('/')}/v1/research-chat/sessions/$sessionId/messages/stream")
            .header("Accept", "text/event-stream")
            .post(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()
        return EventSources.createFactory(httpClient).newEventSource(request, object : EventSourceListener() {
            override fun onEvent(eventSource: EventSource, id: String?, type: String?, data: String) {
                type?.let { ResearchSseParser.parse(it, data) }?.let(onEvent)
            }

            override fun onFailure(eventSource: EventSource, throwable: Throwable?, response: okhttp3.Response?) {
                onFailure(throwable?.message ?: "研究流连接中断（HTTP ${response?.code ?: "unknown"}）")
            }
        })
    }
}
