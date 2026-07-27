package com.thirdhand.app

import android.os.Bundle
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.clickable
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ThirdHandApp() }
    }
}

@Composable
@OptIn(ExperimentalMaterial3Api::class)
private fun ThirdHandApp() {
    val context = LocalContext.current
    var themeMode by remember { mutableStateOf(ThemeStore.load(context)) }
    var tab by remember { mutableIntStateOf(0) }
    val labels = listOf("今日", "持仓", "消息", "我的")
    ThirdHandTheme(themeMode) {
        Scaffold(
            topBar = { TopAppBar(title = { Text("Third-Hand") }) },
            bottomBar = {
                NavigationBar {
                    labels.forEachIndexed { index, label ->
                        NavigationBarItem(selected = tab == index, onClick = { tab = index }, icon = {}, label = { Text(label) })
                    }
                }
            },
        ) { padding ->
            when (tab) {
                0 -> TodayScreen(Modifier.padding(padding))
                1 -> HoldingsScreen(Modifier.padding(padding))
                2 -> FeedScreen(Modifier.padding(padding))
                else -> ProfileScreen(
                    modifier = Modifier.padding(padding),
                    themeMode = themeMode,
                    onThemeModeChange = { mode -> ThemeStore.save(context, mode); themeMode = mode },
                )
            }
        }
    }
}

@Composable
private fun TodayScreen(modifier: Modifier) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var quotes by remember { mutableStateOf<List<MarketQuoteDto>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    fun refresh() = scope.launch {
        error = null
        try {
            holdings = api.holdings()
            quotes = if (holdings.isEmpty()) emptyList() else api.quotes(holdings.map { it.symbol })
        } catch (exception: Exception) {
            error = "无法连接数据服务：${exception.message ?: "请确认后端正在运行"}"
        }
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("今日关注", style = MaterialTheme.typography.headlineSmall) }
        item { Text("行情来自公开源快照，显示北京时间与数据来源，不构成投资建议。") }
        item { Button(onClick = { refresh() }) { Text("刷新行情") } }
        error?.let { message -> item { Text(message, color = MaterialTheme.colorScheme.error) } }
        if (holdings.isEmpty()) item { Text("先在“持仓”页手动添加一只股票，例如小米集团-W（01810）。") }
        items(quotes) { quote -> QuoteCard(quote) }
    }
}

@Composable
private fun QuoteCard(quote: MarketQuoteDto) = Card(Modifier.fillMaxWidth()) {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("${quote.name} · ${quote.symbol}", style = MaterialTheme.typography.titleMedium)
        Text("最新价：${quote.price ?: "--"} ${quote.currency}    涨跌幅：${quote.change_percent ?: "--"}%")
        Text("${quote.source}｜获取：${quote.retrieved_at}", style = MaterialTheme.typography.bodySmall)
        Text(quote.freshness_note, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun HoldingsScreen(modifier: Modifier) {
    val context = LocalContext.current
    val api = ApiClient.service(context)
    var holdings by remember { mutableStateOf<List<HoldingDto>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var showAdd by remember { mutableStateOf(false) }
    var preview by remember { mutableStateOf<List<RecognizedHolding>>(emptyList()) }
    var scanError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { imageUri ->
        if (imageUri != null) scope.launch {
            try {
                scanError = null
                preview = ScreenshotOcr.scan(context, imageUri)
                if (preview.isEmpty()) scanError = "未能识别出完整持仓行，请使用清晰、完整的持仓列表截图。"
            } catch (exception: Exception) {
                scanError = "截图识别失败：${exception.message ?: "请重试"}"
            }
        }
    }
    fun refresh() = scope.launch {
        try { holdings = api.holdings(); error = null }
        catch (exception: Exception) { error = "读取持仓失败：${exception.message ?: "请确认后端正在运行"}" }
    }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("持仓", style = MaterialTheme.typography.headlineSmall) }
        item { Text("仅录入你主动提供的信息；不会索取交易密码、验证码或券商 Cookie。") }
        item { Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { Button(onClick = { showAdd = true }) { Text("手动添加") }; OutlinedButton(onClick = { imagePicker.launch("image/*") }) { Text("识别截图") }; OutlinedButton(onClick = { refresh() }) { Text("刷新") } } }
        error?.let { message -> item { Text(message, color = MaterialTheme.colorScheme.error) } }
        scanError?.let { message -> item { Text(message, color = MaterialTheme.colorScheme.error) } }
        items(holdings, key = { it.id }) { holding ->
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                    Column(Modifier.fillMaxWidth()) {
                        Text("${holding.name} · ${holding.symbol}", style = MaterialTheme.typography.titleMedium)
                        Text("数量：${holding.quantity}　成本：${holding.average_cost}")
                    }
                    TextButton(onClick = { scope.launch { api.deleteHolding(holding.id); refresh() } }) { Text("删除") }
                }
            }
        }
    }
    if (showAdd) AddHoldingDialog(
        onDismiss = { showAdd = false },
        onSave = { input -> scope.launch { api.addHolding(input); showAdd = false; refresh() } },
    )
    if (preview.isNotEmpty()) ScreenshotPreviewDialog(preview, onDismiss = { preview = emptyList() })
}

