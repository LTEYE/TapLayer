# TapLayer · 击层

> [English](README.md) | 简体中文

> **⚠️ 本软件完全免费开源，永远免费。** 任何要求你付费购买 TapLayer 的行为都是骗局，请认准官方仓库/发布页下载。

**一个键，当 N 个键用。** TapLayer（击层）把"一个物理按键"变成最多 **10 层**：单击、双击、三击……一直数到 9 击，还有长按——**每一种按法，触发一个你自己的快捷键**。

鼠标侧键、被改造成 F24 的按键、甚至 `A+S` 这样的组合键，都可以变成一个"快捷键面板"。

**5 秒快速体验**：软件出厂自带三档实用配置——「日常」用 ScrollLock 双击复制、长按粘贴；「游戏」用 ScrollLock 双击开背包、长按开地图；「工作」用 Pause 双击保存、长按关闭。打开软件就能亲手试。

```text
一个输入键
    |
    +-- 1 击    -> 动作 A
    +-- 2 击    -> 动作 B
    +-- 3 击    -> 动作 C
    +-- ...
    +-- 9 击    -> 动作 I
    +-- 长按    -> 动作 J
```

## 为什么要用 TapLayer？

- **一个键 = 10 层**：1~9 击 + 长按，每一层都可以映射不同的输出键（支持组合键）。
- **每层独立"连击窗口"**：每一击级别可以单独设置"多少毫秒内按出下一击才算连击"；不设置就用全局默认值。旧配置文件完全兼容，不用改。
- **全组合键支持**：触发键和输出键都可以是组合键（如 `Ctrl+Shift+A`、`A+S`）。顺序自动归一（`A+S` 和 `S+A` 是同一个），左右修饰键自动统一。
- **鼠标侧键触发**：鼠标侧键（X1/X2）、中键可以直接当触发键——零干扰，比键盘低频键还顺手。录制鼠标键时把鼠标移到弹窗里的蓝色按键显示区点击即可。
- **支持 136 个按键**：字母、数字、F1-F24、小键盘、标点、浏览器/媒体/启动键、鼠标键，全收录。
- **首次使用引导**：第一次打开会引导你设置第一个触发键，并说明哪些键适合（低频键 / F13-F24 虚拟键 / 鼠标侧键）、哪些不适合（Ctrl/Alt/Shift/Win 会被接管）。
- **紧急逃生快捷键**：任何时候按 `Alt+Ctrl+F9` 可暂停/恢复 TapLayer，立即恢复键盘鼠标。
- **触发键冲突检查**：录制一个已经被别的绑定占用的触发键，立刻拒绝并提示。
- **主题**：浅色 / 深色 / 跟随系统。
- **双语界面**：简体中文和英文。
- **系统托盘**、开机自启、配置导入导出、单实例防重复启动。
- **轻量、干净**：纯 Python + PySide6 编写，不依赖任何厂商软件、不改固件、没有隐藏的宏引擎——它只"解释"系统已经收到的输入。
- **开源免费**——永远。

## 安装与运行（源码版）

要求：Windows 10/11，Python 3.10 或更高

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m multitapkey
```

## 配置文件

- 配置文件在 `%APPDATA%\TapLayer\config.json`。
- 保存是"原子"的（先写临时文件、同步磁盘、再改名替换）——保存中途断电/崩溃也不会损坏配置。
- 配置损坏时会**明确报错**，绝不会悄悄重置成默认。

## 打包成 EXE

```powershell
.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm --clean --onefile --windowed `
    --distpath dist --workpath build `
    --icon assets/logo/taplayer-logo-v2-dark-512.png `
    --add-data "multitapkey\i18n\translations;multitapkey\i18n\translations" `
    --add-data "assets;assets" `
    --name TapLayer `
    TapLayer.spec
```

输出：`dist\TapLayer.exe`。（单文件打包可能被部分杀毒软件误报——这是 PyInstaller 单文件的已知特性。）

## 测试

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

键盘钩子、鼠标钩子、按键输出、手势、界面这些真实 Windows 行为，仍需在真机上手动验证。

## 支持我们

如果这个软件对你有帮助，请我喝杯咖啡吧 ☕

[![ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Me-ff5e5b?logo=ko-fi&logoColor=white)](https://ko-fi.com/xkdmw)

| 微信 / 支付宝（国内） | Ko-fi（海外） |
|---|---|
| ![收款码](assets/support_qr.jpg) | <https://ko-fi.com/xkdmw> |

每一份心意都在支撑这个项目继续走下去。谢谢！

## 开源协议

**GPL-3.0** —— [查看完整协议](LICENSE)。

免费使用、修改、分发；任何基于 TapLayer 的修改版本也必须以 GPL-3.0 开源（防闭源吞并）。作者保留全部版权，可另行提供商业授权（双授权模式）。
