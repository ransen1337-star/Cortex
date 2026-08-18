"""Version metadata and non-blocking update checks."""

from dataclasses import dataclass
import os
import re
from typing import Literal

import httpx

from main.core.branding import PROJECT_VERSION


DEFAULT_VERSION_SOURCE_URL = (
    "https://raw.githubusercontent.com/ransen1337-star/Cortex/main/main/core/branding.py"
)
VERSION_PATTERN = re.compile(r'PROJECT_VERSION\s*=\s*["\']([^"\']+)["\']')
VersionStatus = Literal["current", "update_available", "unknown"]


@dataclass(frozen=True)
class VersionCheckResult:
    current_version: str
    latest_version: str | None
    status: VersionStatus
    source_url: str
    error: str | None = None


def check_for_update(*, client: httpx.Client | None = None) -> VersionCheckResult:
    source_url = os.getenv("CORTEX_VERSION_SOURCE_URL", DEFAULT_VERSION_SOURCE_URL)
    http_client = client or httpx.Client(follow_redirects=True, timeout=5)
    should_close = client is None
    try:
        response = http_client.get(source_url, headers={"Accept": "text/plain"})
        response.raise_for_status()
        latest_version = extract_version(response.text)
    except (httpx.HTTPError, ValueError) as error:
        return VersionCheckResult(
            current_version=PROJECT_VERSION,
            latest_version=None,
            status="unknown",
            source_url=source_url,
            error=str(error),
        )
    finally:
        if should_close:
            http_client.close()
    if latest_version is None:
        return VersionCheckResult(
            current_version=PROJECT_VERSION,
            latest_version=None,
            status="unknown",
            source_url=source_url,
            error="Remote version was not found",
        )
    status: VersionStatus = "update_available" if compare_versions(latest_version, PROJECT_VERSION) > 0 else "current"
    return VersionCheckResult(
        current_version=PROJECT_VERSION,
        latest_version=latest_version,
        status=status,
        source_url=source_url,
    )


def extract_version(source: str) -> str | None:
    match = VERSION_PATTERN.search(source)
    return match.group(1) if match else None


def compare_versions(left: str, right: str) -> int:
    left_parts = version_parts(left)
    right_parts = version_parts(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def version_parts(version: str) -> tuple[int, ...]:
    parts = [int(part) for part in re.findall(r"\d+", version)]
    parts = parts or [0]
    return tuple(parts + [0] * (3 - len(parts)))


def log_version_check(result: VersionCheckResult) -> None:
    if result.status == "update_available":
        print(f"[version] update available: {result.current_version} -> {result.latest_version}")
    elif result.status == "current":
        print(f"[version] current: {result.current_version}")
    else:
        print(f"[version] check unavailable: {result.current_version}")