@Composable
private fun ScreenshotPreviewDialog(items: List<RecognizedHolding>, onDismiss: () -> Unit) = AlertDialog(
    onDismissRequest = onDismiss,
    title = { Text("识别结果（请校对）") },
    text = { Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("截图未包含证券代码，结果不会自动入库。请逐项核对名称、数量和成本，再用“手动添加”补全代码。")
        items.forEach { item -> Text("${item.name}：${item.quantity} 股/份，成本 ${item.averageCost}") }
    } },
    confirmButton = { TextButton(onClick = onDismiss) { Text("我知道了") } },
)

@Composable
private fun AddHoldingDialog(onDismiss: () -> Unit, onSave: (HoldingInputDto) -> Unit) {
    var symbol by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var quantity by remember { mutableStateOf("") }
    var cost by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("添加持仓") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(symbol, { symbol = it }, label = { Text("代码，例如 01810") })
            OutlinedTextField(name, { name = it }, label = { Text("名称") })
            OutlinedTextField(quantity, { quantity = it }, label = { Text("数量") })
            OutlinedTextField(cost, { cost = it }, label = { Text("平均成本") })
        } },
        confirmButton = { TextButton(onClick = { onSave(HoldingInputDto(symbol, name, quantity.toDoubleOrNull() ?: 0.0, cost.toDoubleOrNull() ?: -1.0)) }) { Text("保存") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
private fun FeedScreen(modifier: Modifier) {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val api = ApiClient.service(context)
    var feed by remember { mutableStateOf<List<NewsItemDto>>(emptyList()) }
    var announcements by remember { mutableStateOf<List<NewsItemDto>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    fun refresh() = scope.launch { try {
        val symbols = api.holdings().map { it.symbol }
        announcements = api.announcements(symbols)
        feed = api.feed(symbols)
        error = null
    } catch (exception: Exception) { error = exception.message } }
    LaunchedEffect(Unit) { refresh() }
    LazyColumn(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("关联消息", style = MaterialTheme.typography.headlineSmall) }
        item { Text("正式公告优先展示；新闻用于补充背景，均请以原文为准。") }
        item { Button(onClick = { refresh() }) { Text("刷新") } }
        error?.let { item { Text(it ?: "", color = MaterialTheme.colorScheme.error) } }
        if (announcements.isNotEmpty()) item { Text("正式公告", style = MaterialTheme.typography.titleMedium) }
        items(announcements) { item -> FeedCard(item, uriHandler, "公告") }
        if (feed.isNotEmpty()) item { Text("相关新闻", style = MaterialTheme.typography.titleMedium) }
        items(feed) { item -> FeedCard(item, uriHandler, "新闻") }
    }
}

@Composable
private fun FeedCard(item: NewsItemDto, uriHandler: androidx.compose.ui.platform.UriHandler, label: String) = Card(Modifier.fillMaxWidth()) {
    Column(Modifier.padding(16.dp)) {
        Text(label, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelMedium)
        Text(item.title, style = MaterialTheme.typography.titleMedium)
        Text(item.explanation)
        Text("${item.source_name}｜${item.published_at}", style = MaterialTheme.typography.bodySmall)
        TextButton(onClick = { uriHandler.openUri(item.source_url) }) { Text("查看原文") }
    }
}

@Composable
private fun ProfileScreen(modifier: Modifier, themeMode: ThemeMode, onThemeModeChange: (ThemeMode) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var baseUrl by remember { mutableStateOf(EndpointStore.baseUrl(context)) }
    var connectionStatus by remember { mutableStateOf<String?>(null) }
    Column(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("我的", style = MaterialTheme.typography.headlineSmall)
        Text("服务地址（模拟器默认 10.0.2.2；实机填写电脑局域网 IP 或 HTTPS 域名）")
        OutlinedTextField(baseUrl, { baseUrl = it }, label = { Text("例如 http://192.168.1.10:8000/") }, modifier = Modifier.fillMaxWidth())
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { EndpointStore.saveBaseUrl(context, baseUrl); baseUrl = EndpointStore.baseUrl(context); connectionStatus = "已保存：$baseUrl" }) { Text("保存地址") }
            OutlinedButton(onClick = {
                EndpointStore.saveBaseUrl(context, baseUrl)
                scope.launch {
                    connectionStatus = try {
                        val status = ApiClient.service(context).health().status
                        if (status == "ok") "连接成功" else "服务返回：$status"
                    } catch (exception: Exception) { "连接失败：${exception.message ?: "请检查网络、地址和后端"}" }
                }
            }) { Text("测试连接") }
        }
        connectionStatus?.let { Text(it, color = if (it == "连接成功") MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error) }
        Text("外观", style = MaterialTheme.typography.titleMedium)
        ThemeMode.entries.forEach { mode ->
            Row(
                modifier = Modifier.fillMaxWidth().clickable { onThemeModeChange(mode) },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = themeMode == mode, onClick = { onThemeModeChange(mode) })
                Text(mode.label)
            }
        }
        Text("当前为本地 MVP。持仓数据存储在后端 SQLite；请在生产部署前补充账号认证与备份。")
    }
}
