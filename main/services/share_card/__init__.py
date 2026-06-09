import base64
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from html import escape
from typing import Literal
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field
from main.services.utils import build_remote_asset_request_headers
from main.services.utils import create_http_client
from main.services.utils import normalize_remote_asset_url


DEFAULT_CARD_FONT_STACK = "Noto Sans SC, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
CARD_FONT_STACK = DEFAULT_CARD_FONT_STACK


HTTP_CLIENT = create_http_client(20)
AVATAR_BLOCK_OFFSET_Y = -12
CONTENT_BLOCK_OFFSET_Y = -12
AUTHOR_NAME_BASELINE_Y = 118
AUTHOR_BADGE_BASELINE_Y = 118
AUTHOR_CERTIFICATION_TEXT_Y = 128
AUTHOR_NAME_BASELINE_Y_WITH_CERT = 104
AUTHOR_BADGE_BASELINE_Y_WITH_CERT = 104
SECONDARY_LABEL_FILL = "#475569"
SECONDARY_VALUE_FILL = "#111827"


class ShareCardAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    avatar_url: str | None = None
    badge_text: str | None = None
    badge_icon_url: str | None = None
    badge_markup: str | None = None
    certification_icon_markup: str | None = None
    certification_text: str | None = None


class ShareCardMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    label: str | None = None
    icon_svg: str | None = None


class ShareCardBranding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logo_svg: str | None = None
    logo_url: str | None = None
    logo_fill: str = "#00A1D6"
    logo_x: int = 1080
    logo_y: int = 548
    logo_width: int = 56
    logo_height: int = 56
    logo_view_box: str = "0 0 2338 1000"


class ShareCardData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    canonical_url: str
    cover_url: str | None = None
    cover_layout: Literal["landscape", "portrait"] = "landscape"
    author: ShareCardAuthor
    tags: list[str] = Field(default_factory=list)
    primary_metrics: list[ShareCardMetric] = Field(default_factory=list)
    secondary_metrics: list[ShareCardMetric] = Field(default_factory=list)
    branding: ShareCardBranding | None = None


def set_share_card_font_stack(font_stack: str | None) -> None:
    global CARD_FONT_STACK
    normalized_font_stack = (font_stack or "").strip()
    CARD_FONT_STACK = normalized_font_stack or DEFAULT_CARD_FONT_STACK


