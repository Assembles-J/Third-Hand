# Layouts

## Application shell

- Source: `android/app/src/main/java/com/thirdhand/app/MainActivity.kt`
- Compose `Scaffold` with a Material 3 `NavigationBar` at the bottom.
- Primary content switches among market, holdings, news, settings, and administration tabs.

```kotlin
Scaffold(bottomBar = {
    NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
        // NavigationBarItem instances select the active section.
    }
}) { padding ->
    Surface(
        modifier = Modifier.fillMaxSize().padding(padding),
        color = MaterialTheme.colorScheme.background,
    ) { /* selected screen */ }
}
```

The holdings screen is a `LazyColumn`: header/banner, compact status entries, table heading, then `HoldingTableRow` rows.
