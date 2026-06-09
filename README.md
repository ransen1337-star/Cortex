<div align="center">

<img src="main/assets/cortex-logo.svg" alt="Cortex logo" width="240">

# Cortex

**Cortex, a public source code project for Bilibili and Douyin video analysis**

<p>
  <a href="README.en.md"><strong>English</strong></a>
  &nbsp;|&nbsp;
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063" alt="Pydantic">
  <img src="https://img.shields.io/badge/Layout-start.py%20%2B%20main-0F766E" alt="Layout">
</p>

</div>

## Overview

Cortex is a compact FastAPI source code project for parsing public Bilibili and Douyin video links, returning normalized metadata, and rendering SVG share cards.

The repository keeps the root intentionally clean:

- `start.py` as the only startup entry
- `main/` for source code, assets, tests, and runtime dependencies
- `README.md`, `README.en.md`, and `README.zh-CN.md` as the only public docs at the root

## Readme

- English: [README.en.md](README.en.md)
- 简体中文: [README.zh-CN.md](README.zh-CN.md)

## Quick Start

```bash
pip install -r main/requirements.txt
python start.py
```

Default local URLs:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

> #### <img src="main/assets/callout-important.svg" alt="" width="18" align="absmiddle"> IMPORTANT
>
> - Public links only
> - Private or login-only content is not supported
> - Douyin public pages may not expose a reliable real play count
>
> - Attribution must remain as `Cortex by Ransen1337-star` when redistributing this source code

## Structure

```text
.
|-- LICENSE
|-- LICENSE.zh-CN.md
|-- NOTICE
|-- README.md
|-- README.en.md
|-- README.zh-CN.md
|-- TRADEMARKS.md
|-- main/
|   |-- api/
|   |-- assets/
|   |-- core/
|   |-- services/
|   |-- tests/
|   |-- requirements.txt
|   `-- __init__.py
`-- start.py
```

- `main/api/` keeps FastAPI routes and OpenAPI examples
- `main/core/` keeps branding and runtime configuration helpers
- `main/services/` keeps platform parsers, models, utilities, and share-card rendering
- `main/tests/` keeps parser and API regression tests

## License

Cortex is source-available under `PolyForm Noncommercial 1.0.0`.

- English license: [LICENSE](LICENSE)
- Chinese reference: [LICENSE.zh-CN.md](LICENSE.zh-CN.md)
- Commercial use is not allowed without separate permission
- Redistributions and modified copies must keep attribution as `Cortex by Ransen1337-star`
- Required notices in [NOTICE](NOTICE) must be preserved
- The `Cortex` name and logo are not granted as trademark rights; see [TRADEMARKS.md](TRADEMARKS.md)

---

❤️‍🩹 感谢您使用 Cortex，Built with ❤️ by Ransen1337-star
