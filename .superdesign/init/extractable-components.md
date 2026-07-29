# Extractable UI components

## AppNavigation

- Source: `android/app/src/main/java/com/thirdhand/app/MainActivity.kt`
- Category: layout
- Description: Material 3 bottom navigation selecting the app section.
- Extractable props: `selectedTab`.
- Hardcoded: tab labels and Material icon choices.

## HoldingTableRow

- Source: `android/app/src/main/java/com/thirdhand/app/MainActivity.kt`
- Category: basic
- Description: high-density multi-currency position row with edit tap and left-swipe delete.
- Extractable props: holding values, quote, `isDeleteRevealed`.
- Hardcoded: column hierarchy, currency formatting, semantic error delete rail.
