import os
from urllib.parse import unquote_plus

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response

from main.services import BilibiliExtractionError
from main.services import BilibiliParserService
from main.services import DouyinExtractionError
from main.services import DouyinParserService
from main.services import InvalidBilibiliUrlError
from main.services import InvalidDouyinUrlError
from main.services import VideoAnalysisResponse
from main.services.share_card import DEFAULT_CARD_FONT_STACK
from main.services.share_card import set_share_card_font_stack
from main.services.utils import create_http_client
from main.services.utils import normalize_remote_asset_url


APP_TITLE = "Video Analysis API"
APP_VERSION = "0.4.0"
SHARE_CARD_SVG_EXAMPLE = '<svg width="1200" height="630" viewBox="0 0 1200 630" xmlns="http://www.w3.org/2000/svg"></svg>'
SHARE_CARD_ASSET_PROXY_PATH = "/api/v1/share-card/assets"
ASSET_PROXY_CLIENT = create_http_client(20)

BILIBILI_VIDEO_ANALYSIS_EXAMPLES = {
    "bilibili_source_file": {
        "summary": "Bilibili source file",
        "value": {
            "product": "Video Analysis",
            "platform": "bilibili",
            "input_url": "https://www.bilibili.com/video/BV1xx411c7mu",
            "canonical_url": "https://www.bilibili.com/video/BV1xx411c7mu",
            "video_id": "BV1xx411c7mu",
            "title": "Example Bilibili video",
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
                "coin_count": 17036,
            },
            "video_source": {
                "url": "https://example.com/video.mp4",
                "request_headers": {"User-Agent": "Mozilla/5.0"},
                "source_mode": "single_file",
                "format_id": "html5-durl-64",
                "quality": "720P",
                "container": "mp4",
                "width": 1280,
                "height": 720,
            },
            "cover_source": {
                "url": "https://example.com/cover.jpg",
                "request_headers": {"User-Agent": "Mozilla/5.0"},
            },
        },
    }
}

DOUYIN_VIDEO_ANALYSIS_EXAMPLES = {
    "douyin_source_file": {
        "summary": "Douyin source file",
        "value": {
            "product": "Video Analysis",
            "platform": "douyin",
            "input_url": "https://www.iesdouyin.com/share/video/7606942757253803610/",
            "canonical_url": "https://www.douyin.com/video/7606942757253803610",
            "video_id": "7606942757253803610",
            "title": "Example Douyin video",
            "description": "Public video metadata extracted from Douyin.",
            "declaration": "Platform-provided declaration when available.",
            "duration_seconds": 17.267,
            "published_at": "2026-02-18T13:00:00Z",
            "metrics": {
                "comment_count": 238,
                "like_count": 7171,
                "share_count": 159,
                "favorite_count": 255,
            },
            "video_source": {
                "url": "https://example.com/video.mp4",
                "source_mode": "single_file",
                "format_id": "douyin-play",
                "quality": "720p",
                "container": "mp4",
                "width": 2160,
                "height": 3840,
            },
            "cover_source": {"url": "https://example.com/cover.jpeg"},
        },
    }
}


def create_app() -> FastAPI:
    configure_share_card_fonts()

    bilibili_service = BilibiliParserService()
    douyin_service = DouyinParserService()

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description=(
            "Public video analysis APIs for Bilibili and Douyin, "
            "plus reusable SVG share-card rendering."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
        openapi_tags=[
            {"name": "Video Analysis", "description": "Shared service operations."},
            {
                "name": "Bilibili Video Analysis",
                "description": "Analyze Bilibili links and return metrics, direct video source files, and direct cover source files.",
            },
            {
                "name": "Douyin Video Analysis",
                "description": "Analyze Douyin links and return metrics, direct video source files, and direct cover source files.",
            },
            {"name": "Share Card", "description": "Render platform share cards."},
        ],
    )

    register_routes(app, bilibili_service, douyin_service)
    return app


def configure_share_card_fonts() -> None:
    font_stack = os.getenv("VIDEO_ANALYSIS_SHARE_CARD_FONT_FAMILY", DEFAULT_CARD_FONT_STACK)
    set_share_card_font_stack(font_stack)


