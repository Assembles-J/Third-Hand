package com.thirdhand.app

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import kotlinx.coroutines.launch

private const val NewsPageSize = 20

@Composable
fun NewsScreen() {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var news by remember { mutableStateOf<List<NewsItemDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var loadingMore by remember { mutableStateOf(false) }
    var hasMore by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    fun loadPage(reset: Boolean) = scope.launch {
        if (reset) { loading = true; error = null } else loadingMore = true
        val offset = if (reset) 0 else news.size
        runCatching { api.cachedNews(NewsPageSize, offset) }
            .onSuccess { page ->
                news = if (reset) page else (news + page).distinctBy { it.id }
                hasMore = page.size == NewsPageSize
            }
            .onFailure { error = "无法读取已缓存新闻：${it.message ?: "请检查服务连接"}" }
        loading = false; loadingMore = false
    }
    fun refreshInBackground() = scope.launch {
        // Cached page is shown immediately; remote feeds refresh afterwards and
        // never block the first screen paint.
        runCatching {
            val symbols = api.researchTargets().map { it.symbol }.distinct()
            api.feed(symbols)
        }.onSuccess { loadPage(true) }
    }
    LaunchedEffect(Unit) { loadPage(true); refreshInBackground() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item { TradingPageHeader("新闻", "本地缓存优先加载，后台逐步刷新") { IconButton(onClick = { loadPage(true); refreshInBackground() }, enabled = !loading) { Icon(Icons.Filled.Refresh, "刷新新闻") } } }
        if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        error?.let { item { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 12.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
        item { TradingSection("最新动态", if (news.isEmpty()) "正在读取本地内容" else "已加载 ${news.size} 条 · 可继续翻页") }
        if (!loading && news.isEmpty()) item { Text("暂时没有已缓存的新闻。后台抓取完成后会自动显示。", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(news, key = { it.id }) { item ->
            Column(Modifier.fillMaxWidth().clickable(enabled = item.source_url.isNotBlank()) { uriHandler.openUri(item.source_url) }.padding(horizontal = 20.dp, vertical = 12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(if (item.source_name.contains("公告") || item.source_name.contains("交易所")) "公告" else "新闻", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
                    Text("  ${newsTimestamp(item.published_at)}", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
                }
                Text(item.title, Modifier.padding(top = 5.dp), maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                item.explanation.takeIf { it.isNotBlank() }?.let { Text(it, Modifier.padding(top = 4.dp), maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                androidx.compose.foundation.layout.Spacer(Modifier.padding(top = 10.dp)); TradingRowDivider()
            }
        }
        if (hasMore) item { Button(modifier = Modifier.fillMaxWidth().padding(20.dp), enabled = !loadingMore, onClick = { loadPage(false) }) { Text(if (loadingMore) "正在加载更多" else "加载更多新闻") } }
    }
}

private fun newsTimestamp(value: String?): String = value?.replace('T', ' ')?.substringBefore("+")?.takeLast(16) ?: "时间未知"
