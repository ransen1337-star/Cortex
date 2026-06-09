from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx


DEFAULT_REMOTE_IMAGE_ACCEPT = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
DEFAULT_REMOTE_IMAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": DEFAULT_REMOTE_IMAGE_ACCEPT,
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
DOUYIN_ASSET_REFERER = "https://www.douyin.com/"
BILIBILI_ASSET_REFERER = "https://www.bilibili.com/"
DOUYIN_ASSET_HOST_SUFFIXES = (
    "douyinpic.com",
    "douyinvod.com",
    "byteimg.com",
)
BILIBILI_ASSET_HOST_SUFFIXES = (
    "hdslb.com",
    "bilibili.com",
)


def create_http_client(timeout: int) -> httpx.Client:
    try:
        return httpx.Client(http2=True, follow_redirects=True, timeout=timeout)
    except ImportError:
        return httpx.Client(follow_redirects=True, timeout=timeout)


def coerce_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_published_at(timestamp: Any) -> datetime | None:
    if not isinstance(timestamp, int | float):
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def normalize_remote_asset_url(url: str | None) -> str | None:
    if not url:
        return None
    normalized_url = url.strip()
    if normalized_url.startswith("//"):
        return f"https:{normalized_url}"
    if normalized_url.startswith("http://"):
        return "https://" + normalized_url[len("http://"):]
    if normalized_url.startswith("https://"):
        return normalized_url
    return None


def host_matches_suffixes(host: str, suffixes: tuple[str, ...]) -> bool:
    return any(host == suffix or host.endswith(f".{suffix}") for suffix in suffixes)


def build_remote_asset_request_headers(url: str) -> dict[str, str]:
    headers = dict(DEFAULT_REMOTE_IMAGE_HEADERS)
    host = (urlsplit(url).netloc or "").lower()
    if host_matches_suffixes(host, DOUYIN_ASSET_HOST_SUFFIXES):
        headers["Referer"] = DOUYIN_ASSET_REFERER
    elif host_matches_suffixes(host, BILIBILI_ASSET_HOST_SUFFIXES):
        headers["Referer"] = BILIBILI_ASSET_REFERER
    return headers


def collect_platform_declaration_candidates(source: Any, keywords: list[str]) -> list[str]:
    candidates: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for nested_value in value.values():
                walk(nested_value)
            return
        if isinstance(value, list):
            for nested_value in value:
                walk(nested_value)
            return
        if not isinstance(value, str):
            return
        text = value.strip()
        if text and any(keyword in text for keyword in keywords):
            candidates.append(text)

    walk(source)
    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def format_count_short(value: int | None) -> str:
    if value is None:
        return "--"
    if value >= 100000000:
        return f"{value / 100000000:.1f}亿"
    if value >= 10000:
        return f"{value / 10000:.1f}万"
    return str(value)


def format_duration_clock(duration_seconds: int | None) -> str | None:
    if duration_seconds is None:
        return None
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"
