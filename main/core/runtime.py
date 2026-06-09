import os
from dataclasses import dataclass


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


@dataclass(frozen=True)
class RuntimeUrls:
    base: str
    docs: str
    openapi: str
    health: str


def resolve_host() -> str:
    return os.getenv("CORTEX_HOST") or os.getenv("VIDEO_ANALYSIS_HOST", DEFAULT_HOST)


def resolve_port() -> int:
    return int(os.getenv("CORTEX_PORT") or os.getenv("VIDEO_ANALYSIS_PORT", str(DEFAULT_PORT)))


def resolve_display_host(host: str) -> str:
    return DEFAULT_HOST if host == "0.0.0.0" else host


def build_runtime_urls(host: str, port: int) -> RuntimeUrls:
    base_url = f"http://{resolve_display_host(host)}:{port}"
    return RuntimeUrls(
        base=base_url,
        docs=f"{base_url}/docs",
        openapi=f"{base_url}/openapi.json",
        health=f"{base_url}/health",
    )
