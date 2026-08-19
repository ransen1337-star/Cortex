<div align="center">

<img src="main/assets/branding/cortex-logo.svg" alt="Cortex logo" width="420">

# Cortex

**API-only source code project for public Bilibili, Douyin, and GitHub link analysis**

<p>
  <a href="README.md"><strong>Overview</strong></a>
  &nbsp;|&nbsp;
  <a href="README.zh-CN.md"><strong>简体中文</strong></a>
</p>

**Keywords:** `bilibili api` · `douyin api` · `video analysis api` · `video parser` · `fastapi` · `share card generator`

**Version:** `1.1.0`

</div>

## Overview

Cortex is a compact FastAPI codebase for public Bilibili and Douyin video analysis, GitHub repository metadata extraction, and share-card rendering.

It provides:

- one unified response schema for both platforms
- URL filtering, normalization, and fixed example-link validation
- direct author, video, and cover metadata extraction
- share cards in `svg` or `png`, with `performance`, `balanced`, and `quality` PNG presets
- GitHub repository parsing with language, contributor, license, and repository metrics
- GitHub cards in transparent `cortex` style or GitHub's official OpenGraph preview image
- a non-blocking startup check comparing the local version with the remote `PROJECT_VERSION`
- a clean `main/` application layout with `start.py` as the only root entry

## Shared Response Schema

```json
{
  "product": "Cortex",
  "platform": "bilibili | douyin",
  "input_url": "string",
  "canonical_url": "string",
  "video_id": "string",
  "title": "string",
  "description": "string | null",
  "declaration": "string | null",
  "duration_seconds": 0.0,
  "published_at": "ISO-8601 | null",
  "author": {},
  "metrics": {},
  "video_source": {},
  "cover_source": {}
}
```

## GitHub Endpoints

```text
/api/v1/github/repository?url=https://github.com/ransen1337-star/Cortex
/api/v1/github/share-card?url=https://github.com/ransen1337-star/Cortex&style=cortex&mode=png
/api/v1/github/share-card?url=https://github.com/ransen1337-star/Cortex&style=official&mode=png
/api/v1/github/rate-limit
```

`style=cortex` uses the same transparent renderer as Bilibili and Douyin. `style=official` proxies GitHub's official OpenGraph preview image.

## GitHub API Budget

The Cortex card style calls the GitHub REST API for repository metadata. GitHub typically allows 60 unauthenticated REST requests per hour per IP address and 5,000 authenticated requests per hour. Configure a fine-grained token with read-only public repository access through `GITHUB_TOKEN` when rendering cards regularly:

```bash
export GITHUB_TOKEN=github_pat_your_token
```

`/api/v1/github/rate-limit` reports the effective limit, remaining requests, and reset time without exposing the token. The official card style proxies GitHub's OpenGraph image and does not use this REST budget.

## PNG Rendering

PNG cards use CairoSVG by default and require the system Cairo library. On macOS, install it with `brew install cairo`. Set `CORTEX_SHARE_CARD_RENDERER=chromium` to use Chrome/Chromium instead; set `CORTEX_SHARE_CARD_GPU=1` to request Chromium GPU rasterization. `CORTEX_SHARE_CARD_MAX_CONCURRENCY` controls concurrent PNG renders.

## Preview

<table>
  <tr>
    <td width="50%" align="center" valign="top">
      <img src="main/assets/docs/readme-bilibili-card.png" alt="Bilibili share card preview" width="96%">
      <br>
      <strong>Bilibili Share Card</strong>
    </td>
    <td width="50%" align="center" valign="top">
      <img src="main/assets/docs/readme-douyin-card.png" alt="Douyin share card preview" width="96%">
      <br>
      <strong>Douyin Share Card</strong>
    </td>
  </tr>
</table>

<details>
  <summary><strong>Bilibili full JSON example</strong></summary>

