import uvicorn

from main import app
from main.core.runtime import build_runtime_urls
from main.core.runtime import resolve_host
from main.core.runtime import resolve_port


ASCII_BANNER = r"""
 _    ___     _                 ___                _           _
| |  / (_)   | |               / _ \              | |         (_)
| | / / _  __| | ___  ___     / /_\ \_ __   __ _| |_   _ ___ _ ___
| |/ / | |/ _` |/ _ \/ _ \    |  _  | '_ \ / _` | | | | / __| / __|
|   <  | | (_| |  __/ (_) |   | | | | | | | (_| | | |_| \__ \ \__ \
|_|\_\ |_|\__,_|\___|\___/    \_| |_/_| |_|\__,_|_|\__, |___/_|___/
                                                     __/ |
                                                    |___/
"""


if __name__ == "__main__":
    host = resolve_host()
    port = resolve_port()
    urls = build_runtime_urls(host, port)
    print(ASCII_BANNER)
    print(f"[listen] {urls.base}")
    print(f"[docs]   {urls.docs}")
    uvicorn.run(
        app,
        host=host,
        port=port,
    )
