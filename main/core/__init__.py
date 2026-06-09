from main.core.branding import PROJECT_AUTHOR
from main.core.branding import PROJECT_DESCRIPTION
from main.core.branding import PROJECT_NAME
from main.core.branding import PROJECT_SIGNATURE
from main.core.branding import PROJECT_TAGLINE
from main.core.runtime import RuntimeUrls
from main.core.runtime import build_runtime_urls
from main.core.runtime import resolve_display_host
from main.core.runtime import resolve_host
from main.core.runtime import resolve_port

__all__ = [
    "app",
    "create_app",
    "PROJECT_AUTHOR",
    "PROJECT_DESCRIPTION",
    "PROJECT_NAME",
    "PROJECT_SIGNATURE",
    "PROJECT_TAGLINE",
    "RuntimeUrls",
    "build_runtime_urls",
    "resolve_display_host",
    "resolve_host",
    "resolve_port",
]


def __getattr__(name: str):
    if name == "app":
        from main.api.app import app

        return app
    if name == "create_app":
        from main.api.app import create_app

        return create_app
    raise AttributeError(f"module 'main.core' has no attribute {name!r}")
