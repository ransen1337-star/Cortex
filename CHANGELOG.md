# Changelog

All notable changes to Cortex are documented in this file.

## 1.1.0

### Added

- Public GitHub repository analysis with repository metrics, languages, license details, and contributor summaries.
- GitHub share cards in transparent Cortex style and GitHub's official OpenGraph image style.
- GitHub API rate-limit endpoint with authentication, remaining-budget, and reset-time information.
- CairoSVG PNG rendering, configurable Chromium GPU rendering, and process-local render concurrency metrics.

### Improved

- PNG output now preserves transparent corners and avoids starting a browser for the default renderer.
- HTTP clients tolerate malformed local proxy exclusions such as `NO_PROXY=::1`.

## 1.0.0

### Added

- Startup version checks against the remote `PROJECT_VERSION`.
- Clear terminal states for current, update available, local ahead, and unavailable version checks.
- A terminal changelog displayed after the startup version status.

## 0.5.0

### Added

- Bilibili and Douyin public video analysis endpoints with a shared API response model.
- SVG and PNG share-card rendering with performance, balanced, and quality PNG presets.
- Share-card asset proxying and configurable card font support.

### Improved

- URL normalization for public Bilibili and Douyin share links.
- Runtime configuration for the host and port used by the local service.
