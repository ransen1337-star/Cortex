from dataclasses import dataclass
from html import escape
import json
import re
from typing import Any, Protocol
from urllib.parse import urlparse
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

import httpx
from main.services.models import SourceFile
from main.services.models import VideoAnalysisResponse
from main.services.models import VideoMetrics
from main.services.models import VideoSourceFile
from main.services.share_card import ShareCardAuthor
from main.services.share_card import ShareCardBranding
from main.services.share_card import ShareCardData
from main.services.share_card import ShareCardMetric
from main.services.share_card import render_share_card_svg
from main.services.utils import build_published_at
from main.services.utils import collect_platform_declaration_candidates
from main.services.utils import coerce_float
from main.services.utils import coerce_int
from main.services.utils import coerce_string
from main.services.utils import create_http_client
from main.services.utils import format_count_short
from main.services.utils import format_duration_clock
from main.services.utils import normalize_remote_asset_url
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

HTTP_CLIENT = create_http_client(30)
EXTRACT_URL_PATTERN = re.compile(r"https?://[^\s<>'\"）)】]+")
PAGE_STATE_PATTERN = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", re.S)
TRAILING_URL_PUNCTUATION = ".,;!?，。；！？、)]）】>"


@dataclass(frozen=True)
class OfficialVerifyBadge:
    type: int
    title: str | None = None
    desc: str | None = None


class VideoAnalysisError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidBilibiliUrlError(VideoAnalysisError):
    pass


class BilibiliExtractionError(VideoAnalysisError):
    pass


class MediaExtractor(Protocol):
    def extract(self, url: str) -> dict[str, Any]: ...


class PageExtractor(Protocol):
    def extract(self, url: str) -> tuple[dict[str, Any], str]: ...


class YtDlpMediaExtractor:
    def __init__(self) -> None:
        self._options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "http_headers": build_request_headers(),
        }

    def extract(self, url: str) -> dict[str, Any]:
        try:
            with YoutubeDL(self._options) as downloader:
                return downloader.extract_info(url, download=False)
        except DownloadError as error:
            raise BilibiliExtractionError("Unable to parse this Bilibili link right now") from error


class BilibiliPageExtractor:
    def extract(self, url: str) -> tuple[dict[str, Any], str]:
        try:
            response = HTTP_CLIENT.get(
                url,
                headers=build_request_headers(),
            )
            response.raise_for_status()
        except httpx.HTTPError as error:
            raise BilibiliExtractionError("Unable to load this Bilibili page right now") from error
        state_match = PAGE_STATE_PATTERN.search(response.text)
        if not state_match:
            raise BilibiliExtractionError("Unable to extract data from this Bilibili page right now")
        try:
            return json.loads(state_match.group(1)), str(response.url)
        except json.JSONDecodeError as error:
            raise BilibiliExtractionError("Unable to decode data from this Bilibili page right now") from error


class BilibiliParserService:
    def __init__(
        self,
        media_extractor: MediaExtractor | None = None,
        page_extractor: PageExtractor | None = None,
    ) -> None:
        self._media_extractor = media_extractor or YtDlpMediaExtractor()
        self._page_extractor = page_extractor or BilibiliPageExtractor()

    def supports_url(self, url: str) -> bool:
        return extract_supported_bilibili_url(url) is not None

    def parse(self, url: str) -> VideoAnalysisResponse:
        normalized_url = normalize_bilibili_url(url)
        detail_url = resolve_bilibili_detail_url(normalized_url)
        detail_payload = fetch_share_card_detail_payload(detail_url)
        if detail_payload is not None:
            canonical_url, page_state = detail_payload
            return build_response(normalized_url, canonical_url, page_state, {})
        page_state, canonical_url = self._page_extractor.extract(detail_url)
        media_info = self._media_extractor.extract(canonical_url)
        return build_response(normalized_url, canonical_url, page_state, media_info)

    def build_share_card_svg(self, url: str, asset_proxy_path: str | None = None) -> str:
        normalized_url = normalize_bilibili_url(url)
        detail_url = resolve_bilibili_detail_url(normalized_url)
        detail_payload = fetch_share_card_detail_payload(detail_url)
        if detail_payload is not None:
            canonical_url, page_state = detail_payload
        else:
            page_state, canonical_url = self._page_extractor.extract(detail_url)
        card_data = build_share_card_data(canonical_url, page_state)
        return render_share_card_svg(card_data, asset_proxy_path=asset_proxy_path)


