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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.MarketTag
import com.thirdhand.app.ui.components.TradingRowDivider
import kotlinx.coroutines.delay

private const val REMOTE_POLL_LIMIT = 18
private const val REMOTE_POLL_INTERVAL_MS = 650L

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

private fun sortCandidates(query: String, values: List<SecurityCandidateDto>): List<SecurityCandidateDto> = values
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
    var results by remember { mutableStateOf<List<SecurityCandidateDto>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var remoteAttempt by remember { mutableIntStateOf(0) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var retryToken by remember { mutableIntStateOf(0) }
    val responseCache = remember { mutableMapOf<String, SymbolLookupResultDto>() }

    LaunchedEffect(Unit) {
        delay(120)
        focusRequester.requestFocus()
    }

    LaunchedEffect(query, retryToken) {
        val cleaned = query.trim()
        if (cleaned.isEmpty()) {
            results = emptyList()
            loading = false
            remoteAttempt = 0
            statusMessage = null
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

        // Keep typing responsive. Every subsequent call is intentionally short:
        // the server only reads local caches and starts remote work in background.
        delay(220)
        loading = true
        remoteAttempt = 0
        statusMessage = "正在查询本地证券缓存…"
        error = null

        while (true) {
            val response = runCatching {
                api.symbolLookup(SymbolResolveRequestDto(listOf(cleaned))).firstOrNull()
            }.getOrElse {
                loading = false
                error = "搜索服务连接失败：${it.message ?: "请检查服务连接"}"
                statusMessage = null
                return@LaunchedEffect
            }

            if (response == null) {
                loading = false
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
                    // Do not keep a page-local negative cache. The backend may
                    // finish a remote refresh after this response, and retrying
                    // should immediately observe the newly warmed server cache.
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
                        error = if (results.isEmpty()) {
                            "远程证券目录响应较慢，后台仍在查询。你可以稍后点“重新查询”，命中后会直接走缓存。"
                        } else {
                            "已显示本地缓存结果；远程全市场补全仍在后台进行，可稍后重新查询。"
                        }
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
            "优先读取本地数据库与证券缓存；未命中时后台查询远程证券目录。",
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
                Column(Modifier.fillMaxWidth().padding(vertical = 28.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Filled.Search, contentDescription = null, modifier = Modifier.size(30.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("输入股票名称或证券代码", Modifier.padding(top = 10.dp), style = MaterialTheme.typography.bodyMedium)
                    Text("本地已有股票会优先命中；代码前缀也可以直接过滤本地证券目录。", Modifier.padding(top = 4.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
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
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Text(candidate.symbol, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text(
                                        if (candidate.match_type == "database") " · 本地缓存" else " · 证券目录",
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
                                Text("已显示缓存结果，继续补全全市场…", Modifier.padding(start = 8.dp), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}