def render_share_card_svg(card_data: ShareCardData, asset_proxy_path: str | None = None) -> str:
    cover_layout = resolve_cover_layout(card_data.cover_layout)
    avatar_x = 54
    avatar_y = 56 + AVATAR_BLOCK_OFFSET_Y
    avatar_size = 88
    avatar_radius = 44
    avatar_center_x = avatar_x + avatar_radius
    avatar_center_y = avatar_y + avatar_radius
    divider_y = 170 + CONTENT_BLOCK_OFFSET_Y
    title_start_y = 214 + CONTENT_BLOCK_OFFSET_Y
    title_lines = split_title_lines(card_data.title, max_units=22, max_lines=2)
    title_bottom_y = title_start_y + (len(title_lines) - 1) * 60
    tag_y = title_bottom_y + 44
    logo_url = card_data.branding.logo_url if card_data.branding is not None else None
    asset_uris = fetch_remote_image_data_uris(
        [
            card_data.author.avatar_url,
            card_data.author.badge_icon_url,
            card_data.cover_url,
            logo_url,
        ],
        asset_proxy_path=asset_proxy_path,
    )
    avatar_data_uri = asset_uris.get(card_data.author.avatar_url)
    badge_icon_data_uri = asset_uris.get(card_data.author.badge_icon_url)
    cover_data_uri = asset_uris.get(card_data.cover_url)
    brand_logo_data_uri = asset_uris.get(logo_url)
    primary_metric_nodes = "".join(
        build_primary_metric(54 + index * 178, 506 + CONTENT_BLOCK_OFFSET_Y, metric)
        for index, metric in enumerate(card_data.primary_metrics[:4])
    )
    secondary_metric_nodes = "".join(
        build_secondary_metric(968, 250 + index * 82, metric, SECONDARY_LABEL_FILL, SECONDARY_VALUE_FILL)
        for index, metric in enumerate(card_data.secondary_metrics[:3])
    )
    tag_nodes = build_tag_flow(card_data.tags[:4], 54, tag_y, 18, cover_layout["tag_max_x"])
    avatar_image = ""
    if avatar_data_uri:
        avatar_image = build_image_node(
            avatar_data_uri,
            x=avatar_x,
            y=avatar_y,
            width=avatar_size,
            height=avatar_size,
            preserve_aspect_ratio="xMidYMid slice",
            extra_attributes='clip-path="url(#avatarClip)"',
        )
    has_certification = bool(card_data.author.certification_icon_markup)
    author_name_baseline_y = AUTHOR_NAME_BASELINE_Y_WITH_CERT if has_certification else AUTHOR_NAME_BASELINE_Y
    author_badge_baseline_y = AUTHOR_BADGE_BASELINE_Y_WITH_CERT if has_certification else AUTHOR_BADGE_BASELINE_Y
    badge_x = min(168 + int(estimate_text_width_px(card_data.author.name, 34)) + 16, 690)
    badge_markup = card_data.author.badge_markup or ""
    badge_markup = badge_markup.replace("__BADGE_X__", str(badge_x)).replace("__BADGE_Y__", str(author_badge_baseline_y))
    certification_icon_markup = card_data.author.certification_icon_markup or ""
    certification_icon_markup = certification_icon_markup.replace("__CERT_ICON_X__", str(avatar_x + avatar_size - 26)).replace(
        "__CERT_ICON_Y__",
        str(avatar_y + avatar_size - 26),
    )
    certification_text = ""
    if card_data.author.certification_text:
        certification_text = (
            f'<text x="168" y="{AUTHOR_CERTIFICATION_TEXT_Y}" fill="#61666D" font-size="18" font-weight="600" '
            f'font-family="{CARD_FONT_STACK}">{escape(card_data.author.certification_text)}</text>'
        )
    if not badge_markup:
        if badge_icon_data_uri:
            badge_markup = build_image_node(
                badge_icon_data_uri,
                x=badge_x,
                y=author_badge_baseline_y - 30,
                width=36,
                height=36,
                preserve_aspect_ratio="xMidYMid meet",
            )
        else:
            badge_markup = build_author_badge(escape(card_data.author.badge_text or ""))
    title_text = "".join(
        f'<text x="54" y="{title_start_y + index * 60}" fill="#111827" font-size="40" font-weight="800" '
        f'font-family="{CARD_FONT_STACK}">{escape(line)}</text>'
        for index, line in enumerate(title_lines)
    )
    return f"""<svg width="1200" height="630" viewBox="0 0 1200 630" fill="none" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<defs>
  <clipPath id="avatarClip">
    <circle cx="{avatar_center_x}" cy="{avatar_center_y}" r="{avatar_radius}" />
  </clipPath>
  <clipPath id="coverClip">
    <rect x="{cover_layout["x"]}" y="{cover_layout["y"]}" width="{cover_layout["width"]}" height="{cover_layout["height"]}" rx="{cover_layout["radius"]}" />
  </clipPath>
  {build_cover_mask_gradient(cover_layout)}
  <linearGradient id="coverSheen" x1="{cover_layout["x"]}" y1="{cover_layout["y"]}" x2="{cover_layout["x"] + cover_layout["width"]}" y2="{cover_layout["y"] + cover_layout["height"]}" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#FFFFFF" />
    <stop offset="1" stop-color="#FFFFFF" stop-opacity="0" />
  </linearGradient>
  <mask id="coverFadeMask" maskUnits="userSpaceOnUse" x="{cover_layout["x"]}" y="{cover_layout["y"]}" width="{cover_layout["width"]}" height="{cover_layout["height"]}">
    <rect x="{cover_layout["x"]}" y="{cover_layout["y"]}" width="{cover_layout["width"]}" height="{cover_layout["height"]}" fill="url(#coverFadeMaskGradient)" />
  </mask>
</defs>
<rect width="1200" height="630" rx="32" fill="#FFFFFF" />
<rect x="1" y="1" width="1198" height="628" rx="31" stroke="#E5E7EB" stroke-width="2" />
{build_cover_backdrop(cover_data_uri, cover_layout)}
<rect x="{avatar_x}" y="{avatar_y}" width="{avatar_size}" height="{avatar_size}" rx="{avatar_radius}" fill="#EAF5FE" />
{avatar_image}
<text x="168" y="{author_name_baseline_y}" fill="#0F172A" font-size="34" font-weight="800" font-family="{CARD_FONT_STACK}">{escape(card_data.author.name)}</text>
{badge_markup}
{certification_icon_markup}
{certification_text}
<line x1="54" y1="{divider_y}" x2="1146" y2="{divider_y}" stroke="#F1F5F9" stroke-width="2" />
{title_text}
{tag_nodes}
<text x="54" y="{602 + CONTENT_BLOCK_OFFSET_Y}" fill="#94A3B8" font-size="16" font-weight="600" font-family="{CARD_FONT_STACK}">{escape(card_data.canonical_url)}</text>
{primary_metric_nodes}
{secondary_metric_nodes}
{build_brand_logo(card_data.branding, brand_logo_data_uri)}
</svg>"""


