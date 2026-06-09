<div align="center">

<img src="assets/cortex-logo.svg" alt="Cortex logo" width="228">

# Cortex

**Cortex, a clean public source code project for Bilibili and Douyin video analysis**

<p>
  <a href="README.en.md"><strong>English</strong></a>
  &nbsp;|&nbsp;
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063" alt="Pydantic">
  <img src="https://img.shields.io/badge/Layout-main%2F-only-0F766E" alt="Layout">
</p>

</div>

## Language

| Language | Open |
| --- | --- |
| English | [README.en.md](README.en.md) |
| 简体中文 | [README.zh-CN.md](README.zh-CN.md) |

## Overview

Cortex is a public source code project that parses public Bilibili and Douyin links, returns normalized metadata, and generates SVG share cards.

The repository root only keeps `start.py`. Source code, assets, docs, and runtime dependencies live under `main/`.

## Quick Start

```bash
pip install -r main/requirements.txt
python start.py
```

> #### <img src="assets/callout-important.svg" alt="" width="18" align="absmiddle"> IMPORTANT
>
> - Public links only
> - Private or login-only content is not supported
> - Douyin public share pages may not expose a reliable real play count

> #### <img src="assets/callout-warning.svg" alt="" width="18" align="absmiddle"> WARNING
>
> - Public platform responses can change without notice
> - Some upstream metrics may be limited or unstable

> #### <img src="assets/callout-tip.svg" alt="" width="18" align="absmiddle"> TIP
>
> - Prefer full public URLs
> - Use `/docs` for quick endpoint testing

## Features

- Parse public Bilibili and Douyin video links
- Filter and recognize supported links before platform parsing
- Return a shared response structure for downstream use
- Generate SVG share cards for both platforms
- Keep the root structure minimal with `start.py` plus `main/`

## Supported Example Links

- Bilibili examples only use `https://www.bilibili.com/video/BV15kVJzYE5N/`
- Douyin examples only use `https://www.iesdouyin.com/share/video/7634486870264597775/`

## Project Structure

```text
main/
|-- api/
|-- assets/
|-- core/
|-- services/
|-- tests/
|-- README.md
|-- README.en.md
|-- README.zh-CN.md
|-- requirements.txt
`-- __init__.py
```

- `api/` contains FastAPI routes and example payload definitions
- `core/` contains branding and runtime configuration helpers
- `services/` contains platform parsers, shared models, utilities, and share-card rendering
- `tests/` contains API and parser regression tests

## Project Attribution

Redistributions and modified copies must keep the project attribution as `Cortex by Ransen1337-star`.

## License

Cortex is source-available under `PolyForm Noncommercial 1.0.0`.

- English license: [../LICENSE](../LICENSE)
- Chinese reference: [../LICENSE.zh-CN.md](../LICENSE.zh-CN.md)
- No commercial use without separate permission
- Redistributing copies or modified versions must keep attribution as `Cortex by Ransen1337-star`
- Required notices must be preserved from the repository root `NOTICE`
- The `Cortex` name and logo are not licensed as trademarks

---

❤️‍🩹 感谢您使用 Cortex，Built with ❤️ by Ransen1337-star
