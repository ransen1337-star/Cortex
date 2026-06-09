import unittest
from unittest.mock import patch

import httpx

from main.services.share_card import fetch_remote_image_data_uri


class StubImageResponse:
    def __init__(self, content: bytes, media_type: str) -> None:
        self.content = content
        self.headers = {"content-type": media_type}

    def raise_for_status(self) -> None:
        return None


class ShareCardTests(unittest.TestCase):
    def tearDown(self) -> None:
        fetch_remote_image_data_uri.cache_clear()

    def test_fetch_remote_image_data_uri_embeds_remote_images_as_data_uris(self) -> None:
        with patch(
            "main.services.share_card.HTTP_CLIENT.get",
            return_value=StubImageResponse(b"png-bytes", "image/png"),
        ):
            data_uri = fetch_remote_image_data_uri("https://example.com/avatar.png")

        self.assertIsNotNone(data_uri)
        assert data_uri is not None
        self.assertTrue(data_uri.startswith("data:image/png;base64,"))

    def test_fetch_remote_image_data_uri_falls_back_to_proxy_url_when_fetch_fails(self) -> None:
        with patch(
            "main.services.share_card.HTTP_CLIENT.get",
            side_effect=httpx.HTTPError("boom"),
        ):
            fallback_uri = fetch_remote_image_data_uri(
                "https://example.com/cover.jpg",
                asset_proxy_path="/api/v1/share-card/assets",
            )

        self.assertEqual(
            fallback_uri,
            "/api/v1/share-card/assets?url=https%3A%2F%2Fexample.com%2Fcover.jpg",
        )
