import uvicorn

from main import app
from main import PROJECT_SIGNATURE
from main.core.runtime import build_runtime_urls
from main.core.runtime import resolve_host
from main.core.runtime import resolve_port


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


if __name__ == "__main__":
    host = resolve_host()
    port = resolve_port()
    urls = build_runtime_urls(host, port)
    print(ASCII_BANNER)
    print(f"[project] {PROJECT_SIGNATURE}")
    print(f"[listen] {urls.base}")
    print(f"[docs]   {urls.docs}")
    uvicorn.run(
        app,
        host=host,
        port=port,
    )
