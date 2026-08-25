package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.thirdhand.app.ui.components.MarketTag
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.theme.AppSpacing
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
    .replace(Regex("[^A-Z0-9]"), "")

private fun rankCandidate(candidate: SecurityCandidateDto, query: String): Int {
    val cleaned = query.trim().uppercase()
    val normalized = normalizeSearchText(query)
    val normalizedName = normalizeSearchText(candidate.name)
    val paddedHk = if (cleaned.all { it.isDigit() } && cleaned.length < 5) cleaned.padStart(5, '0') else cleaned
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

@OptIn(ExperimentalMaterial3Api::class)
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
        val localMatches = cachedQuotes.filter {
            it.symbol.startsWith(cleanedUpper) || normalizeSearchText(it.name).contains(normalized)
        }.map { it.toSearchCandidate() }

        if (localMatches.isNotEmpty()) {
            results = sortCandidates(cleaned, localMatches)
            loading = false
            remoteAttempt = 0
            statusMessage = "本地缓存匹配"
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

        delay(SEARCH_DEBOUNCE_MS)
        loading = true
        remoteAttempt = 0
        results = emptyList()
        statusMessage = "正在检索证券目录..."
        error = null

        var remoteFinished = false
        while (!remoteFinished) {
            val responseResult = runCatching {
                api.symbolLookup(SymbolResolveRequestDto(listOf(cleaned))).firstOrNull()
            }

            val response = responseResult.getOrNull()
            if (response == null) {
                loading = false
                error = "搜索服务未响应"
                remoteFinished = true
                break
            }

            results = sortCandidates(cleaned, response.matches)
            statusMessage = response.lookup_message.takeIf { it.isNotBlank() }

            if (response.lookup_status == "matched" || response.lookup_status == "not_found") {
                loading = false
                if (response.lookup_status == "matched") responseCache[cleaned] = response
                remoteFinished = true
                break
            }

            remoteAttempt += 1
            if (remoteAttempt >= REMOTE_POLL_LIMIT) {
                loading = false
                error = "远程检索超时，请稍后重试"
                remoteFinished = true
                break
            }
            delay(REMOTE_POLL_INTERVAL_MS)
        }
    }

    Surface(modifier = modifier.fillMaxSize(), color = MaterialTheme.colorScheme.surface) {
        Column(modifier = Modifier.fillMaxSize()) {
            Column(Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large)) {
                Text(
                    text = "查找证券",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.ExtraBold
                )
                Text(
                    text = "支持 A 股代码、拼音缩写或港股标的",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                Spacer(Modifier.height(AppSpacing.large))

                TextField(
                    value = query,
                    onValueChange = { query = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .focusRequester(focusRequester),
                    colors = TextFieldDefaults.colors(
                        focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f),
                        unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.3f),
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                        disabledIndicatorColor = Color.Transparent
                    ),
                    shape = MaterialTheme.shapes.medium,
                    singleLine = true,
                    placeholder = { Text("输入名称或代码", style = MaterialTheme.typography.bodyMedium) },
                    leadingIcon = { Icon(Icons.Filled.Search, null, tint = MaterialTheme.colorScheme.primary) },
                    trailingIcon = {
                        if (query.isNotEmpty()) {
                            IconButton(onClick = { query = "" }) {
                                Icon(Icons.Filled.Clear, null)
                            }
                        }
                    },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { retryToken += 1 }),
                )
            }

            if (loading) {
                LinearProgressIndicator(
                    modifier = Modifier.fillMaxWidth().height(2.dp),
                    color = MaterialTheme.colorScheme.primary,
                    trackColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.3f)
                )
            } else {
                HorizontalDivider(thickness = 0.5.dp, color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.3f))
            }

            Box(Modifier.fillMaxSize()) {
                val currentError = error
                val currentStatus = statusMessage
                if (query.isBlank()) {
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(bottom = 60.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Surface(
                            modifier = Modifier.size(64.dp),
                            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f),
                            shape = CircleShape
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.Default.Search, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(32.dp))
                            }
                        }
                        Spacer(Modifier.height(AppSpacing.large))
                        Text(text = "开始搜索标的", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Bold)
                        Text(text = "输入公司名称或 6 位/5 位股票代码", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                } else if (!loading && results.isEmpty() && currentError == null) {
                    Text(
                        text = "未找到相关结果",
                        modifier = Modifier.align(Alignment.TopCenter).padding(top = 40.dp).fillMaxWidth(),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        textAlign = TextAlign.Center
                    )
                } else if (currentError != null) {
                    Column(
                        modifier = Modifier.align(Alignment.TopCenter).padding(top = 40.dp).padding(horizontal = AppSpacing.xxLarge),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Surface(
                            color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.1f),
                            shape = MaterialTheme.shapes.small,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(Modifier.padding(AppSpacing.large), horizontalAlignment = Alignment.CenterHorizontally) {
                                Text(text = currentError, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
                                Spacer(Modifier.height(AppSpacing.small))
                                TextButton(onClick = { retryToken += 1 }) {
                                    Text("重新检索")
                                }
                            }
                        }
                    }
                } else {
                    Column {
                        if (currentStatus != null) {
                            Text(
                                text = currentStatus,
                                modifier = Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.small),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.primary
                            )
                        }
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge)
                        ) {
                            items(results, key = { "${it.market}:${it.symbol}" }) { candidate ->
                                SearchCandidateRow(candidate) { onSelect(candidate) }
                            }

                            if (loading && results.isNotEmpty()) {
                                item {
                                    Row(
                                        modifier = Modifier.fillMaxWidth().padding(AppSpacing.large),
                                        horizontalArrangement = Arrangement.Center,
                                        verticalAlignment = Alignment.CenterVertically
                                    ) {
                                        CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                                        Spacer(Modifier.width(AppSpacing.medium))
                                        Text(text = "正在深度搜索...", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SearchCandidateRow(candidate: SecurityCandidateDto, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Row(
            Modifier.padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = candidate.name.ifBlank { candidate.symbol },
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Text(
                    text = candidate.symbol,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            MarketTag(
                label = when (candidate.market) {
                    "CN" -> "A股"
                    "HK" -> "港股"
                    "ETF" -> "基金"
                    else -> candidate.market
                }
            )
        }
        TradingRowDivider()
    }
}
