"""Update check: GitHub Releases (primary) with Gitee fallback.

老板拍板（2026-08-28）：优先 https://github.com/LTEYE/TapLayer，
GitHub 请求 1 分钟内失败自动切换 https://gitee.com/XKDMW/TapLayer。
检查 = 请求 Releases 最新 tag，与本地版本号对比。
"""

from __future__ import annotations

import json
import logging
import urllib.request

from multitapkey import __version__

log = logging.getLogger(__name__)

GITHUB_OWNER = "LTEYE"
GITHUB_REPO = "TapLayer"
GITEE_OWNER = "XKDMW"
GITEE_REPO = "TapLayer"

GITHUB_API_URL = (
    "https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
)
GITEE_API_URL = (
    "https://gitee.com/api/v5/repos/"
    f"{GITEE_OWNER}/{GITEE_REPO}/releases/latest"
)
GITHUB_PAGE_URL = (
    "https://github.com/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/releases"
)
GITEE_PAGE_URL = (
    "https://gitee.com/"
    f"{GITEE_OWNER}/{GITEE_REPO}/releases"
)

# GitHub 1 分钟超时失败 → 切 Gitee（老板拍板）
GITHUB_TIMEOUT_S = 60.0
GITEE_TIMEOUT_S = 30.0

# 自动下载/更新的分块大小
_DOWNLOAD_CHUNK = 64 * 1024


def _parse_version(
    raw: str,
) -> tuple[int, ...]:
    parts = []

    for chunk in raw.split("."):
        digits = "".join(
            ch
            for ch in chunk
            if ch.isdigit()
        )
        parts.append(
            int(digits) if digits else 0
        )

    return tuple(parts)


def compare_versions(
    a: str,
    b: str,
) -> int:
    """比较两个版本号：a>b 返回 1，a==b 返回 0，a<b 返回 -1。

    "1.0" 与 "1.0.0" 视为相等（尾部 0 对齐后比较）。
    """
    pa = _parse_version(a)
    pb = _parse_version(b)

    length = max(
        len(pa),
        len(pb),
    )

    pa += (0,) * (
        length - len(pa)
    )
    pb += (0,) * (
        length - len(pb)
    )

    for x, y in zip(pa, pb):
        if x > y:
            return 1
        if x < y:
            return -1

    return 0


def _exe_asset_url(
    assets,
) -> str:
    """从 releases assets 里挑出 exe 下载地址（优先名字含 TapLayer 的）。"""
    if not assets:
        return ""

    exe_urls = [
        str(asset.get("browser_download_url", ""))
        for asset in assets
        if str(
            asset.get("name", "")
        ).lower().endswith(".exe")
    ]

    if not exe_urls:
        return ""

    for url in exe_urls:
        if "tap" in url.lower():
            return url

    return exe_urls[0]


def _fetch_latest(
    api_url: str,
    page_url: str,
    timeout: float,
) -> tuple[bool, str, str, str]:
    """请求单个源；返回 (ok, latest, exe_url, page_url)。"""
    try:
        request = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": (
                    "TapLayer/" + __version__
                )
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )
    except Exception as exc:
        log.warning(
            "update source failed (%s): %s",
            api_url,
            exc,
        )
        return (
            False,
            "",
            "",
            "",
        )

    tag = str(
        data.get("tag_name", "")
    ).strip()

    latest = tag.lstrip("vV")

    if not latest:
        log.warning(
            "update source returned empty tag (%s)",
            api_url,
        )
        return (
            False,
            "",
            "",
            "",
        )

    exe_url = _exe_asset_url(
        data.get("assets") or []
    )

    return (
        True,
        latest,
        exe_url,
        page_url,
    )


def check_for_update() -> tuple[bool, str, str, str]:
    """检查更新：GitHub 优先，1 分钟失败自动切 Gitee。

    返回 (ok, latest_version, exe_download_url, release_page_url)。
    ok=True 且 latest 非空 = 检查成功；exe_download_url 为空表示
    发布里没有 exe 资产（自动更新不可用，只能去发布页手动下载）。
    """
    ok, latest, exe_url, page = _fetch_latest(
        GITHUB_API_URL,
        GITHUB_PAGE_URL,
        GITHUB_TIMEOUT_S,
    )

    if ok:
        return (
            True,
            latest,
            exe_url,
            page,
        )

    log.info(
        "GitHub update check failed; "
        "falling back to Gitee"
    )

    return _fetch_latest(
        GITEE_API_URL,
        GITEE_PAGE_URL,
        GITEE_TIMEOUT_S,
    )


def download_update(
    url: str,
    dest_path: str,
    timeout: float = 60.0,
) -> None:
    """下载最新版 exe 到 dest_path；失败抛异常。"""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "TapLayer/" + __version__
            )
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:
        with open(
            dest_path,
            "wb",
        ) as handle:
            while True:
                chunk = response.read(
                    _DOWNLOAD_CHUNK
                )

                if not chunk:
                    break

                handle.write(chunk)
