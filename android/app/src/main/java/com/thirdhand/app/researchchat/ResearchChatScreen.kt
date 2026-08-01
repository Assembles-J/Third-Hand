package com.thirdhand.app.researchchat

import androidx.activity.compose.BackHandler
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.ui.Modifier
import com.thirdhand.app.EndpointStore
import androidx.compose.ui.platform.LocalContext

/** Small reusable region; navigation integration deliberately waits for a later phase. */
@Composable
fun ResearchChatStreamStatus(controller: ResearchChatController) {
    val state by controller.state.collectAsState()
    BackHandler(enabled = state is ResearchChatUiState.Streaming) { controller.cancel() }
    when (val current = state) {
        ResearchChatUiState.Idle -> Text("研究对话尚未开始")
        is ResearchChatUiState.Streaming -> {
            Text(current.phase.ifBlank { "正在连接研究流" })
            if (current.answer.isNotBlank()) Text(current.answer)
            Button(onClick = controller::cancel) { Text("取消研究") }
        }
        is ResearchChatUiState.Completed -> Text(current.answer)
        is ResearchChatUiState.Failed -> Text(current.message)
    }
}

@Composable
fun ResearchChatScreen() {
    val context = LocalContext.current
    val controller = remember { ResearchChatController() }
    var symbol by remember { mutableStateOf("") }
    var question by remember { mutableStateOf("") }
    Column {
        Text("研究对话")
        Text("仅解释已保存的行情、持仓与计划；不会自动交易。")
        OutlinedTextField(symbol, { symbol = it.uppercase() }, Modifier.fillMaxWidth(), label = { Text("证券代码（可选）") })
        OutlinedTextField(question, { question = it }, Modifier.fillMaxWidth(), label = { Text("研究问题") })
        Button(enabled = question.isNotBlank(), onClick = { controller.createAndStart(EndpointStore.baseUrl(context), question, symbol.ifBlank { null }) }) { Text("开始研究") }
        ResearchChatStreamStatus(controller)
    }
}
