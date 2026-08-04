package com.thirdhand.app.researchchat

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.material3.MaterialTheme
import com.mikepenz.markdown.m3.Markdown
import com.mikepenz.markdown.m3.markdownTypography

/** Full CommonMark renderer with Material 3 styling; streamed updates retain the prior layout. */
@Composable
fun ResearchMarkdown(markdown: String, modifier: Modifier = Modifier) {
    Markdown(
        content = markdown,
        modifier = modifier,
        typography = markdownTypography(
            h1 = MaterialTheme.typography.titleLarge,
            h2 = MaterialTheme.typography.titleMedium,
            h3 = MaterialTheme.typography.titleSmall,
            h4 = MaterialTheme.typography.bodyLarge,
        ),
    )
}
