from main.core.branding import PROJECT_NAME


BILIBILI_VIDEO_ANALYSIS_EXAMPLES = {
    "bilibili_source_file": {
        "summary": "Bilibili source file",
        "value": {
            "product": PROJECT_NAME,
            "platform": "bilibili",
            "input_url": "https://www.bilibili.com/video/BV1xx411c7mu",
            "canonical_url": "https://www.bilibili.com/video/BV1xx411c7mu",
            "video_id": "BV1xx411c7mu",
            "title": "Example Bilibili video",
            "description": "Public video metadata extracted from Bilibili.",
            "declaration": None,
            "duration_seconds": 291.0,
            "published_at": "2026-06-05T10:05:28Z",
            "author": {
                "name": "Example Bilibili Creator",
                "unique_id": "946974",
                "sec_uid": None,
                "profile_url": "https://space.bilibili.com/946974",
                "avatar_url": "https://example.com/avatar.jpg",
                "signature": "Example public creator signature.",
                "follower_count": 4200000,
                "total_favorited": None,
                "verification": {
                    "is_verified": True,
                    "theme": "blue",
                    "text": "bilibili机构认证 Example official verification",
                },
            },
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
                "audio_url": None,
                "format_id": "html5-durl-64",
                "quality": "720P",
                "container": "mp4",
                "width": 1280,
                "height": 720,
                "fps": None,
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
            "product": PROJECT_NAME,
            "platform": "douyin",
            "input_url": "https://www.iesdouyin.com/share/video/7606942757253803610/",
            "canonical_url": "https://www.douyin.com/video/7606942757253803610",
            "video_id": "7606942757253803610",
            "title": "Example Douyin video",
            "description": "Public video metadata extracted from Douyin.",
            "declaration": "Platform-provided declaration when available.",
            "duration_seconds": 17.267,
            "published_at": "2026-02-18T13:00:00Z",
            "author": {
                "name": "Example Douyin Creator",
                "unique_id": "1234567890",
                "sec_uid": "MS4wLjABAAAAexample-sec-uid",
                "profile_url": "https://www.douyin.com/user/MS4wLjABAAAAexample-sec-uid",
                "avatar_url": "https://example.com/avatar.jpeg",
                "signature": "Example public creator signature.",
                "follower_count": 1147000,
                "total_favorited": 83954608,
                "verification": {
                    "is_verified": True,
                    "theme": "red",
                    "text": "Example official verification",
                },
            },
            "metrics": {
                "play_count": None,
                "danmaku_count": None,
                "comment_count": 238,
                "like_count": 7171,
                "share_count": 159,
                "favorite_count": 255,
                "coin_count": None,
            },
            "video_source": {
                "url": "https://example.com/video.mp4",
                "request_headers": None,
                "source_mode": "single_file",
                "audio_url": None,
                "format_id": "douyin-play",
                "quality": "720p",
                "container": "mp4",
                "width": 2160,
                "height": 3840,
                "fps": None,
            },
            "cover_source": {"url": "https://example.com/cover.jpeg", "request_headers": None},
        },
    }
}


def build_json_example_response(examples: dict[str, object]) -> dict[str, object]:
    return {
        "description": "Successful Response",
        "content": {"application/json": {"examples": examples}},
    }


def build_image_example_response() -> dict[str, object]:
    return {
        "description": "Share card image or SVG",
        "content": {
            "image/svg+xml": {"schema": {"type": "string", "format": "binary"}},
            "image/png": {"schema": {"type": "string", "format": "binary"}},
        },
    }
