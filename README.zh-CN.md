<div align="center">

<img src="main/assets/cortex-logo.svg" alt="Cortex 标志" width="420">

# Cortex

**Cortex，面向 Bilibili 与抖音视频解析的轻量公开源码项目**

<p>
  <a href="README.md"><strong>概览</strong></a>
  &nbsp;|&nbsp;
  <a href="README.en.md"><strong>English</strong></a>
</p>

<p>
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063" alt="Pydantic">
  <img src="https://img.shields.io/badge/Mode-API--only-2563EB" alt="Mode">
</p>

</div>

## 简介

Cortex 用于公开源码方式提供视频解析能力，统一输出标题、描述、发布时间、互动指标、视频源、封面源，并支持生成 SVG 分享卡片。

项目根目录只保留 `start.py`，其余源码、资源、文档与依赖统一放在 `main/` 中，结构更清晰，也更方便维护。

## 文档

- 概览：[README.md](README.md)
- English：[README.en.md](README.en.md)

> #### <img src="main/assets/callout-important.svg" alt="" width="18" align="absmiddle"> 重要说明
>
> - 本项目仅面向公开链接解析，不处理私有内容或登录态内容
> - 使用者必须合规使用接口与抓取结果
> - 抖音公开分享页当前可能无法稳定返回真实播放量
> - 面向公众提供服务时，建议补充风控、缓存、日志与来源限制

> #### <img src="main/assets/callout-warning.svg" alt="" width="18" align="absmiddle"> 警告
>
> - 公开平台页面结构会变化，解析逻辑不能保证永久稳定
> - 如果上游接口限流、签名变更或资源失效，部分字段可能短时异常

> #### <img src="main/assets/callout-tip.svg" alt="" width="18" align="absmiddle"> 提示
>
> - 推荐优先使用完整公开链接
> - 启动后可直接访问 `/docs` 调试接口
> - 若面向生产环境，建议补缓存与请求频控

## 功能

- 解析 Bilibili 与抖音公开视频链接
- 自动过滤并识别输入中的有效链接
- 返回统一字段结构，便于前端或脚本接入
- 提供 Bilibili / Douyin 分享卡片 SVG 接口
- 内置 Swagger 文档，启动后可直接访问 `/docs`
- 保留项目署名 `Cortex by Ransen1337-star`

## 支持的链接

- Bilibili 解析示例只使用 `https://www.bilibili.com/video/BV15kVJzYE5N/`
- 抖音解析示例只使用 `https://www.iesdouyin.com/share/video/7634486870264597775/`
- 建议传入完整公开链接，服务会先做基础过滤，再进入对应平台解析流程

## 快速开始

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r main/requirements.txt
python start.py
```

默认地址：

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## 接口示例

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

解析 Bilibili：

```bash
curl "http://127.0.0.1:8000/api/v1/bilibili/video-analysis?url=https%3A%2F%2Fwww.bilibili.com%2Fvideo%2FBV15kVJzYE5N%2F"
```

解析抖音：

```bash
curl "http://127.0.0.1:8000/api/v1/douyin/video-analysis?url=https%3A%2F%2Fwww.iesdouyin.com%2Fshare%2Fvideo%2F7634486870264597775%2F"
```

生成分享卡片：

```bash
curl "http://127.0.0.1:8000/api/v1/bilibili/share-card?url=https%3A%2F%2Fwww.bilibili.com%2Fvideo%2FBV15kVJzYE5N%2F" -o share-card.svg
```

## Card 预览

下面这两张是仓库内置的分享卡片静态预览图：

<p align="center">
  <img src="main/assets/readme-bilibili-card.svg" alt="Bilibili 分享卡片预览" width="48%">
  <img src="main/assets/readme-douyin-card.svg" alt="Douyin 分享卡片预览" width="48%">
</p>

实际卡片接口：

```text
/api/v1/bilibili/share-card?url=https://www.bilibili.com/video/BV15kVJzYE5N/
/api/v1/douyin/share-card?url=https://www.iesdouyin.com/share/video/7634486870264597775/
```

## 返回数据示例

<details>
<summary>Bilibili 返回 JSON</summary>

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
<summary>抖音返回 JSON</summary>

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

## 目录结构

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

- `api/` 放 FastAPI 路由与示例返回
- `core/` 放品牌信息与运行时配置辅助代码
- `services/` 放平台解析器、共享模型、工具函数与分享卡片渲染
- `tests/` 放 API 与解析器回归测试

## 说明

- 平台页面结构变动时，解析逻辑可能需要同步调整
- 抖音部分公开页面字段存在限制，个别指标可能受上游返回影响

## 协议

Cortex 采用 `PolyForm Noncommercial 1.0.0` 源码可见许可。

- 英文原文：[LICENSE](LICENSE)
- 中文参考：[LICENSE.zh-CN.md](LICENSE.zh-CN.md)
- 未经单独授权，不允许商用
- 转载原版或修改版时，必须保留 `Cortex by Ransen1337-star` 署名
- 必须一并保留仓库根目录中的 [NOTICE](NOTICE) 要求通知
- `Cortex` 名称与 logo 不随软件许可一起授权，详见 [TRADEMARKS.md](TRADEMARKS.md)

---

❤️‍🩹 感谢您使用 Cortex，Built with ❤️ by Ransen1337-star
