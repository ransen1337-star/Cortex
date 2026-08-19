import uvicorn
from threading import Thread

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
    log_version_check(check_for_update())
    print_changelog()


if __name__ == "__main__":
    from main import PROJECT_SIGNATURE
    from main import app

    host = resolve_host()
    port = resolve_port()
    urls = build_runtime_urls(host, port)
    print(ASCII_BANNER)
    print(f"[project] {PROJECT_SIGNATURE}")
    print(f"[listen] {urls.base}")
    print(f"[docs]   {urls.docs}")
    Thread(target=run_version_check, name="cortex-version-check", daemon=True).start()
    uvicorn.run(
        app,
        host=host,
        port=port,
    )
