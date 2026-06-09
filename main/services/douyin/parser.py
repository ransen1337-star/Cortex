import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import urlparse
from urllib.parse import urlsplit

import httpx

from main.services.models import SourceFile
from main.services.models import VideoAnalysisResponse
from main.services.models import VideoAuthor
from main.services.models import VideoAuthorVerification
from main.services.models import VideoMetrics
from main.services.models import VideoSourceFile
from main.services.share_card import ShareCardAuthor
from main.services.share_card import ShareCardBranding
from main.services.share_card import ShareCardData
from main.services.share_card import ShareCardMetric
from main.services.share_card import render_share_card_svg
from main.services.utils import build_published_at
from main.services.utils import coerce_float
from main.services.utils import coerce_int
from main.services.utils import coerce_string
from main.services.utils import collect_platform_declaration_candidates
from main.services.utils import create_http_client
from main.services.utils import format_count_short
from main.services.utils import format_duration_clock
from main.services.utils import normalize_remote_asset_url


HTTP_CLIENT = create_http_client(30)
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)
MOBILE_HEADERS = {
    "User-Agent": MOBILE_USER_AGENT,
    "Referer": "https://www.iesdouyin.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
EXTRACT_URL_PATTERN = re.compile(r"https?://[^\s<>'\"]+")
META_CONTENT_PATTERN = re.compile(r'<meta[^>]+content="([^"]+)"', re.IGNORECASE)
PUBLIC_PLAY_COUNT_PATTERNS = (
    re.compile(r"(?P<count>\d[\d,]*(?:\.\d+)?(?:万|亿)?)\s*(?:次)?(?:播放量?|浏览量?|观看量?)"),
    re.compile(r"(?:播放量?|浏览量?|观看量?|已播放)\s*(?P<count>\d[\d,]*(?:\.\d+)?(?:万|亿)?)"),
)
TRAILING_URL_PUNCTUATION = ".,;!?，。；！？、)]）】>"
DOUYIN_CDN_HOST_PRIORITIES = {
    "p11.douyinpic.com": 0,
    "p11-sign.douyinpic.com": 0,
    "p26.douyinpic.com": 1,
    "p26-sign.douyinpic.com": 1,
    "p3.douyinpic.com": 2,
    "p3-sign.douyinpic.com": 2,
}


@dataclass(frozen=True)
class DouyinPageData:
    item: dict[str, Any]
    html: str
    user_profile: dict[str, Any] | None


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
        page_data = fetch_douyin_page_data(input_url)
        return build_response(input_url, page_data)

    def build_share_card_svg(self, url: str, asset_proxy_path: str | None = None) -> str:
        input_url = normalize_douyin_url(url)
        page_data = fetch_douyin_page_data(input_url)
        return render_share_card_svg(
            build_share_card_data(
                page_data.item,
                user_profile=page_data.user_profile,
                page_html=page_data.html,
            ),
            asset_proxy_path=asset_proxy_path,
        )


def build_mobile_headers() -> dict[str, str]:
    return dict(MOBILE_HEADERS)


def build_profile_headers() -> dict[str, str]:
    return {
        "User-Agent": DESKTOP_USER_AGENT,
        "Referer": "https://www.iesdouyin.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


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
    return host in {"v.douyin.com", "iesdouyin.com", "www.iesdouyin.com", "www.douyin.com", "douyin.com"}


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
            response.raise_for_status()
        except httpx.HTTPError:
            return None
    redirect_candidates = [str(response.url), response.headers.get("location", "")]
    redirect_candidates.extend(str(item.url) for item in response.history)
    for candidate in redirect_candidates:
        video_id = extract_douyin_video_id(candidate)
        if video_id is not None:
            return video_id
    return None


def fetch_douyin_page_data(normalized_url: str) -> DouyinPageData:
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
    page_payload = find_video_page_payload(router_data)
    if page_payload is None:
        raise DouyinExtractionError("Unable to find the Douyin video payload right now")
    video_info = page_payload.get("videoInfoRes")
    if not isinstance(video_info, dict):
        raise DouyinExtractionError("Unable to find the Douyin video payload right now")
    item_list = video_info.get("item_list")
    if not isinstance(item_list, list) or not item_list:
        raise DouyinExtractionError("This Douyin video is unavailable or cannot be accessed from the public share page")
    item = item_list[0]
    if not isinstance(item, dict):
        raise DouyinExtractionError("This Douyin video is unavailable or cannot be accessed from the public share page")
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    return DouyinPageData(
        item=item,
        html=response.text,
        user_profile=fetch_douyin_user_profile(author),
    )


def extract_router_data_text(html: str) -> str | None:
    marker = "window._ROUTER_DATA = "
    start_index = html.find(marker)
    if start_index < 0:
        return None
    json_start = html.find("{", start_index + len(marker))
    if json_start < 0:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for index in range(json_start, len(html)):
        char = html[index]
        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return html[json_start : index + 1]
    return None


def find_video_page_payload(router_data: dict[str, Any]) -> dict[str, Any] | None:
    loader_data = router_data.get("loaderData")
    if not isinstance(loader_data, dict):
        return None
    exact_payload = loader_data.get("video_(id)/page")
    if isinstance(exact_payload, dict):
        return exact_payload
    for value in loader_data.values():
        if isinstance(value, dict) and isinstance(value.get("videoInfoRes"), dict):
            return value
    return None


def build_response(input_url: str, page_data: DouyinPageData) -> VideoAnalysisResponse:
    item = page_data.item
    aweme_id = coerce_string(item.get("aweme_id")) or ""
    description = coerce_string(item.get("desc"))
    text_extra = item.get("text_extra")
    statistics = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    video_data = item.get("video") if isinstance(item.get("video"), dict) else {}
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    verification = resolve_douyin_verification(author, page_data.user_profile)
    return VideoAnalysisResponse(
        product="Cortex",
        platform="douyin",
        input_url=input_url,
        canonical_url=f"https://www.douyin.com/video/{aweme_id}",
        video_id=aweme_id,
        title=build_douyin_display_title(description, text_extra) or aweme_id,
        description=description,
        declaration=extract_douyin_declaration(item),
        duration_seconds=build_duration_seconds(video_data.get("duration")),
        published_at=build_published_at(item.get("create_time")),
        author=build_douyin_author(author, page_data.user_profile, verification),
        metrics=VideoMetrics(
            play_count=resolve_douyin_play_count(statistics, page_data.html),
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


def build_share_card_data(
    item: dict[str, Any],
    user_profile: dict[str, Any] | None = None,
    page_html: str | None = None,
) -> ShareCardData:
    aweme_id = coerce_string(item.get("aweme_id")) or ""
    description = coerce_string(item.get("desc"))
    text_extra = item.get("text_extra")
    statistics = item.get("statistics") if isinstance(item.get("statistics"), dict) else {}
    video_data = item.get("video") if isinstance(item.get("video"), dict) else {}
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    verification = resolve_douyin_verification(author, user_profile)
    duration_seconds = build_duration_seconds_int(video_data.get("duration"))
    return ShareCardData(
        title=build_douyin_display_title(description, text_extra) or aweme_id,
        canonical_url=f"https://www.douyin.com/video/{aweme_id}",
        cover_url=choose_best_cover_url(extract_url_list(video_data.get("cover"))),
        cover_layout="portrait",
        author=ShareCardAuthor(
            name=coerce_string(author.get("nickname")) or "Douyin Creator",
            avatar_url=resolve_author_avatar_url(author, user_profile),
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
            ShareCardMetric(label="播放", value=format_count_short(resolve_douyin_play_count(statistics, page_html))),
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
        quality=extract_ratio_label(play_url, video_data),
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
        response = HTTP_CLIENT.get(
            normalized_play_url,
            headers={"User-Agent": MOBILE_USER_AGENT},
            follow_redirects=False,
        )
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
    return SourceFile(
        url=choose_best_cover_url(url_list),
        request_headers=None,
    )


def resolve_douyin_play_count(statistics: dict[str, Any], page_html: str | None = None) -> int | None:
    play_count = coerce_int(statistics.get("play_count"))
    if play_count is not None and play_count > 0:
        return play_count
    fallback_play_count = extract_public_play_count_from_html(page_html)
    if fallback_play_count is not None:
        return fallback_play_count
    if play_count is None:
        return None
    interaction_counts = (
        coerce_int(statistics.get("digg_count")),
        coerce_int(statistics.get("comment_count")),
        coerce_int(statistics.get("share_count")),
        coerce_int(statistics.get("collect_count")),
    )
    if any((count or 0) > 0 for count in interaction_counts):
        return None
    return play_count


def extract_public_play_count_from_html(page_html: str | None) -> int | None:
    if not page_html:
        return None
    search_spaces = [unescape(content) for content in META_CONTENT_PATTERN.findall(page_html)]
    search_spaces.append(unescape(page_html))
    for text in search_spaces:
        for pattern in PUBLIC_PLAY_COUNT_PATTERNS:
            match = pattern.search(text)
            if match is None:
                continue
            play_count = parse_public_count_text(match.group("count"))
            if play_count is not None:
                return play_count
    return None


def parse_public_count_text(value: str | None) -> int | None:
    text = coerce_string(value)
    if text is None:
        return None
    normalized_text = text.replace(",", "")
    multiplier = 1
    if normalized_text.endswith("万"):
        multiplier = 10000
        normalized_text = normalized_text[:-1]
    elif normalized_text.endswith("亿"):
        multiplier = 100000000
        normalized_text = normalized_text[:-1]
    try:
        return int(float(normalized_text) * multiplier)
    except ValueError:
        return None


def choose_first_url(urls: list[Any]) -> str | None:
    for url in urls:
        normalized_url = normalize_remote_asset_url(coerce_string(url))
        if normalized_url is not None:
            return normalized_url
    return None


def choose_preferred_douyin_asset_url(urls: list[Any]) -> str | None:
    normalized_urls: list[str] = []
    for url in urls:
        normalized_url = normalize_remote_asset_url(coerce_string(url))
        if normalized_url is not None and normalized_url not in normalized_urls:
            normalized_urls.append(normalized_url)
    if not normalized_urls:
        return None
    prioritized_urls = sorted(
        enumerate(normalized_urls),
        key=lambda item: (resolve_douyin_asset_priority(item[1]), item[0]),
    )
    return prioritized_urls[0][1]


def resolve_douyin_asset_priority(url: str) -> int:
    try:
        host = urlsplit(url).netloc.lower()
    except ValueError:
        return len(DOUYIN_CDN_HOST_PRIORITIES) + 1
    return DOUYIN_CDN_HOST_PRIORITIES.get(host, len(DOUYIN_CDN_HOST_PRIORITIES))


def choose_best_cover_url(urls: list[Any]) -> str | None:
    normalized_urls: list[str] = []
    for url in urls:
        normalized_url = normalize_remote_asset_url(coerce_string(url))
        if normalized_url is not None:
            normalized_urls.append(normalized_url)
    if not normalized_urls:
        return None
    for normalized_url in normalized_urls:
        if re.search(r"\.(?:jpe?g|png)(?:\?|$)", normalized_url, re.IGNORECASE):
            return normalized_url
    return normalized_urls[0]


def fetch_douyin_user_profile(author: Any) -> dict[str, Any] | None:
    if not isinstance(author, dict):
        return None
    sec_uid = coerce_string(author.get("sec_uid"))
    unique_id = coerce_string(author.get("unique_id"))
    params: dict[str, str] = {}
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
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
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


def resolve_author_avatar_url(author: dict[str, Any], user_profile: dict[str, Any] | None = None) -> str | None:
    avatar_candidates: list[Any] = []
    for source in (author, user_profile or {}):
        for key in ("avatar_larger", "avatar_medium", "avatar_thumb"):
            avatar_candidates.extend(extract_url_list(source.get(key)))
    return choose_preferred_douyin_asset_url(avatar_candidates)


def resolve_douyin_verification(author: dict[str, Any], user_profile: dict[str, Any] | None) -> dict[str, str | None]:
    profile = user_profile or {}
    account_cert_info = parse_account_cert_info(author.get("account_cert_info"))
    if not account_cert_info:
        account_cert_info = parse_account_cert_info(profile.get("account_cert_info"))
    enterprise_verify_reason = pick_first_non_none(
        coerce_string(author.get("enterprise_verify_reason")),
        coerce_string(profile.get("enterprise_verify_reason")),
    )
    custom_verify = pick_first_non_none(
        coerce_string(author.get("custom_verify")),
        coerce_string(profile.get("custom_verify")),
    )
    label_text = coerce_string(account_cert_info.get("label_text"))
    verification_type = pick_first_non_none(
        coerce_int(author.get("verification_type")),
        coerce_int(profile.get("verification_type")),
    )
    is_biz_account = bool(pick_first_non_none(coerce_int(account_cert_info.get("is_biz_account")), 0))
    label_style = coerce_int(account_cert_info.get("label_style"))
    certification_text = pick_first_non_none(enterprise_verify_reason, custom_verify, label_text)
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
    if not isinstance(value, str):
        return {}
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed_value, dict):
        return parsed_value
    return {}


def build_douyin_author(
    author: dict[str, Any],
    user_profile: dict[str, Any] | None,
    verification: dict[str, str | None],
) -> VideoAuthor | None:
    profile = user_profile or {}
    name = pick_first_non_none(
        coerce_string(author.get("nickname")),
        coerce_string(profile.get("nickname")),
    )
    unique_id = pick_first_non_none(
        coerce_string(author.get("unique_id")),
        coerce_string(profile.get("unique_id")),
        coerce_string(author.get("short_id")),
        coerce_string(profile.get("short_id")),
    )
    sec_uid = pick_first_non_none(
        coerce_string(author.get("sec_uid")),
        coerce_string(profile.get("sec_uid")),
    )
    profile_url = build_douyin_profile_url(sec_uid)
    avatar_url = resolve_author_avatar_url(author, profile)
    signature = pick_first_non_none(
        coerce_string(author.get("signature")),
        coerce_string(profile.get("signature")),
    )
    follower_count = pick_first_non_none(
        coerce_int(profile.get("mplatform_followers_count")),
        coerce_int(author.get("mplatform_followers_count")),
        coerce_int(profile.get("follower_count")),
        coerce_int(author.get("follower_count")),
    )
    total_favorited = pick_first_non_none(
        coerce_int(profile.get("total_favorited")),
        coerce_int(author.get("total_favorited")),
    )
    verification_payload = build_douyin_author_verification(verification)
    if not any(
        (
            name,
            unique_id,
            sec_uid,
            profile_url,
            avatar_url,
            signature,
            follower_count,
            total_favorited,
            verification_payload,
        )
    ):
        return None
    return VideoAuthor(
        name=name,
        unique_id=unique_id,
        sec_uid=sec_uid,
        profile_url=profile_url,
        avatar_url=avatar_url,
        signature=signature,
        follower_count=follower_count,
        total_favorited=total_favorited,
        verification=verification_payload,
    )


def build_douyin_author_verification(verification: dict[str, str | None]) -> VideoAuthorVerification | None:
    theme = verification["theme"]
    text = verification["text"]
    if not theme and not text:
        return None
    return VideoAuthorVerification(
        is_verified=True,
        theme=theme,
        text=text,
    )


def build_douyin_profile_url(sec_uid: str | None) -> str | None:
    if not sec_uid:
        return None
    return f"https://www.douyin.com/user/{sec_uid}"


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


def build_douyin_display_title(description: str | None, text_extra: Any) -> str | None:
    description_text = coerce_string(description)
    if description_text:
        return description_text.splitlines()[0].strip()
    tags = build_tag_names(text_extra)
    if not tags:
        return None
    return " ".join(f"#{tag}" for tag in tags[:3])


def build_tag_names(text_extra: Any) -> list[str]:
    if not isinstance(text_extra, list):
        return []
    tag_names: list[str] = []
    for item in text_extra:
        if not isinstance(item, dict):
            continue
        tag_name = coerce_string(item.get("hashtag_name"))
        if tag_name and tag_name not in tag_names:
            tag_names.append(tag_name)
    return tag_names


def build_duration_seconds(value: Any) -> float | None:
    duration = coerce_float(value)
    if duration is None:
        return None
    if duration > 1000:
        duration = duration / 1000
    return round(duration, 3)


def build_duration_seconds_int(value: Any) -> int | None:
    duration_seconds = build_duration_seconds(value)
    if duration_seconds is None:
        return None
    return max(0, int(duration_seconds))


def extract_ratio_label(play_url: str | None, video_data: dict[str, Any] | None = None) -> str | None:
    if play_url:
        ratio_match = re.search(r"(?:[?&]ratio=)([\da-zA-Z]+)", play_url)
        if ratio_match is not None:
            return ratio_match.group(1).lower()
    if isinstance(video_data, dict):
        width = coerce_int(video_data.get("width"))
        height = coerce_int(video_data.get("height"))
        if width is not None and height is not None:
            return f"{min(width, height)}p"
    return None


def pick_first_non_none(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


DOUYIN_ICON_LIKE = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M14 24.8l-1.5-1.3C6 17.9 2 14.3 2 9.8 2 6.2 4.8 3.4 8.4 3.4c2 0 3.9.9 5.1 2.4 1.2-1.5 3.1-2.4 5.1-2.4 3.6 0 6.4 2.8 6.4 6.4 0 4.5-4 8.1-10.5 13.7L14 24.8z" fill="#9499A0"/></svg>'
DOUYIN_ICON_COMMENT = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M14 4C7.4 4 2 8.7 2 14.5c0 3.3 1.8 6.2 4.7 8.1V27l4.1-2.3c1 .2 2.1.3 3.2.3 6.6 0 12-4.7 12-10.5S20.6 4 14 4z" fill="#9499A0"/></svg>'
DOUYIN_ICON_FAVORITE = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M14 3.5l3.3 6.7 7.4 1.1-5.3 5.2 1.3 7.3L14 20.4l-6.7 3.4 1.3-7.3-5.3-5.2 7.4-1.1L14 3.5z" fill="#9499A0"/></svg>'
DOUYIN_ICON_SHARE = '<svg width="28" height="28" viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg"><path d="M16.8 4.2 25 12.4c1 1 1 2.2 0 3.2l-8.2 8.2c-.8.8-2.1.8-2.9 0-.4-.4-.6-.9-.6-1.5v-4.4c-5.9.1-8.5 1.5-11 4.8-.3.3-.8.2-.8-.3 0-8.1 3.7-13.3 11.8-14V5.7c0-1.1.9-2 2-2 .5 0 1 .2 1.5.5z" fill="#9499A0"/></svg>'
DOUYIN_RED_VERIFICATION_ICON = '<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)"><circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.96"/><circle cx="13" cy="13" r="10.5" fill="#F25468"/><path d="M8.3 7.6h2.9l1.8 5.6 1.8-5.6h2.9l-3.2 10h-3z" fill="#FFFFFF"/></g>'
DOUYIN_BLUE_VERIFICATION_ICON = '<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)"><circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.96"/><circle cx="13" cy="13" r="10.5" fill="#168BFF"/><path d="M8.3 7.6h2.9l1.8 5.6 1.8-5.6h2.9l-3.2 10h-3z" fill="#FFFFFF"/></g>'
DOUYIN_GOLD_VERIFICATION_ICON = '<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)"><circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.96"/><circle cx="13" cy="13" r="10.5" fill="#FFB21A"/><path d="M8.3 7.6h2.9l1.8 5.6 1.8-5.6h2.9l-3.2 10h-3z" fill="#FFFFFF"/></g>'
DOUYIN_GRAY_VERIFICATION_ICON = '<g transform="translate(__CERT_ICON_X__ __CERT_ICON_Y__)"><circle cx="13" cy="13" r="13" fill="#FFFFFF" fill-opacity="0.96"/><circle cx="13" cy="13" r="10.5" fill="#7C8594"/><path d="M8.3 7.6h2.9l1.8 5.6 1.8-5.6h2.9l-3.2 10h-3z" fill="#FFFFFF"/></g>'
DOUYIN_LOGO_SVG = '<g><path d="M160.8 30.4c3.2 23.7 17.4 45.2 38.6 58.6 12.4 7.8 26.5 12.8 41.4 14.7v36.9c-29.4-1.5-57.1-13-79.3-32.8v67.9c0 19.1-7.6 37.4-21 51-13.7 13.7-32 21.1-51.1 21.1-39.8 0-72-32.2-72-72 0-39.7 32.2-71.9 72-71.9 4.6 0 9.1.4 13.5 1.3v37.1a37.9 37.9 0 0 0-13.5-2.4c-20 0-36.1 16.1-36.1 35.9 0 19.9 16.1 36 36.1 36 19.8 0 35.9-16.1 35.9-36V8h35.5v22.4z" fill="#25F4EE"/><path d="M169.4 22c3.2 23.7 17.4 45.2 38.6 58.6 12.4 7.8 26.5 12.8 41.4 14.7v36.9c-29.4-1.5-57.1-13-79.3-32.8v67.9c0 19.1-7.6 37.4-21 51-13.7 13.7-32 21.1-51.1 21.1-15.4 0-29.7-4.8-41.5-13 13.1 14.2 31.8 23.1 52.5 23.1 19.1 0 37.4-7.4 51.1-21.1 13.4-13.6 21-31.9 21-51v-67.9c22.2 19.8 49.9 31.3 79.3 32.8v-36.9c-14.9-1.9-29-6.9-41.4-14.7-21.2-13.4-35.4-34.9-38.6-58.6h-11z" fill="#FE2C55"/><path d="M165.2 26.1c3.2 23.7 17.4 45.2 38.6 58.6 12.4 7.8 26.5 12.8 41.4 14.7v36.9c-29.4-1.5-57.1-13-79.3-32.8v67.9c0 19.1-7.6 37.4-21 51-13.7 13.7-32 21.1-51.1 21.1-17.5 0-33.6-6.3-46.1-16.6-11.1-12.8-17.8-29.6-17.8-48 0-39.7 32.2-71.9 72-71.9 4.6 0 9.1.4 13.5 1.3v37.1a37.9 37.9 0 0 0-13.5-2.4c-20 0-36.1 16.1-36.1 35.9 0 19.9 16.1 36 36.1 36 19.8 0 35.9-16.1 35.9-36V12h27.4v14.1z" fill="#111111"/></g>'
