package com.thirdhand.app.researchchat

import org.json.JSONObject

/** Parses Third-Hand's versioned events, never DeepSeek's upstream SSE. */
object ResearchSseParser {
    fun parse(eventName: String, data: String): ResearchSseEvent? = runCatching {
        val envelope = JSONObject(data)
        if (envelope.getString("protocol") != "research-sse-v1" || envelope.getString("event") != eventName) return null
        val rawData = envelope.getJSONObject("data")
        val values = rawData.keys().asSequence().associateWith { key -> rawData.opt(key)?.toString().orEmpty() }
        ResearchSseEvent(envelope.getString("protocol"), eventName, values)
    }.getOrNull()
}
