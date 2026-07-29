# Page dependency trees

## Holdings

Entry: `android/app/src/main/java/com/thirdhand/app/MainActivity.kt` → `HoldingsScreen`

Dependencies:

- `MainActivity.kt`
  - `HoldingTableRow`
  - `PositionValueCell`
  - `MarketStatusEntry`
  - `AnalysisEntry`
  - `HoldingEditor`
  - `ApiClient.kt`
  - `Theme.kt`

The active path is the `LazyColumn` in `HoldingsScreen`. Each position row is an editable compact table row with swipe-to-delete.

## Admin

Entry: `android/app/src/main/java/com/thirdhand/app/AdminDashboardScreen.kt`

Dependencies:

- `AdminDashboardScreen.kt`
  - `ApiClient.kt`
  - Material 3 components
  - Compose layout primitives
