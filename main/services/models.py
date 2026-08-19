from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VideoMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    play_count: int | None = Field(default=None, description="Video play count")
    danmaku_count: int | None = Field(default=None, description="Danmaku count when the platform provides it")
    comment_count: int | None = Field(default=None, description="Comment count")
    like_count: int | None = Field(default=None, description="Like count")
    share_count: int | None = Field(default=None, description="Share count")
    favorite_count: int | None = Field(default=None, description="Favorite or collect count")
    coin_count: int | None = Field(default=None, description="Coin count when the platform provides it")


class SourceFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str | None = Field(default=None, description="Direct source file url")
    request_headers: dict[str, str] | None = Field(default=None, description="Request headers required to access this source url")


class VideoSourceFile(SourceFile):
    model_config = ConfigDict(extra="forbid")

    source_mode: Literal["single_file", "separate_streams"] = Field(description="Whether the video source is a single playable file or a separated video stream")
    audio_url: str | None = Field(default=None, description="Direct audio source url when the source mode is separate_streams")
    format_id: str | None = Field(default=None, description="Platform-specific format id")
    quality: str | None = Field(default=None, description="Human-readable quality label")
    container: str | None = Field(default=None, description="Container format such as mp4 or m4s")
    width: int | None = Field(default=None, description="Video width in pixels")
    height: int | None = Field(default=None, description="Video height in pixels")
    fps: float | None = Field(default=None, description="Frames per second when available")


class VideoAuthorVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_verified: bool = Field(description="Whether the author has a public platform verification")
    theme: Literal["red", "blue", "gold", "gray"] | None = Field(default=None, description="Platform verification theme when available")
    text: str | None = Field(default=None, description="Human-readable verification text")


class VideoAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, description="Author display name")
    unique_id: str | None = Field(default=None, description="Platform author unique id or short id")
    sec_uid: str | None = Field(default=None, description="Platform author secure id when available")
    profile_url: str | None = Field(default=None, description="Public author profile url when available")
    avatar_url: str | None = Field(default=None, description="Author avatar url")
    signature: str | None = Field(default=None, description="Public author signature or bio")
    follower_count: int | None = Field(default=None, description="Public follower count when available")
    total_favorited: int | None = Field(default=None, description="Public total liked or favorited count when available")
    verification: VideoAuthorVerification | None = Field(default=None, description="Public platform verification details")


class VideoAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: Literal["Cortex"] = Field(description="Product name")
    platform: Literal["bilibili", "douyin"] = Field(description="Matched platform")
    input_url: str = Field(description="Normalized input url used for parsing")
    canonical_url: str = Field(description="Canonical platform video url")
    video_id: str = Field(description="Platform video id")
    title: str = Field(description="Video title")
    description: str | None = Field(default=None, description="Video description")
    declaration: str | None = Field(default=None, description="Platform-provided content declaration or risk label")
    duration_seconds: float | None = Field(default=None, description="Video duration in seconds")
    published_at: datetime | None = Field(default=None, description="Publish time in ISO 8601 format")
    author: VideoAuthor | None = Field(default=None, description="Public author information when available")
    metrics: VideoMetrics = Field(description="Video metrics")
    video_source: VideoSourceFile = Field(description="Direct video source information")
    cover_source: SourceFile = Field(description="Direct cover source information")


class GithubRepositoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: Literal["Cortex"] = Field(description="Product name")
    platform: Literal["github"] = Field(description="Matched platform")
    input_url: str = Field(description="Normalized repository URL used for parsing")
    canonical_url: str = Field(description="Canonical GitHub repository URL")
    repository_id: str = Field(description="Repository full name")
    owner: str
    name: str
    description: str | None = None
    avatar_url: str | None = None
    language: str | None = None
    languages: list[str] = Field(default_factory=list)
    contributor_count: int | None = None
    contributors: list[str] = Field(default_factory=list)
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    watchers: int = 0
    license_name: str | None = None
    is_private: bool = False


class GithubRateLimitResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: Literal["Cortex"] = Field(description="Product name")
    platform: Literal["github"] = Field(description="Matched platform")
    authenticated: bool = Field(description="Whether a GitHub token is configured")
    limit: int | None = Field(default=None, description="Current GitHub REST API request limit")
    remaining: int | None = Field(default=None, description="Remaining requests in the active GitHub REST API window")
    reset_at: datetime | None = Field(default=None, description="GitHub REST API reset time in ISO 8601 format")
