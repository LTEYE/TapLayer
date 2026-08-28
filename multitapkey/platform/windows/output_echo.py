"""近期输出回声登记：驱动级输出的自识别机制。

驱动级输出不带任何软件标记（dwExtraInfo=0，与物理键无法区分），
TapLayer 自身的低层钩子因此无法用 cookie 认领自己的输出。
本模块按"输出时登记、钩子按扫描码+方向+时限认领"的方式补位：

- 输出端（InterceptionBackend）在每次发送前后登记 (scan_code, E0, up)；
- 钩子回调对每个键盘事件先查登记表，命中且未超时则视为自身输出，
  不进状态机、不触发连击。

注意权衡：输出后 WINDOW_SECONDS 内用户手按同一键会被误吞。
窗口取 0.3 秒，覆盖一次完整 chord（按下+按住+松开）的开销。
"""

from __future__ import annotations

import collections
import threading
import time


class OutputEcho:
    """线程安全的近期输出登记表（consume-on-match）。"""

    WINDOW_SECONDS = 0.3

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: collections.deque = collections.deque()

    def record(
        self,
        scan_code: int,
        e0: bool,
        is_up: bool,
    ) -> None:
        """输出发出前登记一次击键。"""
        with self._lock:
            self._items.append(
                (
                    int(scan_code),
                    bool(e0),
                    bool(is_up),
                    time.monotonic(),
                )
            )

    def claim(
        self,
        scan_code: int,
        e0: bool,
        is_up: bool,
    ) -> bool:
        """钩子回调用：该事件是否为近期输出。命中则消费掉。"""
        now = time.monotonic()
        claimed = False

        with self._lock:
            while self._items:
                scan, e0f, upf, ts = (
                    self._items[0]
                )

                if now - ts > self.WINDOW_SECONDS:
                    self._items.popleft()
                    continue

                if (
                    scan == int(scan_code)
                    and e0f == bool(e0)
                    and upf == bool(is_up)
                ):
                    self._items.popleft()
                    claimed = True
                    break

                # 队首不匹配也不丢弃（乱序到达时仍可匹配后续事件），
                # 仅在整体超量时防积压
                if len(self._items) > 64:
                    self._items.popleft()
                break

        return claimed
