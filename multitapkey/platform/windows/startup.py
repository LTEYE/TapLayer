"""Windows startup backend using Scheduled Tasks.

TapLayer 强制以管理员运行（UAC manifest）。注册表 Run 键自启的进程
是普通权限，启动时会被 UAC 拦截弹出确认框。任务计划以
``/RL HIGHEST`` 注册"登录时以最高权限运行"，可免弹窗直接以
管理员身份自启。创建/删除需要当前进程已提权（TapLayer 本身是
管理员进程，满足）。
"""

from __future__ import annotations

import subprocess
import sys


TASK_NAME = "TapLayer"

# 自启隐藏参数：任务计划带该参数启动，主窗口不显示，直接进托盘
HIDDEN_ARG = "--hidden"


class WindowsStartupBackend:
    def is_available(
        self,
    ) -> bool:
        return bool(
            getattr(
                sys,
                "frozen",
                False,
            )
        )

    def get_startup(
        self,
    ) -> bool:
        result = subprocess.run(
            [
                "schtasks",
                "/Query",
                "/TN",
                TASK_NAME,
            ],
            capture_output=True,
            text=True,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )

        return result.returncode == 0

    def set_startup(
        self,
        enabled: bool,
    ) -> None:
        if (
            enabled
            and not self.is_available()
        ):
            raise RuntimeError(
                "Startup is supported only "
                "for the packaged executable."
            )

        if enabled:
            # /RL HIGHEST：以最高权限运行，登录时免 UAC 弹窗。
            # /F：任务已存在时静默覆盖。
            result = subprocess.run(
                [
                    "schtasks",
                    "/Create",
                    "/TN",
                    TASK_NAME,
                    "/TR",
                    f'"{sys.executable}" {HIDDEN_ARG}',
                    "/SC",
                    "ONLOGON",
                    "/RL",
                    "HIGHEST",
                    "/F",
                ],
                capture_output=True,
                text=True,
                creationflags=0x08000000,  # CREATE_NO_WINDOW
            )

            if result.returncode != 0:
                raise RuntimeError(
                    "schtasks create failed: "
                    + (result.stderr or "").strip()
                )

            return

        result = subprocess.run(
            [
                "schtasks",
                "/Delete",
                "/TN",
                TASK_NAME,
                "/F",
            ],
            capture_output=True,
            text=True,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )

        if result.returncode != 0:
            # 任务不存在 = 已经是关闭状态，不算错误
            if "does not exist" not in (
                result.stderr or ""
            ).lower():
                raise RuntimeError(
                    "schtasks delete failed: "
                    + (result.stderr or "").strip()
                )
