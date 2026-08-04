package com.thirdhand.app.researchchat

import androidx.compose.runtime.Composable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.ui.Modifier
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

/**
 * Deliberately conservative renderer for streamed research text.
 *
 * The former third-party Markdown renderer was compiled against a different
 * Compose binary API and caused a production `NoSuchMethodError` in BasicText.
 * Research content remains readable while avoiding that incompatible runtime.
 */
@Composable
fun ResearchMarkdown(markdown: String, modifier: Modifier = Modifier) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        markdown.lines().forEach { rawLine ->
            val line = rawLine.trimEnd()
            when {
                line.startsWith("### ") -> Text(markdownInline(line.removePrefix("### ")), style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                line.startsWith("## ") -> Text(markdownInline(line.removePrefix("## ")), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                line.startsWith("# ") -> Text(markdownInline(line.removePrefix("# ")), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                line.startsWith("- ") || line.startsWith("* ") -> Text(markdownInline("• ${line.drop(2)}"), style = MaterialTheme.typography.bodyMedium)
                line.isNotBlank() -> Text(markdownInline(line), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

private fun markdownInline(value: String) = buildAnnotatedString {
    var cursor = 0
    while (cursor < value.length) {
        val opening = value.indexOf("**", cursor)
        if (opening < 0) { append(value.substring(cursor)); break }
        append(value.substring(cursor, opening))
        val closing = value.indexOf("**", opening + 2)
        if (closing < 0) { append(value.substring(opening)); break }
        withStyle(SpanStyle(fontWeight = FontWeight.Bold)) { append(value.substring(opening + 2, closing)) }
        cursor = closing + 2
    }
}

/** Streaming uses one stable text node; Markdown decoration waits for completion. */
@Composable
fun StreamingResearchText(text: String, modifier: Modifier = Modifier) {
    Text(text = text, modifier = modifier, style = MaterialTheme.typography.bodyMedium)
}
