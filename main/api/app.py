import os
from typing import Any
from collections.abc import Callable
from urllib.parse import quote_plus
from urllib.parse import unquote_plus

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response

from main.api.examples import BILIBILI_VIDEO_ANALYSIS_EXAMPLES
from main.api.examples import DOUYIN_VIDEO_ANALYSIS_EXAMPLES
from main.api.examples import build_image_example_response
from main.api.examples import build_json_example_response
from main.core.branding import PROJECT_DESCRIPTION
from main.core.branding import PROJECT_NAME
from main.services import BilibiliExtractionError
from main.services import BilibiliParserService
from main.services import DouyinExtractionError
from main.services import DouyinParserService
from main.services import InvalidBilibiliUrlError
from main.services import InvalidDouyinUrlError
from main.services import VideoAnalysisResponse
from main.services.share_card import DEFAULT_CARD_FONT_STACK
from main.services.share_card import set_share_card_font_stack
from main.services.share_card.rasterizer import ShareCardRenderError
from main.services.share_card.rasterizer import render_share_card_image
from main.services.utils import BILIBILI_ASSET_REFERER
from main.services.utils import DOUYIN_ASSET_REFERER
from main.services.utils import build_remote_asset_request_headers
from main.services.utils import create_http_client
from main.services.utils import normalize_remote_asset_url


APP_TITLE = PROJECT_NAME
APP_VERSION = "0.5.0"
SHARE_CARD_ASSET_PROXY_PATH = "/api/v1/share-card/assets"
ASSET_PROXY_CLIENT = create_http_client(20)

VideoService = BilibiliParserService | DouyinParserService
AssetProxyFetcher = Callable[[str], tuple[bytes, str]]
ShareCardRenderer = Callable[..., tuple[bytes, str]]


def build_asset_proxy_request_headers(url: str) -> dict[str, str]:
    return build_remote_asset_request_headers(url)


def create_default_asset_proxy_fetcher(*, asset_client: Any | None = None) -> AssetProxyFetcher:
    asset_client = asset_client or ASSET_PROXY_CLIENT

    def fetch_asset(url: str) -> tuple[bytes, str]:
        upstream = asset_client.get(url, headers=build_asset_proxy_request_headers(url))
        upstream.raise_for_status()
        media_type = upstream.headers.get("content-type") or "application/octet-stream"
        return upstream.content, media_type

    return fetch_asset


def create_app(
    *,
    bilibili_service: BilibiliParserService | None = None,
    douyin_service: DouyinParserService | None = None,
    asset_proxy_fetcher: AssetProxyFetcher | None = None,
    share_card_renderer: ShareCardRenderer | None = None,
) -> FastAPI:
    configure_share_card_fonts()

    bilibili_service = bilibili_service or BilibiliParserService()
    douyin_service = douyin_service or DouyinParserService()
    asset_proxy_fetcher = asset_proxy_fetcher or create_default_asset_proxy_fetcher()
    share_card_renderer = share_card_renderer or render_share_card_image

    app = FastAPI(
        title=APP_TITLE,
        version=APP_VERSION,
        description=PROJECT_DESCRIPTION,
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url=None,
        openapi_tags=[
            {"name": "Cortex", "description": "Shared Cortex service operations."},
            {
                "name": "Bilibili Analysis",
                "description": "Analyze Bilibili links and return metrics, direct video source files, and direct cover source files.",
            },
            {
                "name": "Douyin Analysis",
                "description": "Analyze Douyin links and return metrics, direct video source files, and direct cover source files.",
            },
            {"name": "Share Card", "description": "Render platform share cards."},
        ],
    )

    register_routes(
        app,
        bilibili_service=bilibili_service,
        douyin_service=douyin_service,
        asset_proxy_fetcher=asset_proxy_fetcher,
        share_card_renderer=share_card_renderer,
    )
    return app


def configure_share_card_fonts() -> None:
    font_stack = (
        os.getenv("CORTEX_SHARE_CARD_FONT_FAMILY")
        or os.getenv("VIDEO_ANALYSIS_SHARE_CARD_FONT_FAMILY")
        or DEFAULT_CARD_FONT_STACK
    )
    set_share_card_font_stack(font_stack)


