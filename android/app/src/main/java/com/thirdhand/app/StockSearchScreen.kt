package com.thirdhand.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.MarketTag
import com.thirdhand.app.ui.components.TradingRowDivider
import kotlinx.coroutines.delay

private const val SEARCH_DEBOUNCE_MS = 450L
private const val REMOTE_POLL_LIMIT = 18
private const val REMOTE_POLL_INTERVAL_MS = 650L

private fun MarketQuoteDto.toSearchCandidate(): SecurityCandidateDto = SecurityCandidateDto(
    symbol = symbol,
    name = name,
    market = when {
        symbol.length == 5 -> "HK"
        symbol.startsWith("15") || symbol.startsWith("16") || symbol.startsWith("51") || symbol.startsWith("56") || symbol.startsWith("58") -> "ETF"
        else -> "CN"
    },
    currency = if (symbol.length == 5) "HKD" else "CNY",
    match_type = "cache",
)

private fun normalizeSearchText(value: String): String = value
    .trim()
    .uppercase()
    .replace(" ", "")
    .replace("-", "")
    .replace("_", "")
    .replace(".", "")
    .replace("·", "")
    .replace("(", "")
    .replace(")", "")
    .replace("（", "")
    .replace("）", "")

private fun rankCandidate(candidate: SecurityCandidateDto, query: String): Int {
    val cleaned = query.trim().uppercase()
    val normalized = normalizeSearchText(query)
    val normalizedName = normalizeSearchText(candidate.name)
    val paddedHk = if (cleaned.all(Char::isDigit) && cleaned.length < 5) cleaned.padStart(5, '0') else cleaned
    return when {
        candidate.symbol == cleaned || candidate.symbol == paddedHk -> 100
        normalizedName == normalized -> 95
        candidate.symbol.startsWith(cleaned) -> 90
        normalizedName.startsWith(normalized) -> 80
        normalizedName.contains(normalized) -> 70
        else -> 0
    }
}

private fun sortCandidates(
    query: String,
    values: List<SecurityCandidateDto>,
): List<SecurityCandidateDto> = values
    .distinctBy { "${it.market}:${it.symbol}" }
    .sortedWith(compareByDescending<SecurityCandidateDto> { rankCandidate(it, query) }.thenBy { it.symbol })
    .take(20)