def build_cover_backdrop(cover_data_uri: str | None, cover_layout: dict[str, int | str]) -> str:
    if not cover_data_uri:
        return ""
    cover_image = build_image_node(
        cover_data_uri,
        x=int(cover_layout["x"]),
        y=int(cover_layout["y"]),
        width=int(cover_layout["width"]),
        height=int(cover_layout["height"]),
        preserve_aspect_ratio=str(cover_layout["preserve_aspect_ratio"]),
    )
    return f"""<g clip-path="url(#coverClip)" mask="url(#coverFadeMask)">
{cover_image}
</g>
<rect x="{cover_layout["x"]}" y="{cover_layout["y"]}" width="{cover_layout["width"]}" height="{cover_layout["height"]}" rx="{cover_layout["radius"]}" fill="url(#coverSheen)" fill-opacity="0.12" />
<g clip-path="url(#coverClip)" mask="url(#coverFadeMask)">
<rect x="{cover_layout["x"]}" y="{cover_layout["y"]}" width="{cover_layout["width"]}" height="{cover_layout["height"]}" rx="{cover_layout["radius"]}" fill="none" stroke="#6B7280" stroke-opacity="0.10" stroke-width="4" />
<rect x="{cover_layout["x"]}" y="{cover_layout["y"]}" width="{cover_layout["width"]}" height="{cover_layout["height"]}" rx="{cover_layout["radius"]}" fill="none" stroke="#6B7280" stroke-opacity="0.18" stroke-width="1.5" />
</g>"""


def resolve_cover_layout(layout: Literal["landscape", "portrait"]) -> dict[str, int | str]:
    if layout == "portrait":
        return {
            "x": 786,
            "y": 218,
            "width": 214,
            "height": 268,
            "radius": 28,
            "preserve_aspect_ratio": "xMidYMin slice",
            "tag_max_x": 860,
        }
    return {
        "x": 620,
        "y": 194,
        "width": 418,
        "height": 286,
        "radius": 28,
        "preserve_aspect_ratio": "xMinYMid slice",
        "tag_max_x": 700,
    }


def build_cover_mask_gradient(cover_layout: dict[str, int | str]) -> str:
    return (
        f'<linearGradient id="coverFadeMaskGradient" x1="{cover_layout["x"]}" y1="0" '
        f'x2="{int(cover_layout["x"]) + int(cover_layout["width"])}" y2="0" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" stop-color="white" />'
        '<stop offset="0.42" stop-color="white" />'
        '<stop offset="0.68" stop-color="white" stop-opacity="0.58" />'
        '<stop offset="1" stop-color="white" stop-opacity="0" />'
        "</linearGradient>"
    )


def build_author_badge(badge_text: str) -> str:
    if not badge_text:
        return ""
    return f"""<rect x="214" y="112" width="76" height="34" rx="17" fill="#F3F4F6" />
<text x="234" y="135" fill="#61666D" font-size="19" font-weight="700" font-family="{CARD_FONT_STACK}">{badge_text}</text>"""


def build_primary_metric(x: int, y: int, metric: ShareCardMetric) -> str:
    icon_node = ""
    if metric.icon_svg:
        icon_node = f'<g transform="translate({x} {y})">{metric.icon_svg}</g>'
    return f"""<g>
{icon_node}
<text x="{x + 42}" y="{y + 24}" fill="#0F172A" font-size="22" font-weight="800" font-family="{CARD_FONT_STACK}">{escape(metric.value)}</text>
</g>"""


def build_secondary_metric(x: int, y: int, metric: ShareCardMetric, label_fill: str, value_fill: str) -> str:
    label_node = ""
    if metric.label:
        label_node = f'<text x="{x}" y="{y}" fill="{label_fill}" font-size="18" font-weight="700" font-family="{CARD_FONT_STACK}">{escape(metric.label)}</text>'
    return f"""<g>
{label_node}
<text x="{x}" y="{y + 38}" fill="{value_fill}" font-size="38" font-weight="800" font-family="{CARD_FONT_STACK}">{escape(metric.value)}</text>
</g>"""


def build_brand_logo(branding: ShareCardBranding | None, logo_data_uri: str | None = None) -> str:
    if branding is None:
        return ""
    if branding.logo_url is not None:
        if logo_data_uri is None:
            return ""
        return build_image_node(
            logo_data_uri,
            x=branding.logo_x,
            y=branding.logo_y,
            width=branding.logo_width,
            height=branding.logo_height,
            preserve_aspect_ratio="xMidYMid meet",
        )
    if branding.logo_svg is None:
        return ""
    return (
        f'<svg x="{branding.logo_x}" y="{branding.logo_y}" width="{branding.logo_width}" '
        f'height="{branding.logo_height}" viewBox="{branding.logo_view_box}" fill="{branding.logo_fill}" '
        f'xmlns="http://www.w3.org/2000/svg">{branding.logo_svg}</svg>'
    )