def register_routes(
    app: FastAPI,
    *,
    bilibili_service: BilibiliParserService,
    douyin_service: DouyinParserService,
    asset_proxy_fetcher: AssetProxyFetcher,
    share_card_renderer: ShareCardRenderer,
) -> None:
    @app.get("/", include_in_schema=False)
    def index() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/health", tags=["Cortex"], summary="Health Check")
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
            content, media_type = asset_proxy_fetcher(normalized_url)
        except Exception as error:
            raise HTTPException(status_code=502, detail="Unable to load share-card asset") from error
        return Response(
            content=content,
            media_type=media_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get(
        "/api/v1/video-analysis",
        response_model=VideoAnalysisResponse,
        include_in_schema=False,
        tags=["Cortex"],
        summary="Analyze Video",
        description="Legacy unified Cortex entry kept for compatibility.",
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
        tags=["Bilibili Analysis"],
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
        tags=["Douyin Analysis"],
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
        description="Render a horizontal Bilibili share card as SVG or PNG. PNG mode supports performance, balanced, and quality presets.",
        responses={200: build_image_example_response()},
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
        mode: str | None = Query(
            None,
            description="Share-card output mode. Defaults to png when omitted",
            pattern="^(svg|png)$",
        ),
        preset: str = Query(
            "balanced",
            description="PNG render preset. Only used when mode=png",
            pattern="^(performance|balanced|quality)$",
        ),
        format: str | None = Query(
            None,
            description="Deprecated legacy share-card format alias",
            pattern="^(svg|png|jpg|jpeg)$",
            deprecated=True,
        ),
    ) -> Response:
        normalized_input = resolve_request_url_input(
            request,
            url,
            ignored_suffix_params=("mode", "preset", "format"),
        )
        try:
            svg = bilibili_service.build_share_card_svg(
                normalized_input,
            )
            image_bytes, media_type = share_card_renderer(
                svg,
                mode=mode,
                png_preset=preset,
                legacy_format=format,
            )
            return Response(content=image_bytes, media_type=media_type)
        except InvalidBilibiliUrlError as error:
            raise HTTPException(status_code=400, detail=error.message) from error
        except BilibiliExtractionError as error:
            raise HTTPException(status_code=502, detail=error.message) from error
        except ShareCardRenderError as error:
            raise HTTPException(status_code=502, detail=error.message) from error

    @app.get(
        "/api/v1/douyin/share-card",
        tags=["Share Card"],
        summary="Render Douyin Share Card",
        description="Render a horizontal Douyin share card as SVG or PNG. PNG mode supports performance, balanced, and quality presets.",
        responses={200: build_image_example_response()},
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
        mode: str | None = Query(
            None,
            description="Share-card output mode. Defaults to png when omitted",
            pattern="^(svg|png)$",
        ),
        preset: str = Query(
            "balanced",
            description="PNG render preset. Only used when mode=png",
            pattern="^(performance|balanced|quality)$",
        ),
        format: str | None = Query(
            None,
            description="Deprecated legacy share-card format alias",
            pattern="^(svg|png|jpg|jpeg)$",
            deprecated=True,
        ),
    ) -> Response:
        normalized_input = resolve_request_url_input(
            request,
            url,
            ignored_suffix_params=("mode", "preset", "format"),
        )
        try:
            svg = douyin_service.build_share_card_svg(
                normalized_input,
            )
            image_bytes, media_type = share_card_renderer(
                svg,
                mode=mode,
                png_preset=preset,
                legacy_format=format,
            )
            return Response(content=image_bytes, media_type=media_type)
        except InvalidDouyinUrlError as error:
            raise HTTPException(status_code=400, detail=error.message) from error
        except DouyinExtractionError as error:
            raise HTTPException(status_code=502, detail=error.message) from error
        except ShareCardRenderError as error:
            raise HTTPException(status_code=502, detail=error.message) from error


def resolve_request_url_input(
    request: Request,
    url: str | None,
    ignored_suffix_params: tuple[str, ...] = (),
) -> str:
    raw_query = request.scope.get("query_string", b"").decode("utf-8", errors="ignore")
    if "url=" in raw_query:
        raw_value = raw_query.split("url=", 1)[1]
        stripped_suffix = True
        while stripped_suffix:
            stripped_suffix = False
            for param_name in ignored_suffix_params:
                param_value = request.query_params.get(param_name)
                if param_value is None:
                    continue
                suffix_candidates = (
                    f"&{param_name}={quote_plus(param_value)}",
                    f"&{param_name}={param_value}",
                )
                for suffix in suffix_candidates:
                    if raw_value.endswith(suffix):
                        raw_value = raw_value[: -len(suffix)]
                        stripped_suffix = True
                        break
                if stripped_suffix:
                    break
        return unquote_plus(raw_value).strip()
    return (url or "").strip()


def resolve_video_service(
    url: str,
    bilibili_service: BilibiliParserService,
    douyin_service: DouyinParserService,
) -> VideoService:
    if bilibili_service.supports_url(url):
        return bilibili_service
    if douyin_service.supports_url(url):
        return douyin_service
    raise HTTPException(status_code=400, detail="Only Bilibili and Douyin video links are supported")


def run_platform_analysis(
    service: VideoService,
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


app = create_app()
