<div align="center">

<img src="assets/cortex-logo.svg" alt="Cortex logo" width="240">

# Cortex

**Cortex, a lightweight public source code project for Bilibili and Douyin video analysis**

<p>
  <a href="README.en.md"><strong>English</strong></a>
  &nbsp;|&nbsp;
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063" alt="Pydantic">
  <img src="https://img.shields.io/badge/Logo-3D%20Cube-0EA5E9" alt="3D Cube Logo">
  <img src="https://img.shields.io/badge/Mode-API--only-2563EB" alt="Mode">
</p>

</div>

## Overview

Cortex publishes source code for parsing public video links and returning normalized metadata, engagement metrics, source URLs, and SVG share cards in a consistent format.

The repository stays intentionally compact: `start.py` remains at the root, while all source code, assets, docs, and dependencies live inside `main/`.

> #### <img src="assets/callout-important.svg" alt="" width="18" align="absmiddle"> IMPORTANT
>
> - This project is for public-link analysis only
> - Private content and login-only content are out of scope
> - Public Douyin share pages may not expose a reliable real play count
> - If you ship this publicly, add rate limits, caching, logs, and source restrictions

> #### <img src="assets/callout-warning.svg" alt="" width="18" align="absmiddle"> WARNING
>
> - Public platform markup can change at any time
> - Upstream rate limits, signed requests, or expired media may temporarily affect field quality

> #### <img src="assets/callout-tip.svg" alt="" width="18" align="absmiddle"> TIP
>
> - Prefer full public URLs for best parser stability
> - Use `/docs` after startup for live endpoint debugging
> - Add caching and request throttling before production use

## Features

- Parse public Bilibili and Douyin video links
- Filter and recognize valid links before platform parsing
- Return a clean shared response structure
- Generate SVG share cards for both platforms
- Expose Swagger documentation at `/docs`
- Preserve project attribution as `Cortex by Ransen1337-star`

## Supported Example Links

- Bilibili examples only use `https://www.bilibili.com/video/BV15kVJzYE5N/`
- Douyin examples only use `https://www.iesdouyin.com/share/video/7634486870264597775/`
- Full public URLs are recommended for best parsing stability

## Quick Start

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r main/requirements.txt
python start.py
```

Default endpoints:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## API Examples

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Analyze a Bilibili video:

```bash
curl "http://127.0.0.1:8000/api/v1/bilibili/video-analysis?url=https%3A%2F%2Fwww.bilibili.com%2Fvideo%2FBV15kVJzYE5N%2F"
```

Analyze a Douyin video:

```bash
curl "http://127.0.0.1:8000/api/v1/douyin/video-analysis?url=https%3A%2F%2Fwww.iesdouyin.com%2Fshare%2Fvideo%2F7634486870264597775%2F"
```

Render a share card:

```bash
curl "http://127.0.0.1:8000/api/v1/bilibili/share-card?url=https%3A%2F%2Fwww.bilibili.com%2Fvideo%2FBV15kVJzYE5N%2F" -o share-card.svg
```

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

- `api/` contains FastAPI routes and example response payloads
- `core/` contains branding and runtime configuration helpers
- `services/` contains platform parsers, shared models, utilities, and share-card rendering
- `tests/` contains API and parser regression tests

## Notes

- Parsing quality depends on upstream public page structure
- Some Douyin metrics may be limited by upstream public responses

## License

Cortex is source-available under `PolyForm Noncommercial 1.0.0`.

- English license: [../LICENSE](../LICENSE)
- Chinese reference: [../LICENSE.zh-CN.md](../LICENSE.zh-CN.md)
- Commercial use is not allowed without separate permission
- Redistributing original or modified copies must keep attribution as `Cortex by Ransen1337-star`
- Required notices must be preserved from the repository root `NOTICE`
- The `Cortex` name and logo are not licensed as trademarks; see `TRADEMARKS.md`

---

❤️‍🩹 Thank you for using Cortex, Built with ❤️ by Ransen1337-star
