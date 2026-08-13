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

@Composable
fun NewsScreen() {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val api = remember(context) { ApiClient.service(context) }
    val scope = rememberCoroutineScope()
    var news by remember { mutableStateOf<List<NewsItemDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    fun refresh() = scope.launch {
        loading = true; error = null
        runCatching {
            val symbols = api.researchTargets().map { it.symbol }.distinct()
            (api.announcements(symbols) + api.feed(symbols)).distinctBy { it.id }.sortedByDescending { it.published_at }
        }.onSuccess { news = it }.onFailure { error = "无法读取新闻：${it.message ?: "请检查服务连接"}" }
        loading = false
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item { TradingPageHeader("新闻", "公告、市场动态与已保存的 AI 解读") { IconButton(onClick = ::refresh, enabled = !loading) { Icon(Icons.Filled.Refresh, "刷新新闻") } } }
        if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) }
        error?.let { item { Text(it, Modifier.padding(horizontal = 20.dp, vertical = 12.dp), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
        item { TradingSection("最新动态", if (news.isEmpty()) "正在等待内容" else "${news.size} 条已保存内容") }
        if (!loading && news.isEmpty()) item { Text("暂时没有可展示的新闻。市场抓取到的内容会保存到数据库，并在这里按时间排列。", Modifier.padding(horizontal = 20.dp, vertical = 14.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        items(news, key = { it.id }) { item ->
            Column(Modifier.fillMaxWidth().clickable(enabled = item.source_url.isNotBlank()) { uriHandler.openUri(item.source_url) }.padding(horizontal = 20.dp, vertical = 12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(if (item.source_name.contains("公告") || item.source_name.contains("交易所")) "公告" else "新闻", color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
                    Text("  ${newsTimestamp(item.published_at)}", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.labelSmall)
                }
                Text(item.title, Modifier.padding(top = 5.dp), maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.SemiBold)
                item.explanation?.takeIf { it.isNotBlank() }?.let { Text(it, Modifier.padding(top = 4.dp), maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                androidx.compose.foundation.layout.Spacer(Modifier.padding(top = 10.dp)); TradingRowDivider()
            }
        }
    }
}

private fun newsTimestamp(value: String?): String = value?.replace('T', ' ')?.substringBefore("+")?.takeLast(16) ?: "时间未知"
