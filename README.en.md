<div align="center">

<img src="main/assets/cortex-logo.svg" alt="Cortex logo" width="420">

# Cortex

**Cortex, a lightweight public source code project for Bilibili and Douyin video analysis**

<p>
  <a href="README.md"><strong>Overview</strong></a>
  &nbsp;|&nbsp;
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063" alt="Pydantic">
  <img src="https://img.shields.io/badge/Mode-API--only-2563EB" alt="Mode">
</p>

</div>

## Overview

Cortex publishes source code for parsing public video links and returning normalized metadata, engagement metrics, source URLs, and SVG share cards in a consistent format.

The repository stays intentionally compact: `start.py` remains at the root, while all source code, assets, docs, and dependencies live inside `main/`.

## Readme

- Overview: [README.md](README.md)
- 简体中文: [README.zh-CN.md](README.zh-CN.md)

> #### <img src="main/assets/callout-important.svg" alt="" width="18" align="absmiddle"> IMPORTANT
>
> - This project is for public-link analysis only
> - Private content and login-only content are out of scope
> - Public Douyin share pages may not expose a reliable real play count
> - If you ship this publicly, add rate limits, caching, logs, and source restrictions

> #### <img src="main/assets/callout-warning.svg" alt="" width="18" align="absmiddle"> WARNING
>
> - Public platform markup can change at any time
> - Upstream rate limits, signed requests, or expired media may temporarily affect field quality

> #### <img src="main/assets/callout-tip.svg" alt="" width="18" align="absmiddle"> TIP
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

## Card Preview

Static preview assets for the built-in share-card layout:

<p align="center">
  <img src="main/assets/readme-bilibili-card.svg" alt="Bilibili share card preview" width="48%">
  <img src="main/assets/readme-douyin-card.svg" alt="Douyin share card preview" width="48%">
</p>

Actual share-card endpoints:

```text
/api/v1/bilibili/share-card?url=https://www.bilibili.com/video/BV15kVJzYE5N/
/api/v1/douyin/share-card?url=https://www.iesdouyin.com/share/video/7634486870264597775/
```

## Response Examples

<details>
<summary>Bilibili response JSON</summary>

```json
{
  "product": "Cortex",
  "platform": "bilibili",
  "input_url": "https://www.bilibili.com/video/BV15kVJzYE5N/",
  "canonical_url": "https://www.bilibili.com/video/BV15kVJzYE5N",
  "video_id": "BV15kVJzYE5N",
  "title": "Bilibili Sample",
  "description": "Public video metadata extracted from Bilibili.",
  "duration_seconds": 291.0,
  "published_at": "2026-06-05T10:05:28Z",
  "metrics": {
    "play_count": 5030049,
    "danmaku_count": 6964,
    "comment_count": 23141,
    "like_count": 213529,
    "share_count": 17775,
    "favorite_count": 25971,
    "coin_count": 17036
  },
  "video_source": {
    "url": "https://example.com/bilibili-video.mp4",
    "request_headers": {
      "User-Agent": "Mozilla/5.0"
    },
    "source_mode": "single_file",
    "format_id": "html5-durl-64",
    "quality": "720P",
    "container": "mp4",
    "width": 1280,
    "height": 720
  },
  "cover_source": {
    "url": "https://example.com/bilibili-cover.jpg",
    "request_headers": {
      "User-Agent": "Mozilla/5.0"
    }
  }
}
```

</details>

<details>
<summary>Douyin response JSON</summary>

```json
{
  "product": "Cortex",
  "platform": "douyin",
  "input_url": "https://www.iesdouyin.com/share/video/7634486870264597775/",
  "canonical_url": "https://www.douyin.com/video/7634486870264597775",
  "video_id": "7634486870264597775",
  "title": "Douyin Sample",
  "description": "Public video metadata extracted from Douyin.",
  "duration_seconds": 17.267,
  "published_at": "2026-02-18T13:00:00Z",
  "author": {
    "name": "Douyin Creator",
    "unique_id": "1234567890",
    "sec_uid": "MS4wLjABAAAAexample-sec-uid",
    "profile_url": "https://www.douyin.com/user/MS4wLjABAAAAexample-sec-uid",
    "avatar_url": "https://example.com/avatar.jpeg",
    "signature": "Example creator signature",
    "follower_count": 1147000,
    "total_favorited": 83954608,
    "verification": {
      "is_verified": true,
      "theme": "red",
      "text": "Example official verification"
    }
  },
  "metrics": {
    "comment_count": 238,
    "like_count": 7171,
    "share_count": 159,
    "favorite_count": 255
  },
  "video_source": {
    "url": "https://example.com/douyin-video.mp4",
    "source_mode": "single_file",
    "format_id": "douyin-play",
    "quality": "720p",
    "container": "mp4",
    "width": 1080,
    "height": 1920
  },
  "cover_source": {
    "url": "https://example.com/douyin-cover.jpeg"
  }
}
```

</details>

## Project Structure

```text
.
|-- README.md
|-- README.en.md
|-- README.zh-CN.md
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

- `api/` contains FastAPI routes and example response payloads
- `core/` contains branding and runtime configuration helpers
- `services/` contains platform parsers, shared models, utilities, and share-card rendering
- `tests/` contains API and parser regression tests

## Notes

- Parsing quality depends on upstream public page structure
- Some Douyin metrics may be limited by upstream public responses

## License

Cortex is source-available under `PolyForm Noncommercial 1.0.0`.

- English license: [LICENSE](LICENSE)
- Chinese reference: [LICENSE.zh-CN.md](LICENSE.zh-CN.md)
- Commercial use is not allowed without separate permission
- Redistributing original or modified copies must keep attribution as `Cortex by Ransen1337-star`
- Required notices must be preserved from [NOTICE](NOTICE)
- The `Cortex` name and logo are not licensed as trademarks; see [TRADEMARKS.md](TRADEMARKS.md)

---

❤️‍🩹 Thank you for using Cortex, Built with ❤️ by Ransen1337-star
