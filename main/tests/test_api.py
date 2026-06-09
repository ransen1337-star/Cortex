from datetime import UTC
from datetime import datetime
import unittest

from fastapi.testclient import TestClient

from main.api.app import SHARE_CARD_ASSET_PROXY_PATH
from main.api.app import BILIBILI_ASSET_REFERER
from main.api.app import DOUYIN_ASSET_REFERER
from main.api.app import build_asset_proxy_request_headers
from main.api.app import create_default_asset_proxy_fetcher
from main.api.app import create_app
from main.services import BilibiliExtractionError
from main.services import InvalidBilibiliUrlError
from main.services import InvalidDouyinUrlError
from main.services import VideoAnalysisResponse
from main.services import VideoAuthor
from main.services import VideoAuthorVerification
from main.services import VideoMetrics
from main.services import VideoSourceFile
from main.services import SourceFile
from main.services.douyin import DouyinExtractionError


def build_bilibili_response() -> VideoAnalysisResponse:
    return VideoAnalysisResponse(
        product="Cortex",
        platform="bilibili",
        input_url="https://www.bilibili.com/video/BV15kVJzYE5N/",
        canonical_url="https://www.bilibili.com/video/BV15kVJzYE5N",
        video_id="BV15kVJzYE5N",
        title="Bilibili Sample",
        description="Bilibili sample description",
        duration_seconds=291.0,
        published_at=datetime(2026, 6, 5, 10, 5, 28, tzinfo=UTC),
        metrics=VideoMetrics(
            play_count=5030049,
            danmaku_count=6964,
            comment_count=23141,
            like_count=213529,
            share_count=17775,
            favorite_count=25971,
            coin_count=17036,
        ),
        video_source=VideoSourceFile(
            url="https://example.com/bilibili-video.mp4",
            request_headers={"User-Agent": "Mozilla/5.0"},
            source_mode="single_file",
            audio_url=None,
            format_id="html5-durl-64",
            quality="720P",
            container="mp4",
            width=1280,
            height=720,
            fps=None,
        ),
        cover_source=SourceFile(
            url="https://example.com/bilibili-cover.jpg",
            request_headers={"User-Agent": "Mozilla/5.0"},
        ),
    )


def build_douyin_response() -> VideoAnalysisResponse:
    return VideoAnalysisResponse(
        product="Cortex",
        platform="douyin",
        input_url="https://www.iesdouyin.com/share/video/7634486870264597775/",
        canonical_url="https://www.douyin.com/video/7634486870264597775",
        video_id="7634486870264597775",
        title="Douyin Sample",
        description="Douyin sample description",
        duration_seconds=17.267,
        published_at=datetime(2026, 2, 18, 13, 0, 0, tzinfo=UTC),
        author=VideoAuthor(
            name="Douyin Creator",
            unique_id="1234567890",
            sec_uid="MS4wLjABAAAAexample-sec-uid",
            profile_url="https://www.douyin.com/user/MS4wLjABAAAAexample-sec-uid",
            avatar_url="https://example.com/avatar.jpeg",
            signature="Example creator signature",
            follower_count=1147000,
            total_favorited=83954608,
            verification=VideoAuthorVerification(
                is_verified=True,
                theme="red",
                text="Example official verification",
            ),
        ),
        metrics=VideoMetrics(
            play_count=None,
            danmaku_count=None,
            comment_count=238,
            like_count=7171,
            share_count=159,
            favorite_count=255,
            coin_count=None,
        ),
        video_source=VideoSourceFile(
            url="https://example.com/douyin-video.mp4",
            request_headers=None,
            source_mode="single_file",
            audio_url=None,
            format_id="douyin-play",
            quality="720p",
            container="mp4",
            width=1080,
            height=1920,
            fps=None,
        ),
        cover_source=SourceFile(
            url="https://example.com/douyin-cover.jpeg",
            request_headers=None,
        ),
    )


class StubVideoService:
    def __init__(
        self,
        *,
        supported_url_fragments: tuple[str, ...] = (),
        response: VideoAnalysisResponse | None = None,
        parse_error: Exception | None = None,
        share_card_svg: str = "<svg>stub</svg>",
        share_card_error: Exception | None = None,
    ) -> None:
        self.supported_url_fragments = supported_url_fragments
        self.response = response
        self.parse_error = parse_error
        self.share_card_svg = share_card_svg
        self.share_card_error = share_card_error
        self.last_parsed_url: str | None = None
        self.last_share_card_url: str | None = None
        self.last_asset_proxy_path: str | None = None

    def supports_url(self, url: str) -> bool:
        return any(fragment in url for fragment in self.supported_url_fragments)

    def parse(self, url: str) -> VideoAnalysisResponse:
        self.last_parsed_url = url
        if self.parse_error is not None:
            raise self.parse_error
        if self.response is None:
            raise AssertionError("StubVideoService.response must be provided for successful parse tests")
        return self.response

    def build_share_card_svg(self, url: str, asset_proxy_path: str | None = None) -> str:
        self.last_share_card_url = url
        self.last_asset_proxy_path = asset_proxy_path
        if self.share_card_error is not None:
            raise self.share_card_error
        return self.share_card_svg


