from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from main.services.models import GithubRepositoryResponse
from main.services.models import GithubRateLimitResponse
from main.services.share_card import ShareCardAuthor
from main.services.share_card import ShareCardBranding
from main.services.share_card import ShareCardData
from main.services.share_card import ShareCardMetric
from main.services.share_card import ShareCardSidebar
from main.services.share_card import ShareCardSidebarContributor
from main.services.share_card import ShareCardSidebarLanguage
from main.services.share_card import render_share_card_svg
from main.services.utils import create_http_client


GITHUB_API_BASE = "https://api.github.com"
GITHUB_HOSTS = {"github.com", "www.github.com"}
GITHUB_URL_PATTERN = re.compile(r"https?://(?:www\.)?github\.com/[^\s<>'\"）)】]+", re.IGNORECASE)
TRAILING_URL_PUNCTUATION = ".,;!?，。；！？、)]）】>"
HTTP_CLIENT = create_http_client(20)


class GithubExtractionError(Exception):
    def __init__(self, message: str = "Unable to load this GitHub repository right now") -> None:
        self.message = message
        super().__init__(message)


class InvalidGithubUrlError(GithubExtractionError):
    pass


@dataclass(frozen=True)
class GithubRepository:
    owner: str
    name: str
    full_name: str
    description: str | None
    html_url: str
    avatar_url: str | None
    language: str | None
    languages: tuple[str, ...]
    contributor_count: int | None
    contributors: tuple[tuple[str, str | None], ...]
    stars: int
    forks: int
    open_issues: int
    watchers: int
    license_name: str | None
    is_private: bool


