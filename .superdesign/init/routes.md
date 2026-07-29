# Screens / routes

This is a single-activity Android Compose app; navigation is tab-state based rather than URL routing.

| Screen | Entry source | Layout |
| --- | --- | --- |
| Market / Today | `MainActivity.kt` `TodayScreen` | list with market cards |
| Holdings | `MainActivity.kt` `HoldingsScreen` | dense `LazyColumn` holdings table |
| News | `MainActivity.kt` | announcement and news lists |
| Settings | `MainActivity.kt` | settings list |
| Admin | `AdminDashboardScreen.kt` | dark operational console |

The current visual target is the Holdings screen. `HoldingTableRow` owns its row-level left-swipe delete interaction.
