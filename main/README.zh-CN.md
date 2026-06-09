<div align="center">

<img src="assets/logo.svg" alt="Video Analysis API 标志" width="176">

# Video Analysis API

**面向 Bilibili 与抖音公开链接的轻量解析 API**

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

## 简介

Video Analysis API 用于解析公开视频链接，统一输出标题、描述、发布时间、互动指标、视频源、封面源，并支持生成 SVG 分享卡片。

项目根目录只保留 `start.py`，其余代码、资源、文档与依赖统一放在 `main/` 中，结构更清晰，也更方便维护。

> #### <img src="assets/callout-important.svg" alt="" width="18" align="absmiddle"> 重要说明
>
> - 本项目仅面向公开链接解析，不处理私有内容或登录态内容
> - 使用者必须合规使用接口与抓取结果
> - 抖音公开分享页当前可能无法稳定返回真实播放量
> - 面向公众提供服务时，建议补充风控、缓存、日志与来源限制

> #### <img src="assets/callout-warning.svg" alt="" width="18" align="absmiddle"> 警告
>
> - 公开平台页面结构会变化，解析逻辑不能保证永久稳定
> - 如果上游接口限流、签名变更或资源失效，部分字段可能短时异常

> #### <img src="assets/callout-tip.svg" alt="" width="18" align="absmiddle"> 提示
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

## 目录结构

```text
.
|-- main/
|   |-- assets/
|   |-- core/
|   |-- services/
|   |-- README.md
|   |-- README.en.md
|   |-- README.zh-CN.md
|   `-- requirements.txt
`-- start.py
```

## 说明

- 平台页面结构变动时，解析逻辑可能需要同步调整
- 抖音部分公开页面字段存在限制，个别指标可能受上游返回影响

---

❤️‍🩹 感谢您使用 Video Analysis API，Built with ❤️ by Ransen1337-star
