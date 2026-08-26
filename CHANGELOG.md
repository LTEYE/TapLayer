# Changelog

## 1.0.0 (2026-08-26)

- **Rebrand**: MultiTapKey → **TapLayer (击层)**.
- One trigger key with 1–9 tap levels + long press, each mapping to its own output key (chords supported).
- **Per-level tap window**: each tap level has an independent `interval_ms` (how many ms to press the next tap); long press has its own `hold_ms`; missing fields fall back to the global defaults. Old configs are fully compatible.
- Unified **Chord** model for triggers and outputs: order-independent (`A+S` = `S+A`), left/right modifiers canonicalized, duplicate triggers rejected at load and at record time.
- **Themes**: Light / Dark / Follow system (Windows dark-mode aware), with full QSS coverage for dialogs, menus, dropdowns, and status colors.
- Settings apply instantly with in-window toast feedback (top floating bar, auto-dismiss); the dirty state is computed by real comparison between the UI and the saved config — toggling a switch back to its original state no longer falsely marks the config as unsaved.
- **First-run onboarding**: explains the trigger-key mechanism, recommends low-usage keys / F13-F24 remaps / mouse side buttons, warns against Ctrl/Alt/Shift/Win, and highlights the trigger card for the user to record their first key.
- **Emergency pause hotkey**: global `Alt+Ctrl+F9` pauses/resumes TapLayer from anywhere (tray balloon notification).
- **Mouse buttons as triggers**: a low-level mouse hook (WH_MOUSE_LL) runs alongside the keyboard hook, so side buttons (X1/X2) and the middle button can be trigger keys. When recording a mouse button, it is captured only while the cursor hovers the highlighted key display area — UI stays fully clickable.
- **136 supported keys**: letters, digits, F1–F24, numpad, punctuation (OEM), menu key, browser/media/launcher keys, sleep, and mouse buttons.
- **Practical default configs**: three profiles — Daily (ScrollLock copy/paste, Insert undo/redo), Gaming (ScrollLock inventory/map, Pause reload/interact) and Work (Pause save/close, Insert find/find-next) — replacing the old demo binding.
- Donation dialog ("Support Us") with WeChat/Alipay QR + Ko-fi link, reachable from the settings panel and the tray menu.
- Localized UI: English and Simplified Chinese (180 keys, fully aligned).
- System tray (with theme-aware v2 logo), start with Windows, config import/export (transactional), single-instance lock.
- v2 logo assets (`assets/logo/`), embedded in the EXE icon and tray/window icons.
- 105+ unit tests.
