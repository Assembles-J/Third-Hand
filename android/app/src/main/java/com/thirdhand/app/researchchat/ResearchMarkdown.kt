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

/** A safe, native subset of Markdown for streamed research replies. Raw HTML is always plain text. */
@Composable
fun ResearchMarkdown(markdown: String, modifier: Modifier = Modifier) {
    var inCodeBlock = false
    Column(modifier) {
        markdown.lines().forEach { line ->
            if (line.trimStart().startsWith("```")) {
                inCodeBlock = !inCodeBlock
                return@forEach
            }
            when {
                inCodeBlock -> Text(
                    line,
                    Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.surfaceContainerHighest).padding(8.dp),
                    fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.bodySmall,
                )
                line.startsWith("### ") -> Text(markdownInline(line.drop(4)), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                line.startsWith("## ") -> Text(markdownInline(line.drop(3)), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                line.startsWith("# ") -> Text(markdownInline(line.drop(2)), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                line.startsWith("- ") || line.startsWith("* ") -> Text(markdownInline("• ${line.drop(2)}"), style = MaterialTheme.typography.bodyMedium)
                line.matches(Regex("^\\d+\\.\\s+.*")) -> Text(markdownInline(line), style = MaterialTheme.typography.bodyMedium)
                line.startsWith("> ") -> Text(markdownInline(line.drop(2)), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodyMedium)
                line.isBlank() -> Text("")
                else -> Text(markdownInline(line), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

private fun markdownInline(text: String): AnnotatedString = buildAnnotatedString {
    val token = Regex("(\\*\\*.+?\\*\\*|`.+?`)")
    var cursor = 0
    token.findAll(text).forEach { match ->
        append(text.substring(cursor, match.range.first))
        val value = match.value
        if (value.startsWith("**")) {
            withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(value.removePrefix("**").removeSuffix("**")) }
        } else {
            withStyle(SpanStyle(fontFamily = FontFamily.Monospace, background = Color(0x1A000000))) { append(value.removePrefix("`").removeSuffix("`")) }
        }
        cursor = match.range.last + 1
    }
    append(text.substring(cursor))
}
