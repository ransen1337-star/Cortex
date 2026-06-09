<div align="center">

<img src="main/assets/cortex-logo.svg" alt="Cortex logo" width="420">

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

## Card Preview

Static preview assets for the built-in share-card layout:

<p align="center">
  <img src="main/assets/readme-bilibili-card.svg" alt="Bilibili share card preview" width="48%">
  <img src="main/assets/readme-douyin-card.svg" alt="Douyin share card preview" width="48%">
</p>

Actual card endpoints:

```text
/api/v1/bilibili/share-card?url=https://www.bilibili.com/video/BV15kVJzYE5N/
/api/v1/douyin/share-card?url=https://www.iesdouyin.com/share/video/7634486870264597775/
```

## Response Preview

<details>
<summary>Bilibili JSON response</summary>

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
<summary>Douyin JSON response</summary>

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
