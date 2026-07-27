package com.thirdhand.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ThirdHandApp() }
    }
}

@Composable
private fun ThirdHandApp() {
    var tab by remember { mutableIntStateOf(0) }
    val labels = listOf("今日", "持仓", "消息", "我的")
    MaterialTheme {
        Scaffold(
            topBar = { TopAppBar(title = { Text("Third-Hand") }) },
            bottomBar = { NavigationBar { labels.forEachIndexed { index, label ->
                NavigationBarItem(selected = tab == index, onClick = { tab = index }, icon = {}, label = { Text(label) })
            } } }
        ) { padding ->
            when (tab) {
                0 -> TodayScreen(Modifier.padding(padding))
                1 -> HoldingsScreen(Modifier.padding(padding))
                else -> PlaceholderScreen(Modifier.padding(padding), labels[tab])
            }
        }
    }
}

@Composable
private fun TodayScreen(modifier: Modifier) = LazyColumn(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
    item { Text("与你的关注有关", style = MaterialTheme.typography.headlineSmall) }
    item { Text("以下是信息解读与核查提醒，不构成投资建议。", style = MaterialTheme.typography.bodyMedium) }
    item { NewsCard("公司发布回购进展公告", "为什么相关：关联你的持仓 / 自选股", "打开公告，确认实际回购数量、金额和期限。") }
    item { GlossaryCard("回购是什么？", "公司买回自身股份；计划与实际完成情况要分开看。") }
}

@Composable
private fun NewsCard(title: String, relation: String, explanation: String) = Card {
    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Text(relation, color = MaterialTheme.colorScheme.primary)
        Text(explanation)
        TextButton(onClick = { }) { Text("查看来源（接入后可跳转）") }
    }
}

@Composable
private fun GlossaryCard(title: String, detail: String) = Card {
    Column(Modifier.padding(16.dp)) { Text(title, style = MaterialTheme.typography.titleMedium); Text(detail) }
}

@Composable
private fun HoldingsScreen(modifier: Modifier) = Column(modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
    Text("持仓", style = MaterialTheme.typography.headlineSmall)
    Text("请手动录入或导入自己从交易软件导出的 CSV。我们不会索取交易密码、验证码或登录 Cookie。")
    Button(onClick = { }) { Text("导入 CSV（待接入文件选择器）") }
    OutlinedButton(onClick = { }) { Text("手动添加持仓（待接入）") }
}

@Composable
private fun PlaceholderScreen(modifier: Modifier, title: String) = Column(modifier.padding(16.dp)) {
    Text(title, style = MaterialTheme.typography.headlineSmall)
    Text("此页面将接入订阅、关联消息与提醒设置。")
}
