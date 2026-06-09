from main.core.branding import PROJECT_AUTHOR
from main.core.branding import PROJECT_NAME
from main.core.branding import PROJECT_SIGNATURE

__all__ = ["app", "create_app", "PROJECT_AUTHOR", "PROJECT_NAME", "PROJECT_SIGNATURE"]


def __getattr__(name: str):
    if name == "app":
        from main.api.app import app

        return app
    if name == "create_app":
        from main.api.app import create_app

        return create_app
    raise AttributeError(f"module 'main' has no attribute {name!r}")
