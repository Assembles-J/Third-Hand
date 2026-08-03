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
import org.json.JSONArray

class ResearchChatRepository(private val httpClient: OkHttpClient) {
    fun sessions(baseUrl: String, onReady: (List<ResearchSessionSummary>) -> Unit, onFailure: (String) -> Unit) {
        getJson("${baseUrl.trimEnd('/')}/v1/research-chat/sessions", { body ->
            val items = JSONArray(body)
            onReady((0 until items.length()).map { index ->
                val item = items.getJSONObject(index)
                ResearchSessionSummary(item.getString("id"), item.optString("title", "研究会话"), item.optString("primary_symbol").ifBlank { null }, item.optString("updated_at"))
            })
        }, onFailure)
    }

    fun messages(baseUrl: String, sessionId: String, onReady: (List<ResearchStoredMessage>) -> Unit, onFailure: (String) -> Unit) {
        getJson("${baseUrl.trimEnd('/')}/v1/research-chat/sessions/$sessionId/messages", { body ->
            val items = JSONArray(body)
            onReady((0 until items.length()).map { index ->
                val item = items.getJSONObject(index)
                ResearchStoredMessage(item.optString("role") == "user", item.optString("content"))
            })
        }, onFailure)
    }
    fun sources(baseUrl: String, sessionId: String, onReady: (List<ResearchAttachedSource>) -> Unit, onFailure: (String) -> Unit) {
        getJson("${baseUrl.trimEnd('/')}/v1/research-chat/sessions/$sessionId/sources", { body ->
            val items = JSONArray(body)
            onReady((0 until items.length()).map { index ->
                val item = items.getJSONObject(index)
                ResearchAttachedSource(item.getString("source_key"), item.getString("title"), item.optString("detail"))
            })
        }, onFailure)
    }
    fun saveSources(baseUrl: String, sessionId: String, sources: List<ResearchAttachedSource>) {
        val entries = JSONArray().also { array -> sources.forEach { source -> array.put(JSONObject().put("source_key", source.key).put("title", source.title).put("detail", source.detail)) } }
        val request = Request.Builder().url("${baseUrl.trimEnd('/')}/v1/research-chat/sessions/$sessionId/sources")
            .put(JSONObject().put("sources", entries).toString().toRequestBody("application/json".toMediaType())).build()
        httpClient.newCall(request).enqueue(object : Callback { override fun onFailure(call: Call, e: java.io.IOException) = Unit; override fun onResponse(call: Call, response: Response) { response.close() } })
    }

    private fun getJson(url: String, onReady: (String) -> Unit, onFailure: (String) -> Unit) {
        httpClient.newCall(Request.Builder().url(url).get().build()).enqueue(object : Callback {
            override fun onFailure(call: Call, e: java.io.IOException) = onFailure(e.message ?: "网络连接失败")
            override fun onResponse(call: Call, response: Response) = response.use {
                val body = it.body?.string().orEmpty()
                if (it.isSuccessful) onReady(body) else onFailure("读取研究记录失败（HTTP ${it.code}）")
            }
        })
    }
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
