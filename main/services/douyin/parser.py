import json
import re
from typing import Any
from urllib.parse import urlparse
from urllib.parse import urlsplit

import httpx

from main.services.models import SourceFile
from main.services.share_card import ShareCardAuthor
from main.services.share_card import ShareCardBranding
from main.services.share_card import ShareCardData
from main.services.share_card import ShareCardMetric
from main.services.share_card import render_share_card_svg
from main.services.models import VideoAnalysisResponse
from main.services.models import VideoMetrics
from main.services.models import VideoSourceFile
from main.services.utils import build_published_at
from main.services.utils import collect_platform_declaration_candidates
from main.services.utils import coerce_int
from main.services.utils import coerce_string
from main.services.utils import create_http_client
from main.services.utils import format_count_short
from main.services.utils import format_duration_clock
from main.services.utils import normalize_remote_asset_url


HTTP_CLIENT = create_http_client(30)
MOBILE_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
MOBILE_HEADERS = {
    "User-Agent": MOBILE_USER_AGENT,
    "Referer": "https://www.iesdouyin.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
EXTRACT_URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+")
TRAILING_URL_PUNCTUATION = ".,;!?，。；！？、)]）】>"


class DouyinExtractionError(Exception):
    def __init__(self, message: str = "Unable to parse this Douyin link right now") -> None:
        self.message = message
        super().__init__(message)


class InvalidDouyinUrlError(DouyinExtractionError):
    pass


class DouyinParserService:
    def supports_url(self, url: str) -> bool:
        return extract_supported_douyin_url(url) is not None

    def parse(self, url: str) -> VideoAnalysisResponse:
        input_url = normalize_douyin_url(url)
        item = fetch_douyin_item(input_url)
        return build_response(input_url, item)

    def build_share_card_svg(self, url: str, asset_proxy_path: str | None = None) -> str:
        input_url = normalize_douyin_url(url)
        item = fetch_douyin_item(input_url)
        return render_share_card_svg(build_share_card_data(item), asset_proxy_path=asset_proxy_path)


def build_mobile_headers() -> dict[str, str]:
    return dict(MOBILE_HEADERS)


def normalize_douyin_url(url: str) -> str:
    extracted_url = extract_supported_douyin_url(url)
    if extracted_url is None:
        raise InvalidDouyinUrlError("Only douyin.com, iesdouyin.com, and v.douyin.com video links are supported")
    video_id = extract_douyin_video_id(extracted_url) or resolve_douyin_video_id(extracted_url)
    if video_id is None:
        raise InvalidDouyinUrlError("Unable to extract the Douyin video id from this link")
    return f"https://www.iesdouyin.com/share/video/{video_id}/"


def extract_supported_douyin_url(text: str) -> str | None:
    normalized_text = text.strip()
    if is_supported_douyin_url(normalized_text):
        return normalized_text
    for candidate in EXTRACT_URL_PATTERN.findall(normalized_text):
        sanitized_candidate = candidate.rstrip(TRAILING_URL_PUNCTUATION)
        if is_supported_douyin_url(sanitized_candidate):
            return sanitized_candidate
    host_match = re.search(
        r"(?:(?:https?://)?(?:www\.)?(?:douyin\.com/video/[^\s<>'\"]+|iesdouyin\.com/share/video/[^\s<>'\"]+|v\.douyin\.com/[^\s<>'\"]+))",
        normalized_text,
        re.IGNORECASE,
    )
    if host_match is None:
        return None
    candidate = host_match.group(0).rstrip(TRAILING_URL_PUNCTUATION)
    if candidate.lower().startswith(("douyin.com", "www.douyin.com", "iesdouyin.com", "v.douyin.com")):
        return f"https://{candidate}"
    return candidate


def is_supported_douyin_url(url: str) -> bool:
    try:
        parsed_url = urlparse(url)
    except ValueError:
        return False
    if parsed_url.scheme not in {"http", "https"}:
        return False
    host = (parsed_url.netloc or "").lower()
    return host == "v.douyin.com" or host == "iesdouyin.com" or host == "www.iesdouyin.com" or host == "www.douyin.com" or host == "douyin.com"


def extract_douyin_video_id(url: str) -> str | None:
    parsed_url = urlsplit(url.strip())
    path = parsed_url.path
    for pattern in (r"/video/(\d+)", r"/share/video/(\d+)"):
        match = re.search(pattern, path)
        if match is not None:
            return match.group(1)
    return None


def resolve_douyin_video_id(url: str) -> str | None:
    try:
        response = HTTP_CLIENT.head(url, headers=MOBILE_HEADERS)
        response.raise_for_status()
    except httpx.HTTPError:
        try:
            response = HTTP_CLIENT.get(url, headers=MOBILE_HEADERS)
        except httpx.HTTPError:
            return None
    for candidate in [str(response.url)] + [response.headers.get("location", "")] + [str(item.url) for item in response.history]:
        video_id = extract_douyin_video_id(candidate)
        if video_id is not None:
            return video_id
    return None


def fetch_douyin_item(normalized_url: str) -> dict[str, Any]:
    try:
        response = HTTP_CLIENT.get(normalized_url, headers=MOBILE_HEADERS)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise DouyinExtractionError("Unable to load this Douyin page right now") from error
    router_data_text = extract_router_data_text(response.text)
    if router_data_text is None:
        raise DouyinExtractionError("Unable to extract data from this Douyin page right now")
    try:
        router_data = json.loads(router_data_text)
    except json.JSONDecodeError as error:
        raise DouyinExtractionError("Unable to decode data from this Douyin page right now") from error
    page_payload = router_data.get("loaderData", {}).get("video_(id)/page")
    if not isinstance(page_payload, dict):
        raise DouyinExtractionError("Unable to find the Douyin video payload right now")
    video_info = page_payload.get("videoInfoRes")
    if not isinstance(video_info, dict):
        raise DouyinExtractionError("Unable to find the Douyin video payload right now")
    item_list = video_info.get("item_list")
    if isinstance(item_list, list) and item_list:
        item = item_list[0]
        if isinstance(item, dict):
            return item
    raise DouyinExtractionError("This Douyin video is unavailable or cannot be accessed from the public share page")


def extract_router_data_text(html: str) -> str | None:
    marker = "window._ROUTER_DATA = "
    start_index = html.find(marker)
    if start_index < 0:
        return None
    json_start = start_index + len(marker)
    json_end = html.find("</script>", json_start)
    if json_end < 0:
        return None
    return html[json_start:json_end].strip()


def build_response(input_url: str, item: dict[str, Any]) -> VideoAnalysisResponse:
    aweme_id = coerce_string(item.get("aweme_id")) or ""
    description = coerce_string(item.get("desc"))
    text_extra = item.get("text_extra")
    statistics = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    video_data = item.get("video") if isinstance(item.get("video"), dict) else {}
    play_count = resolve_douyin_play_count(statistics)
    display_title = build_douyin_display_title(description, text_extra) or aweme_id
    return VideoAnalysisResponse(
        product="Video Analysis",
        platform="douyin",
        input_url=input_url,
        canonical_url=f"https://www.douyin.com/video/{aweme_id}",
        video_id=aweme_id,
        title=display_title,
        description=description,
        declaration=extract_douyin_declaration(item),
        duration_seconds=build_duration_seconds(video_data.get("duration")),
        published_at=build_published_at(item.get("create_time")),
        metrics=VideoMetrics(
            play_count=play_count,
            danmaku_count=None,
            comment_count=coerce_int(statistics.get("comment_count")),
            like_count=coerce_int(statistics.get("digg_count")),
            share_count=coerce_int(statistics.get("share_count")),
            favorite_count=coerce_int(statistics.get("collect_count")),
            coin_count=None,
        ),
        video_source=build_video_source(video_data),
        cover_source=build_cover_source(video_data),
    )


def build_share_card_data(item: dict[str, Any], user_profile: dict[str, Any] | None = None) -> ShareCardData:
    aweme_id = coerce_string(item.get("aweme_id")) or ""
    description = coerce_string(item.get("desc")) or aweme_id
    text_extra = item.get("text_extra")
    statistics = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    video_data = item.get("video") if isinstance(item.get("video"), dict) else {}
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    duration_seconds = build_duration_seconds_int(video_data.get("duration"))
    play_count = resolve_douyin_play_count(statistics)
    verification = resolve_douyin_verification(author, user_profile)
    return ShareCardData(
        title=build_douyin_display_title(description, text_extra) or aweme_id,
        canonical_url=f"https://www.douyin.com/video/{aweme_id}",
        cover_url=choose_best_cover_url(extract_url_list(video_data.get("cover"))),
        cover_layout="portrait",
        author=ShareCardAuthor(
            name=coerce_string(author.get("nickname")) or "Douyin Creator",
            avatar_url=resolve_author_avatar_url(author),
            certification_icon_markup=build_douyin_verification_icon_markup(verification["theme"]),
            certification_text=verification["text"],
        ),
        tags=build_tag_names(text_extra),
        primary_metrics=[
            ShareCardMetric(value=format_count_short(coerce_int(statistics.get("digg_count"))), icon_svg=DOUYIN_ICON_LIKE),
            ShareCardMetric(value=format_count_short(coerce_int(statistics.get("comment_count"))), icon_svg=DOUYIN_ICON_COMMENT),
            ShareCardMetric(value=format_count_short(coerce_int(statistics.get("collect_count"))), icon_svg=DOUYIN_ICON_FAVORITE),
            ShareCardMetric(value=format_count_short(coerce_int(statistics.get("share_count"))), icon_svg=DOUYIN_ICON_SHARE),
        ],
        secondary_metrics=[
            ShareCardMetric(label="时长", value=format_duration_clock(duration_seconds) or "--:--"),
            ShareCardMetric(label="播放", value=format_count_short(play_count)),
            ShareCardMetric(label="评论", value=format_count_short(coerce_int(statistics.get("comment_count")))),
        ],
        branding=ShareCardBranding(
            logo_svg=DOUYIN_LOGO_SVG,
            logo_x=1082,
            logo_y=544,
            logo_width=50,
            logo_height=50,
            logo_view_box="0 0 256 256",
        ),
    )


def build_video_source(video_data: dict[str, Any]) -> VideoSourceFile:
    play_addr = video_data.get("play_addr") if isinstance(video_data.get("play_addr"), dict) else {}
    url_list = play_addr.get("url_list") if isinstance(play_addr.get("url_list"), list) else []
    play_url = choose_first_url(url_list)
    if play_url is None:
        raise DouyinExtractionError("Unable to build the video source for this Douyin link right now")
    source_url = resolve_douyin_play_url(play_url)
    if source_url is None:
        raise DouyinExtractionError("Unable to build the video source for this Douyin link right now")
    return VideoSourceFile(
        url=source_url,
        request_headers=None,
        source_mode="single_file",
        audio_url=None,
        format_id="douyin-play",
        quality=extract_ratio_label(play_url),
        container="mp4",
        width=coerce_int(video_data.get("width")),
        height=coerce_int(video_data.get("height")),
        fps=None,
    )


def extract_douyin_declaration(item: dict[str, Any]) -> str | None:
    risk_infos = item.get("risk_infos") if isinstance(item.get("risk_infos"), dict) else {}
    declaration = coerce_string(risk_infos.get("content"))
    if declaration:
        return declaration
    label_top_text = coerce_string(item.get("label_top_text"))
    if label_top_text:
        return label_top_text
    candidates = collect_platform_declaration_candidates(
        item,
        keywords=[
            "仅供参考",
            "个人观点",
            "风险提示",
            "免责声明",
            "请理性甄别",
        ],
    )
    if candidates:
        return min(candidates, key=len)
    return None


def resolve_douyin_play_url(play_url: str) -> str | None:
    normalized_play_url = normalize_remote_asset_url(play_url)
    if normalized_play_url is None:
        return None
    normalized_play_url = normalized_play_url.replace("/playwm/", "/play/")
    try:
        response = HTTP_CLIENT.get(normalized_play_url, headers={"User-Agent": MOBILE_USER_AGENT}, follow_redirects=False)
    except httpx.HTTPError:
        return normalized_play_url
    location = response.headers.get("location")
    if location:
        return normalize_remote_asset_url(location)
    if response.status_code == 200:
        return str(response.url)
    return normalized_play_url


def build_cover_source(video_data: dict[str, Any]) -> SourceFile:
    cover = video_data.get("cover") if isinstance(video_data.get("cover"), dict) else {}
    url_list = cover.get("url_list") if isinstance(cover.get("url_list"), list) else []
    return SourceFile(url=choose_best_cover_url(url_list), request_headers=None)


def resolve_douyin_play_count(statistics: dict[str, Any]) -> int | None:
    play_count = coerce_int(statistics.get("play_count"))
    if play_count is None:
        return None
    if play_count > 0:
        return play_count
    interaction_counts = (
        coerce_int(statistics.get("digg_count")),
        coerce_int(statistics.get("comment_count")),
        coerce_int(statistics.get("share_count")),
        coerce_int(statistics.get("collect_count")),
    )
    if any((count or 0) > 0 for count in interaction_counts):
        return None
    return play_count


def choose_first_url(urls: list[Any]) -> str | None:
    for url in urls:
        normalized_url = normalize_remote_asset_url(coerce_string(url))
        if normalized_url is not None:
            return normalized_url
    return None


def fetch_douyin_user_profile(author: Any) -> dict[str, Any] | None:
    if not isinstance(author, dict):
        return None
    params: dict[str, str] = {}
    sec_uid = coerce_string(author.get("sec_uid"))
    unique_id = coerce_string(author.get("unique_id"))
    if sec_uid:
        params["sec_uid"] = sec_uid
    elif unique_id:
        params["unique_id"] = unique_id
    else:
        return None
    try:
        response = HTTP_CLIENT.get(
            "https://www.iesdouyin.com/web/api/v2/user/info/",
            params=params,
            headers=build_profile_headers(),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    payload = response.json()
    user_info = payload.get("user_info")
    if not isinstance(user_info, dict):
        return None
    return user_info


def extract_url_list(source: Any) -> list[Any]:
    if not isinstance(source, dict):
        return []
    url_list = source.get("url_list")
    if not isinstance(url_list, list):
        return []
    return url_list


def resolve_author_avatar_url(author: dict[str, Any]) -> str | None:
    for key in ("avatar_medium", "avatar_thumb"):
        avatar_url = choose_first_url(extract_url_list(author.get(key)))
        if avatar_url is not None:
            return avatar_url
    return None


def resolve_douyin_verification(author: dict[str, Any], user_profile: dict[str, Any] | None) -> dict[str, str | None]:
    profile = user_profile or {}
    account_cert_info = parse_account_cert_info(profile.get("account_cert_info"))
    enterprise_verify_reason = (
        coerce_string(author.get("enterprise_verify_reason"))
        or coerce_string(profile.get("enterprise_verify_reason"))
    )
    custom_verify = coerce_string(author.get("custom_verify")) or coerce_string(profile.get("custom_verify"))
    label_text = coerce_string(account_cert_info.get("label_text"))
    verification_type = coerce_int(author.get("verification_type")) or coerce_int(profile.get("verification_type"))
    is_biz_account = bool(coerce_int(account_cert_info.get("is_biz_account")))
    label_style = coerce_int(account_cert_info.get("label_style"))
    certification_text = enterprise_verify_reason or custom_verify or label_text
    certification_theme: str | None = None
    if label_style == 5 or enterprise_verify_reason:
        certification_theme = "red"
    elif is_biz_account:
        certification_theme = "blue"
    elif verification_type == 1 or custom_verify or label_style in {1, 2, 3, 4}:
        certification_theme = "gold"
    elif certification_text:
        certification_theme = "gray"
    if certification_theme == "red" and not certification_text:
        certification_text = "抖音官方认证"
    elif certification_theme == "blue" and not certification_text:
        certification_text = "抖音企业认证"
    elif certification_theme == "gold" and not certification_text:
        certification_text = "抖音个人认证"
    elif certification_theme == "gray" and not certification_text:
        certification_text = "抖音认证"
    return {
        "theme": certification_theme,
        "text": certification_text,
    }


def parse_account_cert_info(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def build_douyin_verification_icon_markup(theme: str | None) -> str:
    if theme == "red":
        return DOUYIN_RED_VERIFICATION_ICON
    if theme == "blue":
        return DOUYIN_BLUE_VERIFICATION_ICON
    if theme == "gold":
        return DOUYIN_GOLD_VERIFICATION_ICON
    if theme == "gray":
        return DOUYIN_GRAY_VERIFICATION_ICON
    return ""


def build_tag_names(text_extra: Any) -> list[str]:
    if not isinstance(text_extra, list):
        return []
    tag_names: list[str] = []
    for item in text_extra:
        if not isinstance(item, dict):
            continue
        tag_name = coerce_string(item.get("hashtag_name"))
        if not tag_name or tag_name in tag_names:
            continue
        tag_names.append(tag_name)
    return tag_names


def build_douyin_display_title(description: str | None, text_extra: Any) -> str | None:
    raw_text = coerce_string(description)
    tag_names = build_tag_names(text_extra)
    if raw_text is None:
        return " ".join(tag_names[:4]) or None
    if not isinstance(text_extra, list):
        return normalize_douyin_title_text(strip_douyin_hashtag_text(raw_text)) or " ".join(tag_names[:4]) or raw_text
    removal_ranges: list[tuple[int, int]] = []
    for item in text_extra:
        if not isinstance(item, dict):
            continue
        if coerce_int(item.get("type")) != 1:
            continue
        start = coerce_int(item.get("start"))
        end = coerce_int(item.get("end"))
        hashtag_name = coerce_string(item.get("hashtag_name"))
        if start is None or end is None or start < 0 or end <= start or end > len(raw_text) or not hashtag_name:
            continue
        range_start = start
        while range_start > 0 and raw_text[range_start - 1].isspace():
            range_start -= 1
        removal_ranges.append((range_start, end))
    if not removal_ranges:
        return normalize_douyin_title_text(strip_douyin_hashtag_text(raw_text)) or " ".join(tag_names[:4]) or raw_text
    merged_ranges = merge_ranges(removal_ranges)
    parts: list[str] = []
    cursor = 0
    for start, end in merged_ranges:
        if cursor < start:
            parts.append(raw_text[cursor:start])
        cursor = end
    if cursor < len(raw_text):
        parts.append(raw_text[cursor:])
    cleaned_text = normalize_douyin_title_text("".join(parts))
    return cleaned_text or normalize_douyin_title_text(strip_douyin_hashtag_text(raw_text)) or " ".join(tag_names[:4]) or raw_text


def merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda value: (value[0], value[1]))
    merged_ranges = [sorted_ranges[0]]
    for start, end in sorted_ranges[1:]:
        last_start, last_end = merged_ranges[-1]
        if start <= last_end:
            merged_ranges[-1] = (last_start, max(last_end, end))
            continue
        merged_ranges.append((start, end))
    return merged_ranges


def strip_douyin_hashtag_text(text: str) -> str:
    return re.sub(r"(?:^|\s)#[^\s#]+", " ", text)


def normalize_douyin_title_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip(" \n\r\t#")
    normalized = re.sub(r"\s([,.!?，。！？；：])", r"\1", normalized)
    return normalized.strip()


def choose_best_cover_url(urls: list[Any]) -> str | None:
    normalized_urls = [normalize_remote_asset_url(coerce_string(url)) for url in urls]
    normalized_urls = [url for url in normalized_urls if url is not None]
    if not normalized_urls:
        return None
    for url in normalized_urls:
        if ".jpeg" in url or ".jpg" in url:
            return url
    return normalized_urls[0]


def build_duration_seconds(duration_ms: Any) -> float | None:
    duration_value = coerce_int(duration_ms)
    if duration_value is None:
        return None
    return duration_value / 1000


def build_duration_seconds_int(duration_ms: Any) -> int | None:
    duration_value = coerce_int(duration_ms)
    if duration_value is None:
        return None
    return duration_value // 1000


def build_profile_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Referer": "https://www.iesdouyin.com/",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def extract_ratio_label(url: str) -> str | None:
    ratio_match = re.search(r"[?&]ratio=([^&]+)", url)
    if ratio_match is None:
        return None
    return ratio_match.group(1)


DOUYIN_ICON_LIKE = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M14 24.8l-1.5-1.3C6 17.9 2 14.3 2 9.8 2 6.2 4.8 3.4 8.4 3.4c2 0 3.9.9 5.1 2.4 1.2-1.5 3.1-2.4 5.1-2.4 3.6 0 6.4 2.8 6.4 6.4 0 4.5-4 8.1-10.5 13.7L14 24.8z" fill="#9499A0"/></svg>'
DOUYIN_ICON_COMMENT = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M14 4C7.4 4 2 8.7 2 14.5c0 3.3 1.8 6.2 4.7 8.1V27l4.1-2.3c1 .2 2.1.3 3.2.3 6.6 0 12-4.7 12-10.5S20.6 4 14 4z" fill="#9499A0"/></svg>'
DOUYIN_ICON_FAVORITE = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M14 3.5l3.3 6.7 7.4 1.1-5.3 5.2 1.3 7.3L14 20.4l-6.7 3.4 1.3-7.3-5.3-5.2 7.4-1.1L14 3.5z" fill="#9499A0"/></svg>'
DOUYIN_ICON_SHARE = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M16.8 4.2 25 12.4c1 1 1 2.2 0 3.2l-8.2 8.2c-.8.8-2.1.8-2.9 0-.4-.4-.6-.9-.6-1.5v-4.4c-5.9.1-8.5 1.5-11 4.8-.3.3-.8.2-.8-.3 0-8.1 3.7-13.3 11.8-14V5.7c0-1.1.9-2 2-2 .5 0 1 .2 1.5.5z" fill="#9499A0"/></svg>'
DOUYIN_RED_VERIFICATION_ICON = '<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)"><circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.96"/><circle cx="13" cy="13" r="10.5" fill="#F25468"/><path d="M8.3 7.6h2.9l1.8 5.6 1.8-5.6h2.9l-3.2 10h-3z" fill="#FFFFFF"/></g>'
DOUYIN_BLUE_VERIFICATION_ICON = '<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)"><circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.96"/><circle cx="13" cy="13" r="10.5" fill="#168BFF"/><path d="M8.3 7.6h2.9l1.8 5.6 1.8-5.6h2.9l-3.2 10h-3z" fill="#FFFFFF"/></g>'
DOUYIN_GOLD_VERIFICATION_ICON = '<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)"><circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.96"/><circle cx="13" cy="13" r="10.5" fill="#FFB21A"/><path d="M8.3 7.6h2.9l1.8 5.6 1.8-5.6h2.9l-3.2 10h-3z" fill="#FFFFFF"/></g>'
DOUYIN_GRAY_VERIFICATION_ICON = '<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)"><circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.96"/><circle cx="13" cy="13" r="10.5" fill="#7C8594"/><path d="M8.3 7.6h2.9l1.8 5.6 1.8-5.6h2.9l-3.2 10h-3z" fill="#FFFFFF"/></g>'
DOUYIN_LOGO_SVG = '<g><path d="M160.8 30.4c3.2 23.7 17.4 45.2 38.6 58.6 12.4 7.8 26.5 12.8 41.4 14.7v36.9c-29.4-1.5-57.1-13-79.3-32.8v67.9c0 19.1-7.6 37.4-21 51-13.7 13.7-32 21.1-51.1 21.1-39.8 0-72-32.2-72-72 0-39.7 32.2-71.9 72-71.9 4.6 0 9.1.4 13.5 1.3v37.1a37.9 37.9 0 0 0-13.5-2.4c-20 0-36.1 16.1-36.1 35.9 0 19.9 16.1 36 36.1 36 19.8 0 35.9-16.1 35.9-36V8h35.5v22.4z" fill="#25F4EE"/><path d="M169.4 22c3.2 23.7 17.4 45.2 38.6 58.6 12.4 7.8 26.5 12.8 41.4 14.7v36.9c-29.4-1.5-57.1-13-79.3-32.8v67.9c0 19.1-7.6 37.4-21 51-13.7 13.7-32 21.1-51.1 21.1-15.4 0-29.7-4.8-41.5-13 13.1 14.2 31.8 23.1 52.5 23.1 19.1 0 37.4-7.4 51.1-21.1 13.4-13.6 21-31.9 21-51v-67.9c22.2 19.8 49.9 31.3 79.3 32.8v-36.9c-14.9-1.9-29-6.9-41.4-14.7-21.2-13.4-35.4-34.9-38.6-58.6h-11z" fill="#FE2C55"/><path d="M165.2 26.1c3.2 23.7 17.4 45.2 38.6 58.6 12.4 7.8 26.5 12.8 41.4 14.7v36.9c-29.4-1.5-57.1-13-79.3-32.8v67.9c0 19.1-7.6 37.4-21 51-13.7 13.7-32 21.1-51.1 21.1-17.5 0-33.6-6.3-46.1-16.6-11.1-12.8-17.8-29.6-17.8-48 0-39.7 32.2-71.9 72-71.9 4.6 0 9.1.4 13.5 1.3v37.1a37.9 37.9 0 0 0-13.5-2.4c-20 0-36.1 16.1-36.1 35.9 0 19.9 16.1 36 36.1 36 19.8 0 35.9-16.1 35.9-36V12h27.4v14.1z" fill="#111111"/></g>'