def build_request_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def build_media_access_headers() -> dict[str, str]:
    request_headers = build_request_headers()
    return {
        "User-Agent": request_headers["User-Agent"],
    }


def normalize_bilibili_url(url: str) -> str:
    extracted_url = extract_supported_bilibili_url(url)
    if extracted_url is None:
        raise InvalidBilibiliUrlError("Only bilibili.com and b23.tv links are supported")
    return sanitize_bilibili_url(extracted_url)


def extract_supported_bilibili_url(text: str) -> str | None:
    normalized_text = text.strip()
    if is_supported_bilibili_url(normalized_text):
        return normalized_text
    for candidate in EXTRACT_URL_PATTERN.findall(normalized_text):
        sanitized_candidate = candidate.rstrip(TRAILING_URL_PUNCTUATION)
        if is_supported_bilibili_url(sanitized_candidate):
            return sanitized_candidate
    host_match = re.search(r"(?:(?:https?://)?(?:www\.)?(?:bilibili\.com/video/[^\s<>'\"）)】]+|b23\.tv/[^\s<>'\"）)】]+))", normalized_text, re.IGNORECASE)
    if host_match:
        candidate = host_match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
        if candidate.lower().startswith(("bilibili.com", "www.bilibili.com", "b23.tv")):
            return f"https://{candidate}"
        if candidate.lower().startswith("www."):
            return f"https://{candidate}"
        return candidate
    return None


def sanitize_bilibili_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or parts.path or "/"
    sanitized_host = parts.netloc.lower()
    sanitized_url = urlunsplit((parts.scheme.lower(), sanitized_host, path, "", ""))
    return sanitized_url


def resolve_bilibili_detail_url(normalized_url: str) -> str:
    if extract_video_locator(normalized_url) is not None:
        return normalized_url
    try:
        response = HTTP_CLIENT.head(normalized_url, headers=build_request_headers())
        response.raise_for_status()
    except httpx.HTTPError:
        return normalized_url
    return sanitize_bilibili_url(str(response.url))


