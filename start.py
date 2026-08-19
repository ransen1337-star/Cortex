import uvicorn

from main.core.runtime import build_runtime_urls
from main.core.runtime import resolve_host
from main.core.runtime import resolve_port
from main.core.changelog import print_changelog
from main.core.version import check_for_update
from main.core.version import log_version_check


ASCII_BANNER = r"""
=====================================================
 ▄████▄   ▒█████   ██▀███  ▄▄▄█████▓▓█████ ▒██   ██▒
▒██▀ ▀█  ▒██▒  ██▒▓██ ▒ ██▒▓  ██▒ ▓▒▓█   ▀ ▒▒ █ █ ▒░
▒▓█    ▄ ▒██░  ██▒▓██ ░▄█ ▒▒ ▓██░ ▒░▒███   ░░  █   ░
▒▓▓▄ ▄██▒▒██   ██░▒██▀▀█▄  ░ ▓██▓ ░ ▒▓█  ▄  ░ █ █ ▒ 
▒ ▓███▀ ░░ ████▓▒░░██▓ ▒██▒  ▒██▒ ░ ░▒████▒▒██▒ ▒██▒
░ ░▒ ▒  ░░ ▒░▒░▒░ ░ ▒▓ ░▒▓░  ▒ ░░   ░░ ▒░ ░▒▒ ░ ░▓ ░
  ░  ▒     ░ ▒ ▒░   ░▒ ░ ▒░    ░     ░ ░  ░░░   ░▒ ░
░        ░ ░ ░ ▒    ░░   ░   ░         ░    ░    ░  
░ ░          ░ ░     ░                 ░  ░ ░    ░  
░                                      
=====================================================               
"""


def run_version_check() -> None:
    print_changelog()
    log_version_check(check_for_update())


if __name__ == "__main__":
    run_version_check()

    from main import PROJECT_SIGNATURE
    from main import app

    host = resolve_host()
    port = resolve_port()
    urls = build_runtime_urls(host, port)
    print(ASCII_BANNER, flush=True)
    print(f"[project] {PROJECT_SIGNATURE}", flush=True)
    print(f"[listen] {urls.base}", flush=True)
    print(f"[docs]   {urls.docs}", flush=True)
    uvicorn.run(
        app,
        host=host,
        port=port,
    )