class GithubParserService:
    def __init__(self, http_client: Any | None = None) -> None:
        self._http_client = http_client or HTTP_CLIENT

    def supports_url(self, url: str) -> bool:
        return extract_github_repository(url) is not None

    def parse(self, url: str) -> GithubRepositoryResponse:
        repository = self.fetch(url)
        return GithubRepositoryResponse(
            product="Cortex",
            platform="github",
            input_url=normalize_github_url(url),
            canonical_url=repository.html_url,
            repository_id=repository.full_name,
            owner=repository.owner,
            name=repository.name,
            description=repository.description,
            avatar_url=repository.avatar_url,
            language=repository.language,
            languages=list(repository.languages),
            contributor_count=repository.contributor_count,
            contributors=[name for name, _ in repository.contributors],
            stars=repository.stars,
            forks=repository.forks,
            open_issues=repository.open_issues,
            watchers=repository.watchers,
            license_name=repository.license_name,
            is_private=repository.is_private,
        )

    def get_rate_limit(self) -> GithubRateLimitResponse:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self._http_client.get(f"{GITHUB_API_BASE}/rate_limit", headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise GithubExtractionError("Unable to load GitHub API rate limit right now") from error
        resources = payload.get("resources") if isinstance(payload, dict) else None
        core = resources.get("core") if isinstance(resources, dict) else None
        if not isinstance(core, dict):
            raise GithubExtractionError("GitHub returned an invalid rate-limit response")
        reset_epoch = coerce_number(core.get("reset"))
        reset_at = datetime.fromtimestamp(reset_epoch, tz=UTC) if reset_epoch else None
        return GithubRateLimitResponse(
            product="Cortex",
            platform="github",
            authenticated=bool(token),
            limit=coerce_number(core.get("limit")),
            remaining=coerce_number(core.get("remaining")),
            reset_at=reset_at,
        )

    def fetch(self, url: str) -> GithubRepository:
        owner, name = extract_github_repository(url) or (None, None)
        if owner is None or name is None:
            raise InvalidGithubUrlError("Only public github.com repository links are supported")
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = os.getenv("GITHUB_TOKEN", "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self._http_client.get(f"{GITHUB_API_BASE}/repos/{owner}/{name}", headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise GithubExtractionError("Unable to load GitHub repository metadata right now") from error
        if not isinstance(payload, dict) or not payload.get("full_name"):
            raise GithubExtractionError("GitHub returned an invalid repository response")
        license_data = payload.get("license") if isinstance(payload.get("license"), dict) else {}
        languages = self.fetch_languages(owner, name, headers)
        contributor_count = self.fetch_contributor_count(owner, name, headers)
        contributors = self.fetch_contributors(owner, name, headers)
        return GithubRepository(
            owner=str(payload.get("owner", {}).get("login") or owner),
            name=str(payload.get("name") or name),
            full_name=str(payload.get("full_name") or f"{owner}/{name}"),
            description=coerce_text(payload.get("description")),
            html_url=str(payload.get("html_url") or f"https://github.com/{owner}/{name}"),
            avatar_url=coerce_text((payload.get("owner") or {}).get("avatar_url")),
            language=coerce_text(payload.get("language")),
            languages=languages,
            contributor_count=contributor_count,
            contributors=contributors,
            stars=coerce_number(payload.get("stargazers_count")),
            forks=coerce_number(payload.get("forks_count")),
            open_issues=coerce_number(payload.get("open_issues_count")),
            watchers=coerce_number(payload.get("subscribers_count")),
            license_name=coerce_text(license_data.get("spdx_id") or license_data.get("name")),
            is_private=bool(payload.get("private")),
        )

    def build_share_card_svg(self, url: str, *, style: str = "cortex", asset_proxy_path: str | None = None) -> str:
        normalized_style = (style or "cortex").strip().lower()
        if normalized_style != "cortex":
            raise InvalidGithubUrlError("GitHub share-card style must be cortex or official")
        repository = self.fetch(url)
        return render_share_card_svg(build_cortex_card_data(repository), asset_proxy_path=asset_proxy_path)

    def build_official_preview_url(self, url: str) -> str:
        owner, name = extract_github_repository(url) or (None, None)
        if owner is None or name is None:
            raise InvalidGithubUrlError("Only public github.com repository links are supported")
        return f"https://opengraph.githubassets.com/1/{owner}/{name}"

    def fetch_languages(self, owner: str, name: str, headers: dict[str, str]) -> tuple[str, ...]:
        try:
            response = self._http_client.get(f"{GITHUB_API_BASE}/repos/{owner}/{name}/languages", headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return ()
        if not isinstance(payload, dict):
            return ()
        return tuple(str(language) for language in payload if str(language).strip())

    def fetch_contributor_count(self, owner: str, name: str, headers: dict[str, str]) -> int | None:
        try:
            response = self._http_client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{name}/contributors?per_page=1&anon=true",
                headers=headers,
            )
            response.raise_for_status()
        except (httpx.HTTPError, ValueError):
            return None
        link_header = getattr(response, "headers", {}).get("link", "")
        last_page = re.search(r"[?&]page=(\d+)>;\s*rel=\"last\"", link_header)
        if last_page:
            return int(last_page.group(1))
        try:
            payload = response.json()
        except ValueError:
            return None
        return len(payload) if isinstance(payload, list) else None

    def fetch_contributors(self, owner: str, name: str, headers: dict[str, str]) -> tuple[tuple[str, str | None], ...]:
        try:
            response = self._http_client.get(
                f"{GITHUB_API_BASE}/repos/{owner}/{name}/contributors?per_page=3&anon=true",
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return ()
        if not isinstance(payload, list):
            return ()
        return tuple(
            (str(item.get("login") or item.get("name")), coerce_text(item.get("avatar_url")))
            for item in payload
            if isinstance(item, dict) and (item.get("login") or item.get("name"))
        )


def extract_github_repository(text: str) -> tuple[str, str] | None:
    value = text.strip()
    candidates = [value, *GITHUB_URL_PATTERN.findall(value)]
    for candidate in candidates:
        candidate = candidate.rstrip(TRAILING_URL_PUNCTUATION)
        try:
            parsed = urlparse(candidate)
        except ValueError:
            continue
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in GITHUB_HOSTS:
            continue
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2 or parts[0].lower() in {"api", "settings", "features", "marketplace", "search"}:
            continue
        owner, name = parts[0], parts[1]
        if name.endswith(".git"):
            name = name[:-4]
        if re.fullmatch(r"[A-Za-z0-9_.-]+", owner) and re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            return owner, name
    return None


def normalize_github_url(url: str) -> str:
    repository = extract_github_repository(url)
    if repository is None:
        raise InvalidGithubUrlError("Only public github.com repository links are supported")
    return f"https://github.com/{repository[0]}/{repository[1]}"


def build_cortex_card_data(repository: GithubRepository) -> ShareCardData:
    tags = list(repository.languages[:3])
    if repository.license_name and repository.license_name not in tags:
        tags.append(repository.license_name)
    return ShareCardData(
        title=repository.name,
        canonical_url=repository.html_url,
        cover_url=None,
        cover_layout="github",
        author=ShareCardAuthor(name=repository.owner, avatar_url=repository.avatar_url),
        tags=tags,
        primary_metrics=[
            ShareCardMetric(value=format_count(repository.stars), icon_svg=GITHUB_STAR_ICON),
            ShareCardMetric(value=format_count(repository.forks), icon_svg=GITHUB_FORK_ICON),
            ShareCardMetric(value=format_count(repository.open_issues), icon_svg=GITHUB_ISSUE_ICON),
        ],
        secondary_metrics=[
            ShareCardMetric(value=repository.name, label="repo"),
            ShareCardMetric(value=str(len(repository.languages)), label="languages"),
            ShareCardMetric(value=str(repository.contributor_count or "--"), label="contributors"),
        ],
        sidebar=ShareCardSidebar(
            title="Community",
            contributors=[
                ShareCardSidebarContributor(name=name, avatar_url=avatar_url)
                for name, avatar_url in repository.contributors
            ],
            contributor_count=repository.contributor_count,
            languages=[
                ShareCardSidebarLanguage(name=language, share=max(1, len(repository.languages) - index))
                for index, language in enumerate(repository.languages[:4])
            ],
        ),
        branding=ShareCardBranding(
            logo_svg=GITHUB_MARK_PATH,
            logo_view_box="0 0 24 24",
            logo_fill="#111827",
            logo_x=1080,
            logo_y=548,
        ),
    )


def coerce_text(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


def coerce_number(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def format_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}m".rstrip("0").rstrip(".")
    if value >= 1_000:
        return f"{value / 1_000:.1f}k".rstrip("0").rstrip(".")
    return str(value)


GITHUB_MARK_PATH = '<path fill="#111827" d="M12 .3a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.04c-3.34.73-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.23 1.84 1.23 1.07 1.83 2.8 1.3 3.49.99.11-.77.42-1.3.76-1.6-2.67-.3-5.47-1.34-5.47-5.94 0-1.31.47-2.38 1.24-3.22-.12-.3-.54-1.52.12-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.66 1.66.24 2.88.24 2.88.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.49 5.93.43.37.81 1.1.81 2.22v3.29c0 .32.22.7.83.58A12 12 0 0 0 12 .3"/>'
GITHUB_STAR_ICON = '<svg width="28" height="28" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="#9499A0" d="M12 .25a.75.75 0 0 1 .673.418l3.058 6.197 6.839.994a.75.75 0 0 1 .415 1.279l-4.948 4.823 1.168 6.811a.751.751 0 0 1-1.088.791L12 18.347l-6.117 3.216a.75.75 0 0 1-1.088-.79l1.168-6.812-4.948-4.823a.75.75 0 0 1 .416-1.28l6.838-.993L11.328.668A.75.75 0 0 1 12 .25Zm0 2.445L9.44 7.882a.75.75 0 0 1-.565.41l-5.725.832 4.143 4.038a.748.748 0 0 1 .215.664l-.978 5.702 5.121-2.692a.75.75 0 0 1 .698 0l5.12 2.692-.977-5.702a.748.748 0 0 1 .215-.664l4.143-4.038-5.725-.831a.75.75 0 0 1-.565-.41L12 2.694Z"/></svg>'
GITHUB_FORK_ICON = '<svg width="28" height="28" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="#9499A0" d="M8.75 19.25a3.25 3.25 0 1 1 6.5 0 3.25 3.25 0 0 1-6.5 0ZM15 4.75a3.25 3.25 0 1 1 6.5 0 3.25 3.25 0 0 1-6.5 0Zm-12.5 0a3.25 3.25 0 1 1 6.5 0 3.25 3.25 0 0 1-6.5 0ZM5.75 6.5a1.75 1.75 0 1 0-.001-3.501A1.75 1.75 0 0 0 5.75 6.5ZM12 21a1.75 1.75 0 1 0-.001-3.501A1.75 1.75 0 0 0 12 21Zm6.25-14.5a1.75 1.75 0 1 0-.001-3.501A1.75 1.75 0 0 0 18.25 6.5Z"/><path fill="#9499A0" d="M6.5 7.75v1A2.25 2.25 0 0 0 8.75 11h6.5a2.25 2.25 0 0 0 2.25-2.25v-1H19v1a3.75 3.75 0 0 1-3.75 3.75h-6.5A3.75 3.75 0 0 1 5 8.75v-1Z"/><path fill="#9499A0" d="M11.25 16.25v-5h1.5v5h-1.5Z"/></svg>'
GITHUB_ISSUE_ICON = '<svg width="28" height="28" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path fill="#9499A0" d="M12 1c6.075 0 11 4.925 11 11s-4.925 11-11 11S1 18.075 1 12 5.925 1 12 1ZM2.5 12a9.5 9.5 0 0 0 9.5 9.5 9.5 9.5 0 0 0 9.5-9.5A9.5 9.5 0 0 0 12 2.5 9.5 9.5 0 0 0 2.5 12Zm9.5 2a2 2 0 1 1-.001-3.999A2 2 0 0 1 12 14Z"/></svg>'