```json
{
  "product": "Cortex",
  "platform": "bilibili",
  "input_url": "https://www.bilibili.com/video/BV15kVJzYE5N",
  "canonical_url": "https://www.bilibili.com/video/BV15kVJzYE5N",
  "video_id": "BV15kVJzYE5N",
  "title": "《消失的青年》：面对焦虑，我们依然还有选择",
  "description": "在社交媒体上，别人的生活永远精彩，自己的生活却布满雷区。从育儿、到读书、到求职，从年龄到外貌，青年们的人生似乎正在被焦虑消除。\n \n2025年五四青年节到来之际，B站发布了短片《消失的青年》，希望大家在面对焦虑时，依然还有选择。",
  "declaration": null,
  "duration_seconds": 246.0,
  "published_at": "2025-05-04T02:00:00Z",
  "author": {
    "name": "哔哩哔哩弹幕网",
    "unique_id": "8047632",
    "sec_uid": null,
    "profile_url": "https://space.bilibili.com/8047632",
    "avatar_url": "https://i0.hdslb.com/bfs/face/0c84b9f4ad546d3f20324809d45fc439a2a8ddab.jpg",
    "signature": "哔哩哔哩 干杯  ( ゜- ゜)つロ",
    "follower_count": 4027756,
    "total_favorited": null,
    "verification": {
      "is_verified": true,
      "theme": "blue",
      "text": "bilibili机构认证 哔哩哔哩弹幕网官方账号"
    }
  },
  "metrics": {
    "play_count": 6414979,
    "danmaku_count": 321,
    "comment_count": 1412,
    "like_count": 56590,
    "share_count": 13266,
    "favorite_count": 39374,
    "coin_count": 24380
  },
  "video_source": {
    "url": "https://upos-sz-estgcos.bilivideo.com/upgcxcode/17/80/29778248017/29778248017-1-192.mp4?e=ig8euxZM2rNcNbR17zdVhwdlhWRahwdVhoNvNC8BqJIzNbfq9rVEuxTEnE8L5F6VnEsSTx0vkX8fqJeYTj_lta53NCM=&gen=playurlv3&os=estgcos&mid=0&uipk=5&trid=c79f4a3276484807b8078bb934b681dh&nbs=1&og=cos&oi=665489043&platform=html5&deadline=1781025430&upsig=543e05de07ab56a9a49ea7f9ac68d2eb&uparams=e,gen,os,mid,uipk,trid,nbs,og,oi,platform,deadline&bvc=vod&nettype=0&bw=941907&lrs=-1&buvid=&build=0&dl=0&f=h_0_0&agrr=0&orderid=0,1",
    "request_headers": {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    },
    "source_mode": "single_file",
    "audio_url": null,
    "format_id": "html5-durl-64",
    "quality": "720P 高清",
    "container": "mp4",
    "width": 1280,
    "height": 720,
    "fps": null
  },
  "cover_source": {
    "url": "https://i1.hdslb.com/bfs/archive/d6f84751ef91dacee0aacc64e7d6f0bd35ae1b8f.jpg",
    "request_headers": {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    }
  }
}
```
</details>

<details>
  <summary><strong>Douyin full JSON example</strong></summary>

```json
{
  "product": "Cortex",
  "platform": "douyin",
  "input_url": "https://www.iesdouyin.com/share/video/7634486870264597775/",
  "canonical_url": "https://www.douyin.com/video/7634486870264597775",
  "video_id": "7634486870264597775",
  "title": "抖音首发 | Google Cloud Next 26 开幕主题演讲：智能体云 The Agentic Cloud （视频由Google Cloud授权发布）",
  "description": "抖音首发 | Google Cloud Next 26 开幕主题演讲：智能体云 The Agentic Cloud （视频由Google Cloud授权发布）\n #抖音前沿科技首发计划#Google#GoogleCloudNext#AI新星计划#前沿科技趋势发布月",
  "declaration": null,
  "duration_seconds": 5941.611,
  "published_at": "2026-04-30T09:48:24Z",
  "author": {
    "name": "抖音精选官方账号",
    "unique_id": "48751955702",
    "sec_uid": "MS4wLjABAAAApksOkI0F7EMtId8CEunyMrlPTWGpOTDuqdlZ8VmCqcQXq7p_tDdUtFB_rLV-rqez",
    "profile_url": "https://www.douyin.com/user/MS4wLjABAAAApksOkI0F7EMtId8CEunyMrlPTWGpOTDuqdlZ8VmCqcQXq7p_tDdUtFB_rLV-rqez",
    "avatar_url": "https://p11.douyinpic.com/aweme/100x100/aweme-avatar/tos-cn-avt-0015_c0e5aad3548629d5e69f3104afa86d12.jpeg?from=327834062",
    "signature": "官方邮箱：douyinjingxuan@bytedance.com\n直播回放：均在主页【节目】板块哦",
    "follower_count": 1148000,
    "total_favorited": 84058107,
    "verification": {
      "is_verified": true,
      "theme": "red",
      "text": "抖音精选官方账号"
    }
  },
  "metrics": {
    "play_count": null,
    "danmaku_count": null,
    "comment_count": 649,
    "like_count": 12000,
    "share_count": 499,
    "favorite_count": 1399,
    "coin_count": null
  },
  "video_source": {
    "url": "https://v99-coldx.douyinvod.com/9112143df5533d34c56571e294724daf/6a2853bc/video/tos/cn/tos-cn-ve-15/owhTIabfRGAcKSXiXkLfB7TXDBZAWCI5EJeCzI/?a=1128&ch=0&cr=0&dr=0&cd=0%7C0%7C0%7C0&cv=1&br=649&bt=649&cs=0&ds=3&ft=KGkhUyqfRR0syrC3-Dy2Nc0iPMgzbL8EKWRU_49fS~wSNv7TGW&mime_type=video_mp4&qs=0&rc=NzVlODw7PDtoOzVlZmlnN0BpanA4bnk5cnRsOjMzNGkzM0AwLmAyMi5hXzIxMDIuLTVhYSNhZmVzMmQ0MW1hLS1kLWFzcw%3D%3D&btag=80010e000b8001&cquery=100y&dy_q=1781018231&feature_id=f5241e7604dff1d9d6c943fd20bd51a2&l=20260609231711E0D17627A5D04E6AFB66",
    "request_headers": null,
    "source_mode": "single_file",
    "audio_url": null,
    "format_id": "douyin-play",
    "quality": "720p",
    "container": "mp4",
    "width": 1920,
    "height": 1080,
    "fps": null
  },
  "cover_source": {
    "url": "https://p11-sign.douyinpic.com/tos-cn-i-dy/ba28e7f300e0425386c18de416fd2484~tplv-dy-resize-walign-adapt-aq:540:q75.jpeg?lk3s=138a59ce&x-expires=1782226800&x-signature=vGXcIpLffj1kiXRq3jssYGQL6Uo%3D&from=327834062&s=PackSourceEnum_DOUYIN_REFLOW&se=false&sc=cover&biz_tag=aweme_video&l=2026060923171006F4A6782875E3D29F5D",
    "request_headers": null
  }
}
```
</details>

