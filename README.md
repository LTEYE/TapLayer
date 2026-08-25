# MultiTapKey

## 项目简介 (Introduction)

MultiTapKey is a lightweight, multi-tap gesture hotkey interpreter for Windows 10/11. It watches a single input key and turns one physical key press into four different shortcut outputs depending on how you tap it:

```text
One input key
    |
    +-- Single tap  -> action A
    +-- Double tap  -> action B
    +-- Triple tap  -> action C
    +-- Long press  -> action D
```

Out of the box it is designed for a Logitech G304X mouse whose on-board DPI button is remapped to emit `F24`, so a single mouse button becomes four shortcuts.

## 为什么存在 (Why it exists)

Most "multi-function key" tools are either heavy macro suites, require vendor software to keep running, or only support a fixed set of keys. MultiTapKey is intentionally minimal:

- It only *interprets* input the operating system has already received.
- It does not replace your mouse driver, does not modify firmware, and does not depend on Logitech G HUB.
- A single canonical key-name architecture keeps the gesture engine platform independent.

## 核心原理 (Core principle)

```text
Physical F24
    |
    v
Windows low-level keyboard hook (WH_KEYBOARD_LL)
    |
    v
Suppression latch (eat the original F24 so it never reaches other apps)
    |
    v
RawKeyEvent -> StateMachine (single / double / triple / long)
    |
    v
Action dispatcher
    |
    v
Windows SendInput emits the chosen gesture key (F23 / F24 / F22 / F21)
```

The gesture engine lives in `multitapkey/core` and never touches Windows, Qt, or `ctypes`. Only `multitapkey/platform/windows` knows about `VK`, `user32`, and `SendInput`.

## 架构 (Architecture)

```text
                    MultiTapKey
                         |
          +-------------+-------------+
          |             |             |
         Core          UI         Platform
          |             |             |
          |             |       +-----+------+
          |             |       |            |
          |             |   Interface    Windows
          |             |                    |
          |             |             Windows API
```

- **Core** — key names, state machine, actions, config, engine. Platform independent.
- **UI** — PySide6 window, capture dialog, system tray. No business logic.
- **Platform** — keyboard hook, send input, startup. Implements the backend contracts.

## Windows 支持 (Windows support)

MultiTapKey v0.1 officially supports Windows 10/11.

## 未来平台 (Future platforms)

The core architecture separates platform-independent gesture logic from platform-specific input backends.

Additional platform backends may be contributed independently in the future.

## 国际化 (Internationalization)

MultiTapKey v0.1 supports English and Simplified Chinese.

Language options:

```text
System
Simplified Chinese
English
```

The default is `System`, which follows the Windows locale (`zh_CN` for a Chinese locale, otherwise `en_US`).

## G304X

```text
G304X DPI
  |
  v
on-board F24
  |
  v
MultiTapKey
```

MultiTapKey does not require Logitech G HUB to remain running.

## 安装 (Install)

Requirements: Windows 10/11, Python >= 3.10.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 运行 (Run)

From the project root:

```powershell
.venv\Scripts\python.exe -m multitapkey
```

## 配置 (Configuration)

Configuration lives at `%APPDATA%\MultiTapKey\config.json`. It is saved atomically (write to a `.tmp` file, flush, `fsync`, then `os.replace`).

If the file is missing, a default configuration is created on first run. If the file is corrupt, MultiTapKey reports a configuration error and does **not** silently fall back to defaults.

## Profile

v0.1 ships three profiles:

```text
default   -> F24 single=F23, double=F24, triple=F22, long=F21
Gaming    -> (empty)
Work      -> (empty)
```

Only switching profiles is supported in v0.1 (no add / delete / rename).

## 手势 (Gestures)

| Gesture     | Default output |
|-------------|----------------|
| Single tap  | F23            |
| Double tap  | F24            |
| Triple tap  | F22            |
| Long press  | F21            |

A long press takes priority: if a press crosses the hold threshold, only `LONG` is produced. A fourth tap after a triple starts a new sequence.

## 暂停 (Pause)

The tray menu can pause and resume gesture interpretation. Pausing clears any pending gesture state and drains the input queue; new input is not intercepted while paused.

## 托盘 (Tray)

The system tray icon provides:

```text
Open MultiTapKey
Pause
Resume
Reload configuration
Import configuration
Export configuration
Exit
```

All menu entries are localized.

## Startup

MultiTapKey can start with Windows via the `HKCU\...\Run` registry key (used by the packaged EXE). In development mode the startup toggle is refused.

## 导入/导出 (Import / Export)

Configuration can be imported and exported as JSON. Import is transactional: a valid import becomes the only on-disk and runtime version; a failed import leaves the previous configuration intact.

## 测试 (Testing)

Unit tests run with pytest:

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

Real Windows behavior (keyboard hook, SendInput, gestures, G304X, Chinese/English UI) must be verified manually on Windows 10/11 and cannot be replaced by pytest.

## 构建 (Build)

```powershell
.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm --clean --onefile --windowed `
    --name MultiTapKey `
    --paths . `
    --add-data "multitapkey\i18n\translations;multitapkey\i18n\translations" `
    multitapkey\__main__.py
```

The output is `dist\MultiTapKey.exe`.

## 已知限制 (Known limitations)

```text
Windows 10/11 only for v0.1
UIPI
Administrator-privileged target application compatibility
F13-F24 require hardware / driver / other software to produce
Low Level Hook is affected by Windows system mechanisms
onefile EXE may trigger false positives from some antivirus software
```

When exiting, if a trigger key is physically held down, the system may see a `KEYUP` without a preceding `KEYDOWN` after the program exits; how the target application handles this unpaired input is up to that application.

## 贡献 (Contributing)

See [CONTRIBUTING.md](CONTRIBUTING.md).

## 许可证 (License)

License to be selected by the project owner. See [LICENSE_PLACEHOLDER](LICENSE_PLACEHOLDER).