@Composable
fun StockSearchScreen(
    onSelect: (SecurityCandidateDto) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val api = remember(context) { ApiClient.service(context) }
    val focusRequester = remember { FocusRequester() }
    var query by remember { mutableStateOf("") }
    var cachedQuotes by remember { mutableStateOf<List<MarketQuoteDto>>(emptyList()) }
    var results by remember { mutableStateOf<List<SecurityCandidateDto>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var remoteAttempt by remember { mutableIntStateOf(0) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryToken by remember { mutableIntStateOf(0) }
    val responseCache = remember { mutableMapOf<String, SymbolLookupResultDto>() }

    LaunchedEffect(Unit) {
        cachedQuotes = runCatching { api.cachedMarketQuotes() }.getOrDefault(emptyList())
        delay(120)
        focusRequester.requestFocus()
    }

    LaunchedEffect(query, cachedQuotes, retryToken) {
        val cleaned = query.trim()
        if (cleaned.isEmpty()) {
            results = emptyList()
            loading = false
            remoteAttempt = 0
            statusMessage = null
            error = null
            return@LaunchedEffect
        }

        val normalized = normalizeSearchText(cleaned)
        val cleanedUpper = cleaned.uppercase()
        val paddedHk = if (cleanedUpper.all(Char::isDigit) && cleanedUpper.length < 5) cleanedUpper.padStart(5, '0') else cleanedUpper
        val localMatches = cachedQuotes.asSequence()
            .filter {
                it.symbol == paddedHk ||
                    it.symbol.startsWith(cleanedUpper) ||
                    normalizeSearchText(it.name).contains(normalized)
            }
            .map(MarketQuoteDto::toSearchCandidate)
            .let { sortCandidates(cleaned, it.toList()) }

        // Existing local quotes are sufficient for interactive search. Never
        // start a provider-backed directory lookup just to "complete" these
        // results. This also prevents an intermediate query such as "小米" from
        // spawning a remote HK lookup while the user is still typing.
        if (localMatches.isNotEmpty()) {
            results = localMatches
            loading = false
            remoteAttempt = 0
            statusMessage = "已从本地行情缓存命中，不需要远程查询。"
            error = null
            return@LaunchedEffect
        }

        responseCache[cleaned]?.let { cached ->
            results = sortCandidates(cleaned, cached.matches)
            loading = false
            remoteAttempt = 0
            statusMessage = cached.lookup_message.takeIf { it.isNotBlank() }
            error = null
            return@LaunchedEffect
        }

        // A true debounce cancels this coroutine while the user is still typing.
        // Only a stable local miss reaches the server.
        delay(SEARCH_DEBOUNCE_MS)
        loading = true
        remoteAttempt = 0
        results = emptyList()
        statusMessage = "正在查询本地证券数据库…"
        error = null

        while (true) {
            val response = runCatching {
                api.symbolLookup(SymbolResolveRequestDto(listOf(cleaned))).firstOrNull()
            }.getOrElse {
                loading = false
                remoteAttempt = 0
                statusMessage = null
                error = "搜索服务连接失败：${it.message ?: "请检查服务连接"}"
                return@LaunchedEffect
            }

            if (response == null) {
                loading = false
                remoteAttempt = 0
                results = emptyList()
                statusMessage = null
                error = "搜索服务没有返回结果，请稍后重试。"
                return@LaunchedEffect
            }

            results = sortCandidates(cleaned, response.matches)
            statusMessage = response.lookup_message.takeIf { it.isNotBlank() }

            when (response.lookup_status) {
                "matched" -> {
                    loading = false
                    remoteAttempt = 0
                    error = null
                    responseCache[cleaned] = response
                    return@LaunchedEffect
                }

                "not_found" -> {
                    loading = false
                    remoteAttempt = 0
                    error = null
                    return@LaunchedEffect
                }

                "pending", "refreshing" -> {
                    remoteAttempt += 1
                    loading = true
                    error = null
                    if (remoteAttempt >= REMOTE_POLL_LIMIT) {
                        loading = false
                        error = "远程证券目录响应较慢，后台仍在查询。稍后点“重新查询”即可读取已经写入的缓存。"
                        return@LaunchedEffect
                    }
                    delay(REMOTE_POLL_INTERVAL_MS)
                }

                "partial_failure", "remote_error" -> {
                    loading = false
                    remoteAttempt = 0
                    error = response.lookup_message.ifBlank { "远程证券目录暂时不可用，请稍后重试。" }
                    return@LaunchedEffect
                }

                else -> {
                    loading = false
                    remoteAttempt = 0
                    error = null
                    return@LaunchedEffect
                }
            }
        }
    }

    Column(modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
        Text("搜索股票", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        Text(
            "本地数据库优先；只有本地没有结果时才后台查询远程证券目录。",
            modifier = Modifier.padding(top = 4.dp, bottom = 12.dp),
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        OutlinedTextField(
            value = query,
            onValueChange = { query = it },
            modifier = Modifier.fillMaxWidth().focusRequester(focusRequester),
            singleLine = true,
            label = { Text("股票名称 / 代码") },
            placeholder = { Text("例如 小米集团 / 01810") },
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(onClick = { query = "" }) {
                        Icon(Icons.Filled.Clear, contentDescription = "清空搜索")
                    }
                }
            },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { retryToken += 1 }),
        )

        if (loading) {
            if (remoteAttempt > 0) {
                LinearProgressIndicator(
                    progress = { remoteAttempt.toFloat() / REMOTE_POLL_LIMIT.toFloat() },
                    modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
                )
            } else {
                LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 10.dp))
            }
        }
        statusMessage?.let {
            Text(
                if (remoteAttempt > 0) "远程查询 ${remoteAttempt}/$REMOTE_POLL_LIMIT · $it" else it,
                Modifier.padding(top = 10.dp),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        error?.let {
            Column(Modifier.fillMaxWidth().padding(top = 8.dp)) {
                Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                if (query.isNotBlank()) {
                    TextButton(onClick = { retryToken += 1 }) {
                        Text("重新查询")
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))

        when {
            query.isBlank() -> {
                Column(
                    Modifier.fillMaxWidth().padding(vertical = 28.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Icon(
                        Icons.Filled.Search,
                        contentDescription = null,
                        modifier = Modifier.size(30.dp),
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text("输入股票名称或证券代码", Modifier.padding(top = 10.dp), style = MaterialTheme.typography.bodyMedium)
                    Text(
                        "已有股票即时从本地返回；本地没有时才显示远程查询进度。",
                        Modifier.padding(top = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            !loading && results.isEmpty() && error == null -> {
                Text(
                    "未找到“${query.trim()}”，请检查股票名称或证券代码。",
                    Modifier.padding(vertical = 24.dp),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            else -> {
                LazyColumn(Modifier.fillMaxWidth()) {
                    items(results, key = { "${it.market}:${it.symbol}" }) { candidate ->
                        Row(
                            Modifier.fillMaxWidth().clickable { onSelect(candidate) }.padding(vertical = 13.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    candidate.name.ifBlank { candidate.symbol },
                                    fontWeight = FontWeight.SemiBold,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(
                                        candidate.symbol,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    Text(
                                        if (candidate.match_type == "database" || candidate.match_type == "cache") " · 本地缓存" else " · 证券目录",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                            MarketTag(
                                when (candidate.market) {
                                    "CN" -> "A股"
                                    "HK" -> "港股"
                                    else -> candidate.market
                                },
                            )
                        }
                        TradingRowDivider()
                    }
                    if (loading && results.isNotEmpty()) {
                        item {
                            Row(
                                Modifier.fillMaxWidth().padding(vertical = 16.dp),
                                horizontalArrangement = Arrangement.Center,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                                Text(
                                    "已显示本地结果，后台查询继续进行…",
                                    Modifier.padding(start = 8.dp),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}