def fetch_share_card_detail_payload(normalized_url: str) -> tuple[str, dict[str, Any]] | None:
    locator = extract_video_locator(normalized_url)
    if locator is None:
        return None
    try:
        response = HTTP_CLIENT.get(
            "https://api.bilibili.com/x/web-interface/view/detail",
            params=locator,
            headers=build_request_headers(),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    payload = response.json().get("data")
    if not isinstance(payload, dict):
        return None
    view_data = payload.get("View")
    card_data = payload.get("Card")
    tags_data = payload.get("Tags")
    if not isinstance(view_data, dict) or not isinstance(card_data, dict):
        return None
    up_card = card_data.get("card") if isinstance(card_data.get("card"), dict) else {}
    bvid = coerce_string(view_data.get("bvid"))
    canonical_url = f"https://www.bilibili.com/video/{bvid}" if bvid else normalized_url
    return canonical_url, {
        "videoData": view_data,
        "upData": up_card,
        "tags": tags_data if isinstance(tags_data, list) else [],
        "aid": view_data.get("aid"),
        "cid": view_data.get("cid"),
    }


def extract_video_locator(normalized_url: str) -> dict[str, str] | None:
    parsed_url = urlsplit(normalized_url)
    path = parsed_url.path
    bvid_match = re.search(r"/(BV[0-9A-Za-z]+)", path)
    if bvid_match:
        return {"bvid": bvid_match.group(1)}
    aid_match = re.search(r"/av(\d+)", path, re.IGNORECASE)
    if aid_match:
        return {"aid": aid_match.group(1)}
    return None


def is_supported_bilibili_url(url: str) -> bool:
    try:
        parsed_url = urlparse(url)
    except ValueError:
        return False
    if parsed_url.scheme not in {"http", "https"}:
        return False
    host = (parsed_url.netloc or "").lower()
    return host == "b23.tv" or host == "bilibili.com" or host.endswith(".bilibili.com")


def build_response(
    input_url: str,
    canonical_url: str,
    page_state: dict[str, Any],
    media_info: dict[str, Any],
) -> VideoAnalysisResponse:
    video_data = page_state.get("videoData") if isinstance(page_state.get("videoData"), dict) else {}
    stat = video_data.get("stat") if isinstance(video_data.get("stat"), dict) else {}
    return VideoAnalysisResponse(
        product="Cortex",
        platform="bilibili",
        input_url=input_url,
        canonical_url=canonical_url,
        video_id=coerce_string(video_data.get("bvid")) or coerce_string(media_info.get("id")) or "",
        title=coerce_string(video_data.get("title")) or coerce_string(media_info.get("title")) or "",
        description=coerce_string(video_data.get("desc")) or coerce_string(media_info.get("description")),
        declaration=extract_bilibili_declaration(page_state),
        duration_seconds=coerce_float(video_data.get("duration")) or coerce_float(media_info.get("duration")),
        published_at=build_published_at(video_data.get("pubdate") or media_info.get("timestamp")),
        metrics=build_metrics(stat),
        video_source=build_video_source(page_state, media_info),
        cover_source=build_cover_source(video_data, media_info),
    )


def build_metrics(stat: dict[str, Any]) -> VideoMetrics:
    return VideoMetrics(
        play_count=coerce_int(stat.get("view")),
        danmaku_count=coerce_int(stat.get("danmaku")),
        comment_count=coerce_int(stat.get("reply")),
        like_count=coerce_int(stat.get("like")),
        share_count=coerce_int(stat.get("share")),
        favorite_count=coerce_int(stat.get("favorite")),
        coin_count=coerce_int(stat.get("coin")),
    )


def extract_bilibili_declaration(page_state: dict[str, Any]) -> str | None:
    candidates = collect_platform_declaration_candidates(
        page_state,
        keywords=[
            "仅供参考",
            "个人观点",
            "风险提示",
            "免责声明",
            "内容存在争议",
            "请谨慎甄别",
            "科普信息",
        ],
    )
    if candidates:
        return min(candidates, key=len)
    return None


def build_video_source(page_state: dict[str, Any], media_info: dict[str, Any]) -> VideoSourceFile:
    html5_source = fetch_html5_source_file(page_state)
    if html5_source is not None:
        return html5_source
    browser_source = fetch_browser_playable_source(page_state)
    if browser_source is not None:
        return browser_source
    return build_dash_video_source(media_info)


def fetch_html5_source_file(page_state: dict[str, Any]) -> VideoSourceFile | None:
    video_data = page_state.get("videoData") if isinstance(page_state.get("videoData"), dict) else {}
    bvid = coerce_string(video_data.get("bvid"))
    cid = coerce_int(video_data.get("cid")) or coerce_int(page_state.get("cid"))
    aid = coerce_int(video_data.get("aid")) or coerce_int(page_state.get("aid"))
    if cid is None or (bvid is None and aid is None):
        return None
    params: dict[str, Any] = {
        "cid": cid,
        "qn": 64,
        "platform": "html5",
        "high_quality": 1,
    }
    if bvid is not None:
        params["bvid"] = bvid
    else:
        params["avid"] = aid
    try:
        response = HTTP_CLIENT.get(
            "https://api.bilibili.com/x/player/playurl",
            params=params,
            headers=build_request_headers(),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    payload = response.json().get("data")
    if not isinstance(payload, dict):
        return None
    durl = payload.get("durl")
    if not isinstance(durl, list) or not durl:
        return None
    first_source = durl[0] if isinstance(durl[0], dict) else None
    if first_source is None:
        return None
    source_url = normalize_remote_asset_url(coerce_string(first_source.get("url")))
    if source_url is None:
        return None
    quality = coerce_int(payload.get("quality"))
    format_id = f"html5-durl-{quality}" if quality is not None else "html5-durl"
    width, height = find_quality_dimensions(quality)
    return VideoSourceFile(
        url=source_url,
        request_headers=build_media_access_headers(),
        source_mode="single_file",
        audio_url=None,
        format_id=format_id,
        quality=find_quality_label(payload, quality),
        container="mp4",
        width=width,
        height=height,
        fps=None,
    )


def fetch_browser_playable_source(page_state: dict[str, Any]) -> VideoSourceFile | None:
    aid = coerce_int(page_state.get("aid"))
    cid = coerce_int(page_state.get("cid"))
    if aid is None or cid is None:
        return None
    try:
        response = HTTP_CLIENT.get(
            "https://api.bilibili.com/x/player/playurl",
            params={
                "avid": aid,
                "cid": cid,
                "qn": 127,
                "fnval": 0,
                "fnver": 0,
                "fourk": 1,
            },
            headers=build_request_headers(),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    payload = response.json().get("data")
    if not isinstance(payload, dict):
        return None
    durl = payload.get("durl")
    if not isinstance(durl, list) or not durl:
        return None
    first_source = durl[0] if isinstance(durl[0], dict) else None
    if first_source is None:
        return None
    source_url = coerce_string(first_source.get("url"))
    if source_url is None:
        return None
    quality = coerce_int(payload.get("quality"))
    format_id = f"durl-{quality}" if quality is not None else None
    width, height = find_quality_dimensions(quality)
    return VideoSourceFile(
        url=source_url,
        request_headers=build_media_access_headers(),
        source_mode="single_file",
        audio_url=None,
        format_id=format_id,
        quality=find_quality_label(payload, quality),
        container="mp4",
        width=width,
        height=height,
        fps=None,
    )


def find_quality_label(payload: dict[str, Any], quality: int | None) -> str | None:
    support_formats = payload.get("support_formats")
    if isinstance(support_formats, list):
        for item in support_formats:
            if isinstance(item, dict) and coerce_int(item.get("quality")) == quality:
                return coerce_string(item.get("new_description")) or coerce_string(item.get("display_desc"))
    accept_description = payload.get("accept_description")
    if isinstance(accept_description, list) and accept_description:
        return coerce_string(accept_description[0])
    return None


def find_quality_dimensions(quality: int | None) -> tuple[int | None, int | None]:
    quality_map = {
        16: (640, 360),
        32: (852, 480),
        64: (1280, 720),
        74: (1280, 720),
        80: (1920, 1080),
        112: (1920, 1080),
        116: (1920, 1080),
        120: (3840, 2160),
        125: (3840, 2160),
        126: (3840, 2160),
        127: (7680, 4320),
    }
    return quality_map.get(quality, (None, None))


def build_dash_video_source(media_info: dict[str, Any]) -> VideoSourceFile:
    combined_url = coerce_string(media_info.get("url"))
    combined_format_id = coerce_string(media_info.get("format_id"))
    if combined_url:
        return VideoSourceFile(
            url=combined_url,
            request_headers=build_media_access_headers(),
            source_mode="single_file",
            audio_url=None,
            format_id=combined_format_id,
            quality=coerce_string(media_info.get("format")) or build_quality_label(media_info),
            container=coerce_string(media_info.get("ext")),
            width=coerce_int(media_info.get("width")),
            height=coerce_int(media_info.get("height")),
            fps=coerce_float(media_info.get("fps")),
        )
    requested_formats = media_info.get("requested_formats")
    video_stream = pick_requested_video_stream(requested_formats) or pick_best_video_stream(media_info.get("formats"))
    audio_stream = pick_requested_audio_stream(requested_formats) or pick_best_audio_stream(media_info.get("formats"))
    if not video_stream:
        raise BilibiliExtractionError("Unable to build the video source for this Bilibili link right now")
    video_url = coerce_string(video_stream.get("url"))
    if not video_url:
        raise BilibiliExtractionError("Unable to build the video source for this Bilibili link right now")
    return VideoSourceFile(
        url=video_url,
        request_headers=build_media_access_headers(),
        source_mode="separate_streams" if audio_stream else "single_file",
        audio_url=coerce_string(audio_stream.get("url")) if audio_stream else None,
        format_id=coerce_string(video_stream.get("format_id")) or combined_format_id,
        quality=build_quality_label(video_stream),
        container=coerce_string(video_stream.get("ext")),
        width=coerce_int(video_stream.get("width")),
        height=coerce_int(video_stream.get("height")),
        fps=coerce_float(video_stream.get("fps")),
    )


def build_cover_source(video_data: dict[str, Any], media_info: dict[str, Any]) -> SourceFile:
    source_url = normalize_remote_asset_url(coerce_string(video_data.get("pic")) or coerce_string(media_info.get("thumbnail")))
    return SourceFile(url=source_url, request_headers=build_media_access_headers())


def build_share_card_data(canonical_url: str, page_state: dict[str, Any]) -> ShareCardData:
    video_data = page_state.get("videoData") if isinstance(page_state.get("videoData"), dict) else {}
    up_data = page_state.get("upData") if isinstance(page_state.get("upData"), dict) else {}
    owner_data = video_data.get("owner") if isinstance(video_data.get("owner"), dict) else {}
    stat = video_data.get("stat") if isinstance(video_data.get("stat"), dict) else {}
    level_info = up_data.get("level_info") if isinstance(up_data.get("level_info"), dict) else {}
    tags = page_state.get("tags") if isinstance(page_state.get("tags"), list) else []
    duration_seconds = coerce_int(video_data.get("duration"))
    author_level = coerce_int(level_info.get("current_level"))
    official_verify = resolve_official_verify_badge(up_data, owner_data)
    return ShareCardData(
        title=coerce_string(video_data.get("title")) or "",
        canonical_url=canonical_url,
        cover_url=coerce_string(video_data.get("pic")),
        author=ShareCardAuthor(
            name=coerce_string(up_data.get("name")) or coerce_string(owner_data.get("name")) or "Bilibili Creator",
            avatar_url=coerce_string(up_data.get("face")) or coerce_string(owner_data.get("face")),
            badge_markup=build_bilibili_level_badge_markup(author_level),
            certification_icon_markup=build_bilibili_official_badge_icon_markup(official_verify),
            certification_text=build_official_verify_text(official_verify) if official_verify is not None else None,
        ),
        tags=build_tag_names(tags),
        primary_metrics=[
            ShareCardMetric(value=format_count_short(coerce_int(stat.get("like"))), icon_svg=BILIBILI_ICON_LIKE),
            ShareCardMetric(value=format_count_short(coerce_int(stat.get("share"))), icon_svg=BILIBILI_ICON_SHARE),
            ShareCardMetric(value=format_count_short(coerce_int(stat.get("favorite"))), icon_svg=BILIBILI_ICON_FAVORITE),
            ShareCardMetric(value=format_count_short(coerce_int(stat.get("coin"))), icon_svg=BILIBILI_ICON_COIN),
        ],
        secondary_metrics=[
            ShareCardMetric(label="时长", value=format_duration_clock(duration_seconds) or "--:--"),
            ShareCardMetric(label="播放", value=format_count_short(coerce_int(stat.get("view")))),
            ShareCardMetric(label="弹幕", value=format_count_short(coerce_int(stat.get("danmaku")))),
        ],
        branding=ShareCardBranding(
            logo_url="https://i0.hdslb.com/bfs/static/jinkela/long/images/favicon.ico",
            logo_x=1090,
            logo_y=554,
            logo_width=34,
            logo_height=34,
        ),
    )


def resolve_official_verify_badge(up_data: dict[str, Any], owner_data: dict[str, Any]) -> OfficialVerifyBadge | None:
    candidates = [
        up_data.get("Official"),
        up_data.get("official_verify"),
        owner_data.get("official"),
        owner_data.get("official_verify"),
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        official_type = coerce_int(candidate.get("type"))
        if official_type is None or official_type < 0:
            continue
        return OfficialVerifyBadge(
            type=official_type,
            title=coerce_string(candidate.get("title")),
            desc=coerce_string(candidate.get("desc")),
        )
    return None


def build_bilibili_level_badge_markup(level: int | None) -> str:
    font_url = "https://s1.hdslb.com/bfs/svg-next/font/2025-10-27/freshspace-zpjpp3aqht.ttf"
    codepoint = {
        0: 0xE042,
        1: 0xE043,
        2: 0xE044,
        3: 0xE045,
        4: 0xE046,
        5: 0xE047,
        6: 0xE048,
    }.get(level)
    if codepoint is None:
        return ""
    return f"""<style>
@font-face {{
  font-family: "BilibiliLevelIcon";
  src: url("{font_url}") format("truetype");
  font-weight: normal;
  font-style: normal;
}}
</style>
<text x="__BADGE_X__" y="__BADGE_Y__" fill="#000000" font-family="BilibiliLevelIcon" font-size="34">{chr(codepoint)}</text>"""


def build_bilibili_official_badge_icon_markup(official_verify: OfficialVerifyBadge | None) -> str:
    if official_verify is None:
        return ""
    color = resolve_official_badge_color(official_verify.type)
    return f"""<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)">
<circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.94"/>
<g transform="translate(1 1) scale(1.5)">
<path d="M16 8C16 12.4183 12.4183 16 8 16C3.58172 16 0 12.4183 0 8C0 3.58172 3.58172 0 8 0C12.4183 0 16 3.58172 16 8Z" fill="{color}"/>
<path fill-rule="evenodd" clip-rule="evenodd" d="M7.28832 12.7244C7.20127 12.767 7.1148 12.7988 7.02538 12.8C6.80863 12.8042 6.62919 12.6296 6.62564 12.4101C6.62742 12.3717 6.63512 12.3351 6.64814 12.2997L7.40676 8.78586L4.26392 8.79186C4.03651 8.79545 3.85825 8.6209 3.85352 8.40196C3.85588 8.27299 3.9228 8.15362 4.03118 8.08524L8.72206 3.2901C8.80852 3.23732 8.90149 3.20133 8.99743 3.20013C9.21477 3.19653 9.39303 3.37108 9.39776 3.59063C9.39599 3.65541 9.37822 3.71839 9.34506 3.77358L8.59118 7.23047H11.7388C11.9614 7.22687 12.1403 7.40142 12.1444 7.62096C12.1426 7.75113 12.0757 7.8705 11.9668 7.93888L7.28832 12.7244Z" fill="white"/>
</g>
</g>"""


def build_official_verify_text(official_verify: OfficialVerifyBadge) -> str:
    prefix = "bilibili机构认证" if official_verify.type == 1 else "bilibili个人认证"
    title = official_verify.title or official_verify.desc or ""
    if not title:
        return prefix
    return f"{prefix} {title}"


def resolve_official_badge_color(official_type: int) -> str:
    if official_type == 1:
        return "#00AEEC"
    return "#FFB02E"


def build_tag_names(tags: list[Any]) -> list[str]:
    tag_names: list[str] = []
    for item in tags:
        if not isinstance(item, dict):
            continue
        if coerce_string(item.get("tag_type")) == "bgm":
            continue
        tag_name = coerce_string(item.get("tag_name"))
        if tag_name:
            tag_names.append(tag_name)
    return tag_names


BILIBILI_ICON_LIKE = '<svg width="28" height="28" viewBox="0 0 36 36" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M9.77234 30.8573V11.7471H7.54573C5.50932 11.7471 3.85742 13.3931 3.85742 15.425V27.1794C3.85742 29.2112 5.50932 30.8573 7.54573 30.8573H9.77234ZM11.9902 30.8573V11.7054C14.9897 10.627 16.6942 7.8853 17.1055 3.33591C17.2666 1.55463 18.9633 0.814421 20.5803 1.59505C22.1847 2.36964 23.243 4.32583 23.243 6.93947C23.243 8.50265 23.0478 10.1054 22.6582 11.7471H29.7324C31.7739 11.7471 33.4289 13.402 33.4289 15.4435C33.4289 15.7416 33.3928 16.0386 33.3215 16.328L30.9883 25.7957C30.2558 28.7683 27.5894 30.8573 24.528 30.8573H11.9911H11.9902Z" fill="#9499A0"></path></svg>'
BILIBILI_ICON_COIN = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M14.045 25.5454C7.69377 25.5454 2.54504 20.3967 2.54504 14.0454C2.54504 7.69413 7.69377 2.54541 14.045 2.54541C20.3963 2.54541 25.545 7.69413 25.545 14.0454C25.545 17.0954 24.3334 20.0205 22.1768 22.1771C20.0201 24.3338 17.095 25.5454 14.045 25.5454ZM9.66202 6.81624H18.2761C18.825 6.81624 19.27 7.22183 19.27 7.72216C19.27 8.22248 18.825 8.62807 18.2761 8.62807H14.95V10.2903C17.989 10.4444 20.3766 12.9487 20.3855 15.9916V17.1995C20.3854 17.6997 19.9799 18.1052 19.4796 18.1052C18.9793 18.1052 18.5738 17.6997 18.5737 17.1995V15.9916C18.5667 13.9478 16.9882 12.2535 14.95 12.1022V20.5574C14.95 21.0577 14.5444 21.4633 14.0441 21.4633C13.5437 21.4633 13.1382 21.0577 13.1382 20.5574V12.1022C11.1 12.2535 9.52148 13.9478 9.51448 15.9916V17.1995C9.5144 17.6997 9.10883 18.1052 8.60856 18.1052C8.1083 18.1052 7.70273 17.6997 7.70265 17.1995V15.9916C7.71158 12.9487 10.0992 10.4444 13.1382 10.2903V8.62807H9.66202C9.11309 8.62807 8.66809 8.22248 8.66809 7.72216C8.66809 7.22183 9.11309 6.81624 9.66202 6.81624Z" fill="#9499A0"></path></svg>'
BILIBILI_ICON_FAVORITE = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path fill-rule="evenodd" clip-rule="evenodd" d="M19.8071 9.26152C18.7438 9.09915 17.7624 8.36846 17.3534 7.39421L15.4723 3.4972C14.8998 2.1982 13.1004 2.1982 12.4461 3.4972L10.6468 7.39421C10.1561 8.36846 9.25639 9.09915 8.19315 9.26152L3.94016 9.91102C2.63155 10.0734 2.05904 11.6972 3.04049 12.6714L6.23023 15.9189C6.96632 16.6496 7.29348 17.705 7.1299 18.7605L6.39381 23.307C6.14844 24.6872 7.62063 25.6614 8.84745 25.0119L12.4461 23.0634C13.4276 22.4951 14.6544 22.4951 15.6359 23.0634L19.2345 25.0119C20.4614 25.6614 21.8518 24.6872 21.6882 23.307L20.8703 18.7605C20.7051 17.705 21.0339 16.6496 21.77 15.9189L24.9597 12.6714C25.9412 11.6972 25.3687 10.0734 24.06 9.91102L19.8071 9.26152Z" fill="#9499A0"></path></svg>'
BILIBILI_ICON_SHARE = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M12.6058 10.3326V5.44359C12.6058 4.64632 13.2718 4 14.0934 4C14.4423 4 14.78 4.11895 15.0476 4.33606L25.3847 12.7221C26.112 13.3121 26.2087 14.3626 25.6007 15.0684C25.5352 15.1443 25.463 15.2144 25.3847 15.2779L15.0476 23.6639C14.4173 24.1753 13.4791 24.094 12.9521 23.4823C12.7283 23.2226 12.6058 22.8949 12.6058 22.5564V18.053C7.59502 18.053 5.37116 19.9116 2.57197 23.5251C2.47607 23.6489 2.00031 23.7769 2.00031 23.2122C2.00031 16.2165 3.90102 10.3326 12.6058 10.3326Z" fill="#9499A0"></path></svg>'


def pick_requested_video_stream(requested_formats: Any) -> dict[str, Any] | None:
    if not isinstance(requested_formats, list):
        return None
    for item in requested_formats:
        if isinstance(item, dict) and normalize_codec(item.get("vcodec")):
            return item
    return None


def pick_requested_audio_stream(requested_formats: Any) -> dict[str, Any] | None:
    if not isinstance(requested_formats, list):
        return None
    for item in requested_formats:
        if isinstance(item, dict) and not normalize_codec(item.get("vcodec")) and normalize_codec(item.get("acodec")):
            return item
    return None


def pick_best_video_stream(formats: Any) -> dict[str, Any] | None:
    candidates = [item for item in ensure_format_list(formats) if normalize_codec(item.get("vcodec"))]
    if not candidates:
        return None
    return max(candidates, key=video_stream_sort_key)


def pick_best_audio_stream(formats: Any) -> dict[str, Any] | None:
    candidates = [item for item in ensure_format_list(formats) if normalize_codec(item.get("acodec")) and not normalize_codec(item.get("vcodec"))]
    if not candidates:
        return None
    return max(candidates, key=audio_stream_sort_key)


def ensure_format_list(formats: Any) -> list[dict[str, Any]]:
    if not isinstance(formats, list):
        return []
    return [item for item in formats if isinstance(item, dict)]


def video_stream_sort_key(item: dict[str, Any]) -> tuple[int, float, float]:
    return (
        coerce_int(item.get("height")) or 0,
        coerce_float(item.get("fps")) or 0.0,
        coerce_float(item.get("tbr")) or 0.0,
    )


def audio_stream_sort_key(item: dict[str, Any]) -> float:
    return coerce_float(item.get("tbr")) or 0.0


def build_quality_label(item: dict[str, Any]) -> str | None:
    quality = coerce_string(item.get("format_note"))
    if quality:
        return quality
    height = coerce_int(item.get("height"))
    if height:
        return f"{height}p"
    return coerce_string(item.get("format"))


def normalize_codec(value: Any) -> str | None:
    codec = coerce_string(value)
    if codec in {None, "none"}:
        return None
    return codec
