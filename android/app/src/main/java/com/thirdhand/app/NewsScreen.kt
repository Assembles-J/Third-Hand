package com.thirdhand.app

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.thirdhand.app.ui.components.TradingPageHeader
import com.thirdhand.app.ui.components.TradingRowDivider
import com.thirdhand.app.ui.components.TradingSection
import com.thirdhand.app.ui.theme.AppSpacing
import kotlinx.coroutines.launch

private const val NewsPageSize = 20

@OptIn(ExperimentalMaterial3Api::class)
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
    var scopeFilter by remember { mutableStateOf("all") }

    fun loadPage(reset: Boolean) = scope.launch {
        if (reset) { loading = true; error = null } else loadingMore = true
        val offset = if (reset) 0 else news.size
        runCatching { api.cachedNews(NewsPageSize, offset, scopeFilter) }
            .onSuccess { page ->
                news = if (reset) page else (news + page).distinctBy { it.id }
                hasMore = page.size == NewsPageSize
            }
            .onFailure { error = "数据同步异常：${it.message ?: "网络连接失败"}" }
        loading = false; loadingMore = false
    }

    fun refreshInBackground() = scope.launch {
        runCatching {
            val symbols = when (scopeFilter) {
                "paper_positions" -> api.paperTradingAccount().positions.map { it.symbol }
                "learning_cases" -> api.learningCases().mapNotNull { it.symbol }
                else -> api.researchTargets().map { it.symbol }
            }.distinct()
            api.feed(symbols)
        }.onSuccess { loadPage(true) }
    }

    LaunchedEffect(scopeFilter) { loadPage(true); refreshInBackground() }

    Scaffold(
        topBar = {
            TradingPageHeader("资讯中心", "深度研报、市场公告与持仓动态") {
                IconButton(onClick = { loadPage(true); refreshInBackground() }, enabled = !loading) {
                    if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    else Icon(Icons.Filled.Refresh, "刷新", tint = MaterialTheme.colorScheme.primary)
                }
            }
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(paddingValues),
            contentPadding = PaddingValues(bottom = AppSpacing.xxLarge)
        ) {
            item {
                LazyRow(
                    modifier = Modifier.fillMaxWidth(),
                    contentPadding = PaddingValues(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.medium)
                ) {
                    items(listOf("all" to "推荐", "paper_positions" to "自选", "learning_cases" to "研报关联")) { (value, label) ->
                        FilterChip(
                            selected = scopeFilter == value,
                            onClick = { scopeFilter = value },
                            label = { Text(label) },
                            modifier = Modifier.padding(end = AppSpacing.small),
                            shape = MaterialTheme.shapes.small
                        )
                    }
                }
            }

            if (loading && news.isEmpty()) {
                item { LinearProgressIndicator(Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge)) }
            }

            error?.let {
                item {
                    Surface(
                        Modifier.fillMaxWidth().padding(horizontal = AppSpacing.xxLarge),
                        color = MaterialTheme.colorScheme.errorContainer,
                        shape = MaterialTheme.shapes.small
                    ) {
                        Text(it, Modifier.padding(AppSpacing.medium), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onErrorContainer)
                    }
                }
            }

            item {
                TradingSection(
                    title = if (scopeFilter == "all") "全市场动态" else "关联资讯",
                    detail = if (news.isNotEmpty()) "已加载 ${news.size} 条即时快讯" else "正在检索最新数据..."
                )
            }

            items(news, key = { it.id }) { item ->
                NewsRow(item) {
                    if (item.source_url.isNotBlank()) uriHandler.openUri(item.source_url)
                }
            }

            if (hasMore && news.isNotEmpty()) {
                item {
                    TextButton(
                        modifier = Modifier.fillMaxWidth().padding(AppSpacing.xxLarge),
                        onClick = { loadPage(false) },
                        enabled = !loadingMore
                    ) {
                        if (loadingMore) {
                            CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(if (loadingMore) "加载中" else "查看更多资讯")
                    }
                }
            }
        }
    }
}

@Composable
private fun NewsRow(item: NewsItemDto, onClick: () -> Unit) {
    val isAnnouncement = item.source_name.contains("公告") || item.source_name.contains("交易所")

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = AppSpacing.xxLarge, vertical = AppSpacing.large)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Surface(
                color = if (isAnnouncement) MaterialTheme.colorScheme.tertiaryContainer else MaterialTheme.colorScheme.secondaryContainer,
                shape = RoundedCornerShape(4.dp)
            ) {
                Text(
                    text = if (isAnnouncement) "公告" else "快讯",
                    modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = if (isAnnouncement) MaterialTheme.colorScheme.onTertiaryContainer else MaterialTheme.colorScheme.onSecondaryContainer
                )
            }
            Spacer(Modifier.width(AppSpacing.small))
            Text(
                text = newsTimestamp(item.published_at),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Spacer(Modifier.height(AppSpacing.small))

        Text(
            text = item.title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            color = MaterialTheme.colorScheme.onSurface
        )

        if (item.explanation.isNotBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(
                text = item.explanation,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis
            )
        }

        Spacer(Modifier.height(AppSpacing.large))
        TradingRowDivider()
    }
}

private fun newsTimestamp(value: String?): String {
    val raw = value?.replace('T', ' ')?.substringBefore("+") ?: return ""
    return if (raw.length > 16) raw.takeLast(16) else raw
}
