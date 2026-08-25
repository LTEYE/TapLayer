"""Windows HKCU Run startup backend."""

from __future__ import annotations

import sys
import winreg


VALUE_NAME = "MultiTapKey"

RUN_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Run"
)


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
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                winreg.KEY_QUERY_VALUE,
            ) as key:
                winreg.QueryValueEx(
                    key,
                    VALUE_NAME,
                )
                return True

        except OSError:
            return False

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

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key,
                    VALUE_NAME,
                    0,
                    winreg.REG_SZ,
                    f'"{sys.executable}"',
                )
                return

            try:
                winreg.DeleteValue(
                    key,
                    VALUE_NAME,
                )
            except FileNotFoundError:
                return
