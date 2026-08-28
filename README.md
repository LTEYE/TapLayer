# TapLayer · 击层

> English | [简体中文](README.zh-CN.md)

> **⚠️ Free & open source — forever.** If anyone asks you to pay for TapLayer, it's a scam. Only download from the official repository / release pages.

**One key, many shortcuts.** TapLayer turns a single physical key into up to **10 layers** — single tap, double tap, triple tap … up to 9 taps, and long press — and each layer triggers its own shortcut. A mouse side button, an F24 remap, or even a chord like `A+S` can become a whole shortcut panel.

![TapLayer main window — binding editor showing two mouse side-button bindings](assets/screenshots/screenshot-main-en.png)

**Try it in 5 seconds:** the out-of-box config ships with three practical profiles — "Daily" (ScrollLock double-tap = copy, long-press = paste), "Gaming" (ScrollLock double-tap = inventory, long-press = map) and "Work" (Pause double-tap = save, long-press = close). Launch the app and feel it yourself.

```text
One input key
    |
    +-- 1 tap      -> action A
    +-- 2 taps     -> action B
    +-- 3 taps     -> action C
    +-- ...
    +-- 9 taps     -> action I
    +-- long press -> action J
```

## Why TapLayer?

- **1 key → 10 layers**: 1–9 taps + long press, each with its own output key (chords supported).
- **Per-layer tap window**: each tap level has its own "tap window" — how many milliseconds you have to press the next tap — with a global default as fallback. Old configs work unchanged.
- **Output modes per gesture**: each tap level can output once, repeat N times, hold for N ms, or hold until you release the trigger key. Long-press now defaults to a 1 s hold output (customizable).
- **Chords everywhere**: triggers and outputs can both be chords (`Ctrl+Shift+A`, `A+S`). Order is normalized (`A+S` = `S+A`), left/right modifiers are canonicalized.
- **Mouse buttons as triggers**: side buttons (X1/X2) and middle button can be used directly as trigger keys — zero conflict. To record a mouse button, move the cursor over the highlighted (blue) key display area in the recorder dialog and click.
- **136 keys supported**: letters, digits, F1-F24, numpad, punctuation, browser/media/launcher keys, and mouse buttons.
- **First-run onboarding**: the first launch guides you through setting your first trigger key and explains which keys are suitable (low-usage keys / F13-F24 virtual keys / mouse side buttons) and which are not (Ctrl/Alt/Shift/Win get intercepted).
- **Emergency pause hotkey**: press `Alt+Ctrl+F9` anytime to pause/resume TapLayer and instantly restore your keyboard and mouse.
- **Duplicate trigger detection**: recording a trigger already used by another binding is rejected immediately.
- **Custom binding names**: rename any binding — the OSD popup and binding card show your name (e.g. `开镜: Ctrl+Shift+S`) instead of just the key.
- **Themes**: Light / Dark / Follow system.
- **Localized**: English and Simplified Chinese UI.
- **System tray**, start with Windows (via a scheduled task — no UAC prompt at boot), config import/export, single-instance lock.
- **Auto-update**: checks for new releases on startup (GitHub with automatic fallback to Gitee) and can download & install updates automatically.
- **Lightweight & honest**: pure Python + PySide6, no vendor software, no firmware changes, no hidden macro engine. It only interprets input the OS already received.
- **Open source & free** — forever.

## Install & Run (from source)

Requirements: Windows 10/11, Python >= 3.10

> **Administrator privileges required**: TapLayer injects keys into other programs, and Windows blocks normal-privilege processes from sending keys to elevated ones. Please **run as administrator**. The release EXE embeds a "require administrator" manifest — double-clicking launches it elevated (a one-time UAC prompt is expected).

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m multitapkey
```

## Configuration

- Config lives at `%APPDATA%\TapLayer\config.json`.
- Saved atomically (write `.tmp`, flush, `fsync`, `os.replace`) — a crash mid-save never corrupts the file.
- Every save maintains a backup (`config.json.bak`); if the config gets corrupted, TapLayer **auto-restores from the backup** on startup instead of silently resetting to defaults.

## Build the EXE

```powershell
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean TapLayer.spec
```

Output: `dist\TapLayer.exe`. (The EXE may trigger false positives from some antivirus software — a known quirk of onefile PyInstaller builds.)
The EXE embeds a `requireAdministrator` manifest (`TapLayer.manifest`) — double-clicking launches it elevated with a UAC prompt, no need to right-click "Run as administrator".

## Testing

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

Real Windows behavior (keyboard hook, mouse hook, SendInput, gestures, UI) must still be verified manually.

## Support Us

If TapLayer helps you, you can buy me a coffee ☕

[![ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Me-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/xkdmw)

| WeChat / Alipay (CN) | Ko-fi (overseas) |
|---|---|
| ![QR](assets/support_qr.jpg) | <https://ko-fi.com/xkdmw> |

Every little bit keeps the project alive. Thank you!

## License

**GPL-3.0** — see the full text in [LICENSE](LICENSE).

Free to use, modify and redistribute; any modified version of TapLayer must also be open source under GPL-3.0 (no closed-source forks). The author retains full copyright and may offer commercial licensing separately (dual-licensing model).