def build_tag_chip(x: int, y: int, tag: str) -> str:
    safe_tag = truncate_text_units(tag, 18)
    width = estimate_tag_chip_width(safe_tag)
    return f"""<g>
<rect x="{x}" y="{y}" width="{width}" height="34" rx="17" fill="#F8FAFC" stroke="#E5E7EB" />
<text x="{x + 16}" y="{y + 23}" fill="#61666D" font-size="16" font-weight="700" font-family="{CARD_FONT_STACK}">#{escape(safe_tag)}</text>
</g>"""


def build_tag_flow(tags: list[str], start_x: int, y: int, gap: int, max_x: int) -> str:
    nodes: list[str] = []
    current_x = start_x
    for tag in tags:
        safe_tag = truncate_text_units(tag, 18)
        width = estimate_tag_chip_width(safe_tag)
        if current_x + width > max_x:
            break
        nodes.append(build_tag_chip(current_x, y, tag))
        current_x += width + gap
    return "".join(nodes)


def split_title_lines(title: str, max_units: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    units = 0
    for char in title:
        char_units = 2 if ord(char) > 127 else 1
        if units + char_units > max_units:
            lines.append(current)
            current = char
            units = char_units
            if len(lines) == max_lines - 1:
                break
            continue
        current += char
        units += char_units
    remaining = title[len("".join(lines) + current):]
    if current:
        if len(lines) == max_lines - 1 and remaining:
            current = truncate_text_units(current + remaining, max_units)
        lines.append(current)
    return lines[:max_lines] or [title]


def estimate_text_units(text: str) -> int:
    return sum(2 if ord(char) > 127 else 1 for char in text)


def estimate_text_width_px(text: str, font_size: int) -> float:
    width = 0.0
    for char in text:
        width += font_size if ord(char) > 127 else font_size * 0.56
    return width


def estimate_tag_chip_width(text: str) -> int:
    return int(34 + estimate_text_width_px(f"#{text}", 16) + 10)


def truncate_text_units(text: str, max_units: int) -> str:
    result = ""
    units = 0
    for char in text:
        char_units = 2 if ord(char) > 127 else 1
        if units + char_units > max_units - 2:
            return result + "..."
        result += char
        units += char_units
    return result


@lru_cache(maxsize=256)
def fetch_remote_image_data_uri(url: str | None, asset_proxy_path: str | None = None) -> str | None:
    normalized_url = normalize_remote_asset_url(url)
    if normalized_url is None:
        return None
    try:
        response = HTTP_CLIENT.get(
            normalized_url,
            headers=build_remote_asset_request_headers(normalized_url),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        if asset_proxy_path:
            return build_share_card_asset_proxy_url(asset_proxy_path, normalized_url)
        return normalized_url
    media_type = response.headers.get("content-type") or "application/octet-stream"
    encoded_content = base64.b64encode(response.content).decode("ascii")
    return f"data:{media_type};base64,{encoded_content}"


def fetch_remote_image_data_uris(urls: list[str | None], asset_proxy_path: str | None = None) -> dict[str | None, str | None]:
    unique_urls: list[str | None] = []
    for url in urls:
        if url not in unique_urls:
            unique_urls.append(url)
    results: dict[str | None, str | None] = {}
    target_urls = [url for url in unique_urls if url]
    if target_urls:
        with ThreadPoolExecutor(max_workers=min(4, len(target_urls))) as executor:
            future_map = {
                executor.submit(fetch_remote_image_data_uri, url, asset_proxy_path): url
                for url in target_urls
            }
            for future, url in future_map.items():
                results[url] = future.result()
    for url in unique_urls:
        results.setdefault(url, None)
    return results


def build_share_card_asset_proxy_url(asset_proxy_path: str, remote_url: str) -> str:
    normalized_path = asset_proxy_path.strip() or "/api/v1/share-card/assets"
    encoded_remote_url = quote(remote_url, safe="")
    return f"{normalized_path}?url={encoded_remote_url}"


def build_image_node(
    href: str,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    preserve_aspect_ratio: str,
    extra_attributes: str = "",
) -> str:
    suffix = f" {extra_attributes}" if extra_attributes else ""
    safe_href = escape(href, quote=True)
    return (
        f'<image href="{safe_href}" xlink:href="{safe_href}" x="{x}" y="{y}" width="{width}" '
        f'height="{height}" preserveAspectRatio="{preserve_aspect_ratio}"{suffix} />'
    )