class StubUpstreamResponse:
    def __init__(self, *, content: bytes = b"asset-bytes", media_type: str = "image/png") -> None:
        self.content = content
        self.headers = {"content-type": media_type}

    def raise_for_status(self) -> None:
        return None


class StubAssetClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get(self, url: str, headers: dict[str, str]) -> StubUpstreamResponse:
        self.calls.append((url, headers))
        return StubUpstreamResponse(content=b"proxied-image", media_type="image/jpeg")


class ApiRouteTests(unittest.TestCase):
    def build_client(
        self,
        *,
        bilibili_service: StubVideoService | None = None,
        douyin_service: StubVideoService | None = None,
        asset_proxy_fetcher=None,
    ) -> TestClient:
        app = create_app(
            bilibili_service=bilibili_service or StubVideoService(response=build_bilibili_response()),
            douyin_service=douyin_service or StubVideoService(response=build_douyin_response()),
            asset_proxy_fetcher=asset_proxy_fetcher,
        )
        return TestClient(app)

    def test_root_redirects_to_docs(self) -> None:
        client = self.build_client()
        response = client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/docs")

    def test_openapi_returns_cortex_metadata(self) -> None:
        client = self.build_client()
        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["info"]["title"], "Cortex")
        self.assertEqual(payload["info"]["version"], "0.4.0")
        self.assertIn("/api/v1/bilibili/video-analysis", payload["paths"])
        self.assertIn("/api/v1/douyin/share-card", payload["paths"])

    def test_docs_page_is_available(self) -> None:
        client = self.build_client()
        response = client.get("/docs")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Swagger UI", response.text)

    def test_health_returns_ok(self) -> None:
        client = self.build_client()
        response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_share_card_asset_requires_url_parameter(self) -> None:
        client = self.build_client()

        for path in (
            "/api/v1/video-analysis",
            "/api/v1/bilibili/video-analysis",
            "/api/v1/bilibili/parse",
            "/api/v1/douyin/video-analysis",
            "/api/v1/douyin/parse",
            "/api/v1/bilibili/share-card",
            "/api/v1/douyin/share-card",
            SHARE_CARD_ASSET_PROXY_PATH,
        ):
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 422)

    def test_share_card_asset_rejects_invalid_url(self) -> None:
        client = self.build_client()
        response = client.get(SHARE_CARD_ASSET_PROXY_PATH, params={"url": "javascript:alert(1)"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Invalid remote asset URL"})

    def test_share_card_asset_returns_proxied_content(self) -> None:
        seen_urls: list[str] = []

        def asset_proxy_fetcher(url: str) -> tuple[bytes, str]:
            seen_urls.append(url)
            return b"asset-bytes", "image/png"

        client = self.build_client(asset_proxy_fetcher=asset_proxy_fetcher)
        response = client.get(SHARE_CARD_ASSET_PROXY_PATH, params={"url": "https://example.com/logo.png"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"asset-bytes")
        self.assertEqual(response.headers["content-type"], "image/png")
        self.assertEqual(response.headers["cache-control"], "public, max-age=3600")
        self.assertEqual(seen_urls, ["https://example.com/logo.png"])

    def test_share_card_asset_returns_502_when_fetch_fails(self) -> None:
        def asset_proxy_fetcher(url: str) -> tuple[bytes, str]:
            raise RuntimeError(f"failed to fetch {url}")

        client = self.build_client(asset_proxy_fetcher=asset_proxy_fetcher)
        response = client.get(SHARE_CARD_ASSET_PROXY_PATH, params={"url": "https://example.com/logo.png"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Unable to load share-card asset"})

    def test_build_asset_proxy_request_headers_adds_douyin_referer_for_douyin_assets(self) -> None:
        headers = build_asset_proxy_request_headers("https://p3.douyinpic.com/aweme/100x100/example.jpeg")

        self.assertEqual(headers["Referer"], DOUYIN_ASSET_REFERER)
        self.assertIn("image/", headers["Accept"])

    def test_build_asset_proxy_request_headers_adds_bilibili_referer_for_bilibili_assets(self) -> None:
        headers = build_asset_proxy_request_headers("https://i0.hdslb.com/bfs/archive/example.png")

        self.assertEqual(headers["Referer"], BILIBILI_ASSET_REFERER)
        self.assertIn("image/", headers["Accept"])

    def test_default_asset_proxy_fetcher_uses_site_aware_headers(self) -> None:
        asset_client = StubAssetClient()
        fetcher = create_default_asset_proxy_fetcher(asset_client=asset_client)

        content, media_type = fetcher("https://p3.douyinpic.com/aweme/100x100/example.jpeg")

        self.assertEqual(content, b"proxied-image")
        self.assertEqual(media_type, "image/jpeg")
        self.assertEqual(len(asset_client.calls), 1)
        _, headers = asset_client.calls[0]
        self.assertEqual(headers["Referer"], DOUYIN_ASSET_REFERER)

    def test_unified_analysis_uses_bilibili_service(self) -> None:
        bilibili_service = StubVideoService(
            supported_url_fragments=("bilibili.com",),
            response=build_bilibili_response(),
        )
        douyin_service = StubVideoService(
            supported_url_fragments=("iesdouyin.com",),
            response=build_douyin_response(),
        )
        client = self.build_client(
            bilibili_service=bilibili_service,
            douyin_service=douyin_service,
        )

        response = client.get("/api/v1/video-analysis", params={"url": "https://www.bilibili.com/video/BV15kVJzYE5N/"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["platform"], "bilibili")
        self.assertEqual(bilibili_service.last_parsed_url, "https://www.bilibili.com/video/BV15kVJzYE5N/")

    def test_unified_analysis_uses_douyin_service(self) -> None:
        bilibili_service = StubVideoService(
            supported_url_fragments=("bilibili.com",),
            response=build_bilibili_response(),
        )
        douyin_service = StubVideoService(
            supported_url_fragments=("iesdouyin.com",),
            response=build_douyin_response(),
        )
        client = self.build_client(
            bilibili_service=bilibili_service,
            douyin_service=douyin_service,
        )

        response = client.get("/api/v1/video-analysis", params={"url": "https://www.iesdouyin.com/share/video/7634486870264597775/"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["platform"], "douyin")
        self.assertEqual(douyin_service.last_parsed_url, "https://www.iesdouyin.com/share/video/7634486870264597775/")

    def test_unified_analysis_rejects_unsupported_url(self) -> None:
        client = self.build_client(
            bilibili_service=StubVideoService(supported_url_fragments=("bilibili.com",), response=build_bilibili_response()),
            douyin_service=StubVideoService(supported_url_fragments=("iesdouyin.com",), response=build_douyin_response()),
        )

        response = client.get("/api/v1/video-analysis", params={"url": "https://example.com/video/123"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Only Bilibili and Douyin video links are supported"})

    def test_platform_routes_preserve_full_raw_url_query_value(self) -> None:
        bilibili_service = StubVideoService(response=build_bilibili_response())
        client = self.build_client(bilibili_service=bilibili_service)

        response = client.get("/api/v1/bilibili/video-analysis?url=https://example.com/watch?v=1&list=2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(bilibili_service.last_parsed_url, "https://example.com/watch?v=1&list=2")

    def test_bilibili_video_analysis_success(self) -> None:
        client = self.build_client(
            bilibili_service=StubVideoService(response=build_bilibili_response()),
        )
        response = client.get("/api/v1/bilibili/video-analysis", params={"url": "https://www.bilibili.com/video/BV15kVJzYE5N/"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["platform"], "bilibili")
        self.assertEqual(payload["metrics"]["play_count"], 5030049)

    def test_bilibili_video_analysis_invalid_url_error_maps_to_400(self) -> None:
        client = self.build_client(
            bilibili_service=StubVideoService(parse_error=InvalidBilibiliUrlError("bad bilibili url")),
        )
        response = client.get("/api/v1/bilibili/video-analysis", params={"url": "bad"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "bad bilibili url"})

    def test_bilibili_video_analysis_extraction_error_maps_to_502(self) -> None:
        client = self.build_client(
            bilibili_service=StubVideoService(parse_error=BilibiliExtractionError("bilibili unavailable")),
        )
        response = client.get("/api/v1/bilibili/video-analysis", params={"url": "https://www.bilibili.com/video/BV15kVJzYE5N/"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "bilibili unavailable"})

    def test_bilibili_legacy_parse_route_returns_same_payload_shape(self) -> None:
        client = self.build_client(
            bilibili_service=StubVideoService(response=build_bilibili_response()),
        )
        response = client.get("/api/v1/bilibili/parse", params={"url": "https://www.bilibili.com/video/BV15kVJzYE5N/"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["video_id"], "BV15kVJzYE5N")

    def test_douyin_video_analysis_success(self) -> None:
        client = self.build_client(
            douyin_service=StubVideoService(response=build_douyin_response()),
        )
        response = client.get("/api/v1/douyin/video-analysis", params={"url": "https://www.iesdouyin.com/share/video/7634486870264597775/"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["platform"], "douyin")
        self.assertEqual(payload["author"]["verification"]["theme"], "red")

    def test_douyin_video_analysis_invalid_url_error_maps_to_400(self) -> None:
        client = self.build_client(
            douyin_service=StubVideoService(parse_error=InvalidDouyinUrlError("bad douyin url")),
        )
        response = client.get("/api/v1/douyin/video-analysis", params={"url": "bad"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "bad douyin url"})

    def test_douyin_video_analysis_extraction_error_maps_to_502(self) -> None:
        client = self.build_client(
            douyin_service=StubVideoService(parse_error=DouyinExtractionError("douyin unavailable")),
        )
        response = client.get("/api/v1/douyin/video-analysis", params={"url": "https://www.iesdouyin.com/share/video/7634486870264597775/"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "douyin unavailable"})

    def test_douyin_legacy_parse_route_returns_same_payload_shape(self) -> None:
        client = self.build_client(
            douyin_service=StubVideoService(response=build_douyin_response()),
        )
        response = client.get("/api/v1/douyin/parse", params={"url": "https://www.iesdouyin.com/share/video/7634486870264597775/"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["video_id"], "7634486870264597775")

    def test_bilibili_share_card_success(self) -> None:
        bilibili_service = StubVideoService(share_card_svg="<svg>bilibili</svg>")
        client = self.build_client(bilibili_service=bilibili_service)

        response = client.get("/api/v1/bilibili/share-card", params={"url": "https://www.bilibili.com/video/BV15kVJzYE5N/"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "<svg>bilibili</svg>")
        self.assertEqual(response.headers["content-type"], "image/svg+xml")
        self.assertEqual(bilibili_service.last_asset_proxy_path, SHARE_CARD_ASSET_PROXY_PATH)

    def test_bilibili_share_card_error_mapping(self) -> None:
        invalid_client = self.build_client(
            bilibili_service=StubVideoService(share_card_error=InvalidBilibiliUrlError("bad bilibili share url")),
        )
        invalid_response = invalid_client.get("/api/v1/bilibili/share-card", params={"url": "bad"})
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.json(), {"detail": "bad bilibili share url"})

        extraction_client = self.build_client(
            bilibili_service=StubVideoService(share_card_error=BilibiliExtractionError("bilibili share unavailable")),
        )
        extraction_response = extraction_client.get("/api/v1/bilibili/share-card", params={"url": "https://www.bilibili.com/video/BV15kVJzYE5N/"})
        self.assertEqual(extraction_response.status_code, 502)
        self.assertEqual(extraction_response.json(), {"detail": "bilibili share unavailable"})

    def test_douyin_share_card_success(self) -> None:
        douyin_service = StubVideoService(share_card_svg="<svg>douyin</svg>")
        client = self.build_client(douyin_service=douyin_service)

        response = client.get("/api/v1/douyin/share-card", params={"url": "https://www.iesdouyin.com/share/video/7634486870264597775/"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "<svg>douyin</svg>")
        self.assertEqual(response.headers["content-type"], "image/svg+xml")
        self.assertEqual(douyin_service.last_asset_proxy_path, SHARE_CARD_ASSET_PROXY_PATH)

    def test_douyin_share_card_error_mapping(self) -> None:
        invalid_client = self.build_client(
            douyin_service=StubVideoService(share_card_error=InvalidDouyinUrlError("bad douyin share url")),
        )
        invalid_response = invalid_client.get("/api/v1/douyin/share-card", params={"url": "bad"})
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.json(), {"detail": "bad douyin share url"})

        extraction_client = self.build_client(
            douyin_service=StubVideoService(share_card_error=DouyinExtractionError("douyin share unavailable")),
        )
        extraction_response = extraction_client.get("/api/v1/douyin/share-card", params={"url": "https://www.iesdouyin.com/share/video/7634486870264597775/"})
        self.assertEqual(extraction_response.status_code, 502)
        self.assertEqual(extraction_response.json(), {"detail": "douyin share unavailable"})


if __name__ == "__main__":
    unittest.main()
