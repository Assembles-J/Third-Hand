package com.thirdhand.app

import kotlinx.coroutines.delay

/**
 * Trigger the existing bounded background market refresh, then give it two
 * short opportunities to replace the local SQLite snapshot before rendering.
 *
 * This is a read/display helper only. It never marks a quote executable and it
 * never loops indefinitely. Paper Broker / ExecutionPrecheck keep their own
 * strict session and freshness authority.
 */
internal suspend fun loadLatestDisplayQuotes(
    api: ThirdHandApi,
    symbols: List<String>,
): List<MarketQuoteDto> {
    val normalized = symbols.map { it.trim().uppercase() }.filter { it.isNotBlank() }.distinct()
    if (normalized.isEmpty()) return emptyList()

    var current = ApiClient.latestMarketQuotes(api, normalized)
    val initialFingerprint = current.quoteFingerprint()

    repeat(2) { attempt ->
        // latestMarketQuotes(refresh=true) intentionally queues the provider job
        // and returns the current cache immediately. A bounded re-read lets the
        // UI observe the replacement without blocking the server read endpoint.
        delay(if (attempt == 0) 700L else 1_100L)
        val reread = runCatching {
            api.quotes(MarketQuoteBatchRequestDto(symbols = normalized, refresh = false))
        }.getOrNull().orEmpty()
        if (reread.isNotEmpty()) current = mergeDisplayQuotes(current, reread)
        if (current.quoteFingerprint() != initialFingerprint) return current
    }
    return current
}

private fun List<MarketQuoteDto>.quoteFingerprint(): String =
    sortedBy { it.symbol }.joinToString("|") { quote ->
        listOf(
            quote.symbol,
            quote.price?.toString().orEmpty(),
            quote.as_of.orEmpty(),
            quote.retrieved_at.orEmpty(),
            quote.refresh_status.orEmpty(),
        ).joinToString(":")
    }

private fun mergeDisplayQuotes(
    previous: List<MarketQuoteDto>,
    refreshed: List<MarketQuoteDto>,
): List<MarketQuoteDto> {
    val previousBySymbol = previous.associateBy { it.symbol }.toMutableMap()
    refreshed.forEach { quote -> previousBySymbol[quote.symbol] = quote }
    return previousBySymbol.values.toList()
}
