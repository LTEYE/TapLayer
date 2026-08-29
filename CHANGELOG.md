# Changelog

## 1.1.1 (2026-08-29)

- **In-app update download from the manual check**: the "Download" button in the update dialog now downloads the new exe in the background and installs it automatically on exit (previously it only opened the release page in a browser). Falls back to opening the release page when running from source or when the release has no exe asset.
- **Test button now shows the OSD popup**: clicking a gesture's "Test" button displays the same on-screen popup as a real trigger (`BindingName: OutputKeys`), and it shows **even when "Show output popup" is disabled in settings** — tests always give visual feedback.
- **Test output honors the configured output behavior**: repeat count and hold duration from the binding are used in tests (previously every test degenerated to a single tap). `Hold until release` degrades to a 1-second hold in tests, because there is no trigger key to release in that context.
- **Fixed**: the close dialog's ×/Esc roles were swapped — clicking × (or pressing Esc) minimized to the tray instead of canceling; both now cancel as expected.
- **Fixed**: several auto-update setting controls did not retranslate when switching the UI language at runtime.

## 1.1.0 (2026-08-28)

- **Output behavior per gesture**: besides "tap once", each output can be *repeat N times*, *hold for N ms*, or *hold until the trigger key is released*. Long-press triggers now default to a 1 s hold output (customizable). New "输出方式" (Output mode) selector in the binding editor.
- **Combo-key timing fix**: modifier+key outputs (e.g. `Alt+Q`) are sent key-by-key with zero inter-key gap, so the browser no longer treats the modifier as a standalone key. Batch arrays (multiple INPUTs in one SendInput call) are avoided because some environments (mouse-driver hooks / security software) silently reject them (SendInput returns 0).
- **Per-level tap-window fix**: the wait window for the next tap now uses the *current level's* `interval_ms` (e.g. the "1-tap" row's window governs the double-tap wait), instead of the next level's — previously a per-level window set on level 1 was ignored and fell back to the global value, turning double taps into two single taps.
- **Config backup & auto-restore**: every save maintains `config.json.bak`; if the main config gets corrupted, TapLayer auto-restores from the backup instead of silently resetting to defaults.
- **Dynamic whitelist**: the keyboard/mouse hooks now only process keys used as triggers (left/right modifiers expanded); all other keys pass through untouched, reducing overhead and stray state.
- **OSD hidden from screenshots**: the on-screen output popup is excluded from screen capture (SetWindowDisplayAffinity / WDA_EXCLUDEFROMCAPTURE), so it no longer shows up in screenshots.
- **Per-binding custom name**: each key binding can be renamed (「改名」button on the binding card). The OSD popup and binding card show the custom name, falling back to the trigger key. OSD format: `CustomName: OutputKey` (e.g. `开镜: Ctrl+Shift+S`).
- **Check for updates**: a "Check for updates" button in Settings queries the latest release (Gitee) and opens the download page when a new version exists.
- **Timing-value guards**: double-tap window and hold threshold are clamped to sane minimums (200 ms / 300 ms) on load, and the UI sliders can no longer reach pathological values that made single taps register as long-presses.
- **Output reliability**: per-key sends retry on failure and fall back to `keybd_event` (which some drivers/security software do not intercept); all pressed keys are guaranteed to be released even if a send fails mid-chord (no more stuck modifiers). The hook now ignores all injected input.
- **Auto-save on exit**: settings and bindings are silently saved when quitting, so "unsaved changes" no longer get lost.
- **Startup dirty-state fix**: the UI no longer reports spurious "unsaved changes" right after launch (a startup signal had been polluting the working config with default checkbox states).
- **Auto-update**: check for updates on startup and auto-download/auto-install options. Update source is GitHub (`LTEYE/TapLayer`) with automatic fallback to Gitee (`XKDMW/TapLayer`) after a timeout.
- **Force administrator**: the EXE embeds a `requireAdministrator` manifest — double-click launches elevated with a UAC prompt (needed to inject keys into elevated apps); README updated.
- **Startup via Scheduled Task**: "Start with Windows" now registers a login task with highest privileges (no UAC prompt at boot); startup launches hidden into the tray, and minimizing the window hides it to the tray.

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
