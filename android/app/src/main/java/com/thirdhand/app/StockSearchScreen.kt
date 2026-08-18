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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.MarketTag
import com.thirdhand.app.ui.components.TradingRowDivider
import kotlinx.coroutines.delay

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
    val normalized = normalizeSearchText(query)
    val normalizedName = normalizeSearchText(candidate.name)
    return when {
        candidate.symbol == query.trim() -> 100
        normalizeSearchText(candidate.name) == normalized -> 90
        candidate.symbol.startsWith(query.trim()) -> 80
        normalizedName.startsWith(normalized) -> 70
        normalizedName.contains(normalized) -> 60
        else -> 0
    }
}

private fun mergeCandidates(
    query: String,
    remote: List<SecurityCandidateDto>,
    local: List<SecurityCandidateDto>,
): List<SecurityCandidateDto> = (remote + local)
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
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val responseCache = remember { mutableMapOf<String, SymbolLookupResultDto>() }

    LaunchedEffect(Unit) {
        cachedQuotes = runCatching { api.cachedMarketQuotes() }.getOrDefault(emptyList())
        delay(120)
        focusRequester.requestFocus()
    }

    LaunchedEffect(query, cachedQuotes) {
        val cleaned = query.trim()
        if (cleaned.isEmpty()) {
            results = emptyList()
            loading = false
            statusMessage = null
            error = null
            return@LaunchedEffect
        }

        val normalized = normalizeSearchText(cleaned)
        val localMatches = cachedQuotes.asSequence()
            .filter {
                it.symbol.startsWith(cleaned) ||
                    normalizeSearchText(it.name).contains(normalized)
            }
            .map(MarketQuoteDto::toSearchCandidate)
            .sortedByDescending { rankCandidate(it, cleaned) }
            .take(20)
            .toList()

        // Show local cached matches immediately. The remote directory search then
        // fills gaps without making the user stare at an empty loading state.
        results = localMatches
        loading = true
        error = null
        statusMessage = if (localMatches.isNotEmpty()) "正在补全全市场结果…" else "正在查询证券目录…"

        responseCache[cleaned]?.let { cached ->
            results = mergeCandidates(cleaned, cached.matches, localMatches)
            loading = false
            statusMessage = cached.lookup_message.takeIf { cached.lookup_status == "partial_failure" }
            return@LaunchedEffect
        }

        delay(250)
        runCatching {
            api.symbolLookup(SymbolResolveRequestDto(listOf(cleaned))).firstOrNull()
        }.onSuccess { response ->
            if (response == null) {
                results = localMatches
                statusMessage = null
            } else {
                responseCache[cleaned] = response
                results = mergeCandidates(cleaned, response.matches, localMatches)
                statusMessage = response.lookup_message.takeIf { response.lookup_status == "partial_failure" }
            }
            loading = false
        }.onFailure {
            loading = false
            results = localMatches
            error = if (localMatches.isNotEmpty()) {
                "全市场目录暂时不可用，已显示本地行情缓存中的匹配项。"
            } else {
                "搜索暂时不可用：${it.message ?: "请稍后重试"}"
            }
            statusMessage = null
        }
    }

    Column(modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
        Text("搜索股票", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
        Text(
            "支持证券名称和代码；已有行情会先显示，再补全全市场结果。",
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
            placeholder = { Text("例如 贵州茅台 / 600519") },
            leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
            trailingIcon = {
                if (query.isNotEmpty()) {
                    IconButton(onClick = { query = "" }) {
                        Icon(Icons.Filled.Clear, contentDescription = "清空搜索")
                    }
                }
            },
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = {}),
        )
        if (loading) {
            LinearProgressIndicator(Modifier.fillMaxWidth().padding(top = 10.dp))
        }
        statusMessage?.let {
            Text(it, Modifier.padding(top = 10.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        error?.let {
            Text(it, Modifier.padding(top = 10.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
        }
        Spacer(Modifier.height(8.dp))

        when {
            query.isBlank() -> {
                Column(Modifier.fillMaxWidth().padding(vertical = 28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Filled.Search, contentDescription = null, modifier = Modifier.size(30.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("输入股票名称或证券代码", Modifier.padding(top = 10.dp), style = MaterialTheme.typography.bodyMedium)
                    Text("代码可直接输入完整证券代码；已缓存股票支持代码前缀即时过滤。", Modifier.padding(top = 4.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                                Text(candidate.name.ifBlank { candidate.symbol }, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text(candidate.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                                Text("继续补全…", Modifier.padding(start = 8.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}