def register_routes(
    app: FastAPI,
    bilibili_service: BilibiliParserService,
    douyin_service: DouyinParserService,
) -> None:
    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/health", tags=["Video Analysis"], summary="Health Check")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        SHARE_CARD_ASSET_PROXY_PATH,
        include_in_schema=False,
    )
    def share_card_asset(url: str = Query(..., description="Remote asset URL")) -> Response:
        normalized_url = normalize_remote_asset_url(url)
        if normalized_url is None:
            raise HTTPException(status_code=400, detail="Invalid remote asset URL")
        try:
            upstream = ASSET_PROXY_CLIENT.get(
                normalized_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )
            upstream.raise_for_status()
        except Exception as error:
            raise HTTPException(status_code=502, detail="Unable to load share-card asset") from error
        media_type = upstream.headers.get("content-type") or "application/octet-stream"
        return Response(
            content=upstream.content,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get(
        "/api/v1/video-analysis",
        response_model=VideoAnalysisResponse,
        response_model_exclude_none=True,
        include_in_schema=False,
        tags=["Video Analysis"],
        summary="Analyze Video",
        description="Legacy unified entry kept for compatibility.",
    )
    def analyze_video(
        request: Request,
        url: str = Query(
            ...,
            description="Bilibili or Douyin video link",
            examples=[
                "https://www.bilibili.com/video/BV1xx411c7mu",
                "https://b23.tv/xxxxxx",
                "https://www.douyin.com/video/7606942757253803610",
                "https://www.iesdouyin.com/share/video/7606942757253803610/",
            ],
        ),
    ) -> VideoAnalysisResponse:
        normalized_input = resolve_request_url_input(request, url)
        service = resolve_video_service(normalized_input, bilibili_service, douyin_service)
        return run_platform_analysis(
            service,
            normalized_input,
            (InvalidBilibiliUrlError, InvalidDouyinUrlError),
            (BilibiliExtractionError, DouyinExtractionError),
        )

    @app.get(
        "/api/v1/bilibili/video-analysis",
        response_model=VideoAnalysisResponse,
        response_model_exclude_none=True,
        tags=["Bilibili Video Analysis"],
        summary="Analyze Bilibili Video",
        description="Return core metrics, a direct video source file, and a direct cover source file from a Bilibili video link.",
        responses={200: build_json_example_response(BILIBILI_VIDEO_ANALYSIS_EXAMPLES)},
    )
    def analyze_bilibili_video(
        request: Request,
        url: str = Query(
            ...,
            description="Bilibili video link",
            examples=[
                "https://www.bilibili.com/video/BV1xx411c7mu",
                "https://b23.tv/xxxxxx",
            ],
        ),
    ) -> VideoAnalysisResponse:
        normalized_input = resolve_request_url_input(request, url)
        return run_platform_analysis(
            bilibili_service,
            normalized_input,
            InvalidBilibiliUrlError,
            BilibiliExtractionError,
        )

    @app.get("/api/v1/bilibili/parse", include_in_schema=False)
    def analyze_bilibili_legacy(
        request: Request,
        url: str = Query(..., description="Bilibili video link"),
    ) -> VideoAnalysisResponse:
        return analyze_bilibili_video(request, url)

    @app.get(
        "/api/v1/douyin/video-analysis",
        response_model=VideoAnalysisResponse,
        response_model_exclude_none=True,
        tags=["Douyin Video Analysis"],
        summary="Analyze Douyin Video",
        description="Return core metrics, a direct video source file, and a direct cover source file from a Douyin video link.",
        responses={200: build_json_example_response(DOUYIN_VIDEO_ANALYSIS_EXAMPLES)},
    )
    def analyze_douyin_video(
        request: Request,
        url: str = Query(
            ...,
            description="Douyin video link",
            examples=[
                "https://www.douyin.com/video/7606942757253803610",
                "https://www.iesdouyin.com/share/video/7606942757253803610/",
            ],
        ),
    ) -> VideoAnalysisResponse:
        normalized_input = resolve_request_url_input(request, url)
        return run_platform_analysis(
            douyin_service,
            normalized_input,
            InvalidDouyinUrlError,
            DouyinExtractionError,
        )

    @app.get("/api/v1/douyin/parse", include_in_schema=False)
    def analyze_douyin_legacy(
        request: Request,
        url: str = Query(..., description="Douyin video link"),
    ) -> VideoAnalysisResponse:
        return analyze_douyin_video(request, url)

    @app.get(
        "/api/v1/bilibili/share-card",
        tags=["Share Card"],
        summary="Render Bilibili Share Card",
        description="Render a horizontal Bilibili share card as SVG with author, title, metrics, duration, play count, and the Bilibili logo.",
        responses={200: build_svg_example_response()},
    )
    def bilibili_share_card(
        request: Request,
        url: str = Query(
            ...,
            description="Bilibili video link",
            examples=[
                "https://www.bilibili.com/video/BV1xx411c7mu",
                "https://b23.tv/xxxxxx",
            ],
        ),
    ) -> Response:
        normalized_input = resolve_request_url_input(request, url)
        try:
            svg = bilibili_service.build_share_card_svg(
                normalized_input,
                asset_proxy_path=SHARE_CARD_ASSET_PROXY_PATH,
            )
            return Response(content=svg, media_type="image/svg+xml")
        except InvalidBilibiliUrlError as error:
            raise HTTPException(status_code=400, detail=error.message) from error
        except BilibiliExtractionError as error:
            raise HTTPException(status_code=502, detail=error.message) from error

    @app.get(
        "/api/v1/douyin/share-card",
        tags=["Share Card"],
        summary="Render Douyin Share Card",
        description="Render a horizontal Douyin share card as SVG with author, title, tags, metrics, cover, and the Douyin logo.",
        responses={200: build_svg_example_response()},
    )
    def douyin_share_card(
        request: Request,
        url: str = Query(
            ...,
            description="Douyin video link",
            examples=[
                "https://www.douyin.com/video/7606942757253803610",
                "https://www.iesdouyin.com/share/video/7606942757253803610/",
            ],
        ),
    ) -> Response:
        normalized_input = resolve_request_url_input(request, url)
        try:
            svg = douyin_service.build_share_card_svg(
                normalized_input,
                asset_proxy_path=SHARE_CARD_ASSET_PROXY_PATH,
            )
            return Response(content=svg, media_type="image/svg+xml")
        except InvalidDouyinUrlError as error:
            raise HTTPException(status_code=400, detail=error.message) from error
        except DouyinExtractionError as error:
            raise HTTPException(status_code=502, detail=error.message) from error


def resolve_request_url_input(request: Request, url: str | None) -> str:
    raw_query = request.scope.get("query_string", b"").decode("utf-8", errors="ignore")
    if "url=" in raw_query:
        return unquote_plus(raw_query.split("url=", 1)[1]).strip()
    return (url or "").strip()


def resolve_video_service(
    url: str,
    bilibili_service: BilibiliParserService,
    douyin_service: DouyinParserService,
) -> BilibiliParserService | DouyinParserService:
    if bilibili_service.supports_url(url):
        return bilibili_service
    if douyin_service.supports_url(url):
        return douyin_service
    raise HTTPException(status_code=400, detail="Only Bilibili and Douyin video links are supported")


def run_platform_analysis(
    service: BilibiliParserService | DouyinParserService,
    normalized_input: str,
    invalid_errors: type[Exception] | tuple[type[Exception], ...],
    extraction_errors: type[Exception] | tuple[type[Exception], ...],
) -> VideoAnalysisResponse:
    try:
        return service.parse(normalized_input)
    except invalid_errors as error:
        raise HTTPException(status_code=400, detail=error.message) from error
    except extraction_errors as error:
        raise HTTPException(status_code=502, detail=error.message) from error


def build_json_example_response(examples: dict[str, object]) -> dict[str, object]:
    return {
        "description": "Successful Response",
        "content": {"application/json": {"examples": examples}},
    }


def build_svg_example_response() -> dict[str, object]:
    return {
        "description": "SVG share card",
        "content": {"image/svg+xml": {"example": SHARE_CARD_SVG_EXAMPLE}},
    }


app = create_app()
