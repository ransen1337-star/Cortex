import unittest

from main.services.douyin.parser import build_douyin_author
from main.services.douyin.parser import parse_public_count_text
from main.services.douyin.parser import resolve_author_avatar_url
from main.services.douyin.parser import resolve_douyin_play_count
from main.services.douyin.parser import resolve_douyin_verification


class DouyinParserTests(unittest.TestCase):
    def test_resolve_douyin_verification_uses_public_user_profile(self) -> None:
        verification = resolve_douyin_verification(
            author={"nickname": "抖音精选官方账号"},
            user_profile={
                "enterprise_verify_reason": "抖音精选官方账号",
                "account_cert_info": '{"label_style":5,"label_text":"抖音精选官方账号","is_biz_account":1}',
                "verification_type": 0,
            },
        )

        self.assertEqual(verification["theme"], "red")
        self.assertEqual(verification["text"], "抖音精选官方账号")

    def test_resolve_douyin_play_count_prefers_public_text_fallback(self) -> None:
        play_count = resolve_douyin_play_count(
            statistics={
                "play_count": 0,
                "digg_count": 12001,
                "comment_count": 649,
                "share_count": 496,
                "collect_count": 1400,
            },
            page_html='<meta name="description" content="该视频已播放 12.3万 次，欢迎观看" />',
        )

        self.assertEqual(play_count, 123000)

    def test_parse_public_count_text_supports_units(self) -> None:
        self.assertEqual(parse_public_count_text("12.3万"), 123000)
        self.assertEqual(parse_public_count_text("2亿"), 200000000)
        self.assertEqual(parse_public_count_text("1,234"), 1234)

    def test_resolve_douyin_play_count_returns_none_when_public_count_is_unavailable(self) -> None:
        play_count = resolve_douyin_play_count(
            statistics={
                "play_count": 0,
                "digg_count": 12001,
                "comment_count": 649,
                "share_count": 496,
                "collect_count": 1400,
            },
            page_html="<html><head><meta name=\"description\" content=\"仅展示公开视频信息\" /></head></html>",
        )

        self.assertIsNone(play_count)

    def test_build_douyin_author_uses_user_profile_fields(self) -> None:
        author = build_douyin_author(
            author={
                "nickname": "抖音精选官方账号",
                "sec_uid": "MS4wLjABAAAAexample",
                "unique_id": "48751955702",
            },
            user_profile={
                "signature": "官方邮箱：demo@example.com",
                "mplatform_followers_count": 1147000,
                "total_favorited": "83954608",
            },
            verification={"theme": "red", "text": "抖音精选官方账号"},
        )

        self.assertIsNotNone(author)
        assert author is not None
        self.assertEqual(author.profile_url, "https://www.douyin.com/user/MS4wLjABAAAAexample")
        self.assertEqual(author.follower_count, 1147000)
        self.assertEqual(author.total_favorited, 83954608)
        self.assertEqual(author.verification.text, "抖音精选官方账号")

    def test_resolve_author_avatar_url_prefers_faster_douyin_cdn_candidates(self) -> None:
        avatar_url = resolve_author_avatar_url(
            author={
                "avatar_medium": {
                    "url_list": [
                        "https://p3.douyinpic.com/aweme/100x100/example-avatar.jpeg",
                        "https://p11.douyinpic.com/aweme/100x100/example-avatar.jpeg",
                        "https://p26.douyinpic.com/aweme/100x100/example-avatar.jpeg",
                    ],
                }
            },
            user_profile=None,
        )

        self.assertEqual(avatar_url, "https://p11.douyinpic.com/aweme/100x100/example-avatar.jpeg")


if __name__ == "__main__":
    unittest.main()