Snapshot files:

- [main/assets/docs/readme-bilibili-response.json](main/assets/docs/readme-bilibili-response.json)
- [main/assets/docs/readme-douyin-response.json](main/assets/docs/readme-douyin-response.json)

## Quick Start

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r main/requirements.txt
python start.py
```

Default local URLs:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## Example Endpoints

```text
/api/v1/bilibili/video-analysis?url=https://www.bilibili.com/video/BV15kVJzYE5N/
/api/v1/douyin/video-analysis?url=https://www.iesdouyin.com/share/video/7634486870264597775/
/api/v1/bilibili/share-card?url=https://www.bilibili.com/video/BV15kVJzYE5N/
/api/v1/bilibili/share-card?url=https://www.bilibili.com/video/BV15kVJzYE5N/&mode=svg
/api/v1/douyin/share-card?url=https://www.iesdouyin.com/share/video/7634486870264597775/&mode=png&preset=performance
/api/v1/douyin/share-card?url=https://www.iesdouyin.com/share/video/7634486870264597775/&mode=png&preset=quality
```

## Project Structure

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
|   |   |-- badges/
|   |   |-- branding/
|   |   `-- docs/
|   |-- core/
|   |   |-- branding.py
|   |   |-- runtime.py
|   |   `-- version.py
|   |-- services/
|   |   |-- bilibili/
|   |   |-- douyin/
|   |   |-- github/
|   |   `-- share_card/
|   |-- requirements.txt
|   `-- __init__.py
`-- start.py
```

The startup version check reads the remote source configured by `CORTEX_VERSION_SOURCE_URL`; by default it checks `main/core/branding.py` on the repository's `main` branch.

## Notes

> #### <img src="main/assets/branding/callout-important.svg" alt="" width="18" align="absmiddle"> IMPORTANT
>
> - Repository examples are fixed to `https://www.bilibili.com/video/BV15kVJzYE5N/`
> - Repository examples are fixed to `https://www.iesdouyin.com/share/video/7634486870264597775/`
> - Share-card endpoints support both raw `svg` and rendered `png`
> - PNG presets are `performance`, `balanced`, and `quality`
> - Douyin public share pages may not expose a reliable real play count

## Other Docs

- Overview: [README.md](README.md)
- 简体中文: [README.zh-CN.md](README.zh-CN.md)

## License

Cortex is source-available under `PolyForm Noncommercial 1.0.0`.

- [LICENSE](LICENSE)
- [LICENSE.zh-CN.md](LICENSE.zh-CN.md)
- [NOTICE](NOTICE)
- [TRADEMARKS.md](TRADEMARKS.md)

---

❤️‍🩹感谢您使用 Cortex，Built with ❤️ by Ransen1337-star
