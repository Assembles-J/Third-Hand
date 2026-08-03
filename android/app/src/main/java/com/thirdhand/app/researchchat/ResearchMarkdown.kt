package com.thirdhand.app.researchchat

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp

/** Native, readable Markdown subset for streamed mobile research answers. */
@Composable
fun ResearchMarkdown(markdown: String, modifier: Modifier = Modifier) {
    var codeBlock = false
    Column(modifier) {
        markdown.lines().forEach { raw ->
            val line = raw.trimEnd()
            if (line.trimStart().startsWith("```")) { codeBlock = !codeBlock; return@forEach }
            when {
                codeBlock -> Text(line, Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceContainerHighest).padding(10.dp), fontFamily = FontFamily.Monospace, style = MaterialTheme.typography.bodySmall)
                line.startsWith("### ") -> Text(inline(line.drop(4)), Modifier.padding(top = 8.dp), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                line.startsWith("## ") -> Text(inline(line.drop(3)), Modifier.padding(top = 10.dp), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                line.startsWith("# ") -> Text(inline(line.drop(2)), Modifier.padding(top = 10.dp), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                line.trimStart().startsWith("- ") || line.trimStart().startsWith("* ") -> Text(inline("• ${line.trimStart().drop(2)}"), Modifier.padding(start = 4.dp, top = 3.dp), style = MaterialTheme.typography.bodyMedium)
                line.matches(Regex("^\\s*\\d+\\.\\s+.*")) -> Text(inline(line.trimStart()), Modifier.padding(start = 4.dp, top = 3.dp), style = MaterialTheme.typography.bodyMedium)
                line.startsWith("> ") -> Text(inline(line.drop(2)), Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.primaryContainer).padding(10.dp), color = MaterialTheme.colorScheme.onPrimaryContainer, style = MaterialTheme.typography.bodyMedium)
                line.isBlank() -> Text("", Modifier.padding(vertical = 3.dp))
                else -> Text(inline(line), Modifier.padding(top = 2.dp), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

private fun inline(text: String): AnnotatedString = buildAnnotatedString {
    val token = Regex("(\\*\\*.+?\\*\\*|`.+?`)")
    var cursor = 0
    token.findAll(text).forEach { match ->
        append(text.substring(cursor, match.range.first))
        val value = match.value
        if (value.startsWith("**")) withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(value.removePrefix("**").removeSuffix("**")) }
        else withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = Color(0x1A000000))) { append(value.removePrefix("`").removeSuffix("`")) }
        cursor = match.range.last + 1
    }
    append(text.substring(cursor))
}
