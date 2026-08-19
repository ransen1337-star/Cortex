from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from threading import Lock
from time import perf_counter
from typing import Literal

if sys.platform == "darwin":
    cairo_library_paths = [
        path
        for path in ("/opt/homebrew/opt/cairo/lib", "/usr/local/opt/cairo/lib")
        if Path(path).exists()
    ]
    if cairo_library_paths:
        existing_cairo_paths = os.getenv("DYLD_LIBRARY_PATH", "")
        os.environ["DYLD_LIBRARY_PATH"] = ":".join((*cairo_library_paths, existing_cairo_paths))

import cairosvg
from PIL import Image


SHARE_CARD_IMAGE_WIDTH = 1200
SHARE_CARD_IMAGE_HEIGHT = 630
DEFAULT_SHARE_CARD_OUTPUT_MODE = "png"
DEFAULT_SHARE_CARD_PNG_PRESET = "balanced"
DEFAULT_SHARE_CARD_JPEG_QUALITY = 82
PNG_RESAMPLE_FILTER = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS
DEFAULT_SHARE_CARD_MAX_CONCURRENCY = max(4, min(16, (os.cpu_count() or 1) * 2))


@dataclass(frozen=True)
class ShareCardPngPreset:
    render_scale_factor: float
    compress_level: int
    optimize: bool
    virtual_time_budget_ms: int


SHARE_CARD_PNG_PRESETS: dict[str, ShareCardPngPreset] = {
    "performance": ShareCardPngPreset(
        render_scale_factor=1.0,
        compress_level=1,
        optimize=False,
        virtual_time_budget_ms=250,
    ),
    "balanced": ShareCardPngPreset(
        render_scale_factor=1.5,
        compress_level=6,
        optimize=True,
        virtual_time_budget_ms=500,
    ),
    "quality": ShareCardPngPreset(
        render_scale_factor=2.0,
        compress_level=8,
        optimize=True,
        virtual_time_budget_ms=800,
    ),
}


class ShareCardRenderError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class ShareCardRenderMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._active = 0
        self._peak_active = 0
        self._completed = 0
        self._failed = 0
        self._durations_ms: list[float] = []
        self._queue_durations_ms: list[float] = []

    def begin(self) -> None:
        with self._lock:
            self._active += 1
            self._peak_active = max(self._peak_active, self._active)

    def finish(self, *, duration_ms: float, queue_duration_ms: float, succeeded: bool) -> None:
        with self._lock:
            self._active = max(0, self._active - 1)
            self._completed += 1
            if not succeeded:
                self._failed += 1
            self._durations_ms.append(duration_ms)
            self._queue_durations_ms.append(queue_duration_ms)
            del self._durations_ms[:-500]
            del self._queue_durations_ms[:-500]

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "renderer_mode": resolve_share_card_renderer(),
                "gpu_requested": is_share_card_gpu_enabled(),
                "concurrency_limit": resolve_share_card_max_concurrency(),
                "active_renders": self._active,
                "peak_concurrent_renders": self._peak_active,
                "completed_renders": self._completed,
                "failed_renders": self._failed,
                "render_time_ms": summarize_durations(self._durations_ms),
                "queue_time_ms": summarize_durations(self._queue_durations_ms),
            }


def summarize_durations(durations: list[float]) -> dict[str, float | int | None]:
    if not durations:
        return {"samples": 0, "min": None, "max": None, "average": None, "last": None}
    return {
        "samples": len(durations),
        "min": round(min(durations), 2),
        "max": round(max(durations), 2),
        "average": round(sum(durations) / len(durations), 2),
        "last": round(durations[-1], 2),
    }


def is_share_card_gpu_enabled() -> bool:
    return (os.getenv("CORTEX_SHARE_CARD_GPU") or "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_share_card_renderer() -> Literal["cairosvg", "chromium"]:
    configured = (os.getenv("CORTEX_SHARE_CARD_RENDERER") or "auto").strip().lower()
    if configured == "cairosvg":
        return "cairosvg"
    if configured == "chromium" or is_share_card_gpu_enabled():
        return "chromium"
    return "cairosvg"


def resolve_share_card_max_concurrency() -> int:
    configured = (os.getenv("CORTEX_SHARE_CARD_MAX_CONCURRENCY") or "").strip()
    try:
        return max(1, min(int(configured), 32)) if configured else DEFAULT_SHARE_CARD_MAX_CONCURRENCY
    except ValueError:
        return DEFAULT_SHARE_CARD_MAX_CONCURRENCY


RENDER_METRICS = ShareCardRenderMetrics()
RENDER_SEMAPHORE = BoundedSemaphore(resolve_share_card_max_concurrency())


def normalize_share_card_output_mode(mode: str | None) -> Literal["svg", "png"]:
    normalized = (mode or DEFAULT_SHARE_CARD_OUTPUT_MODE).strip().lower()
    if normalized in {"svg", "png"}:
        return normalized
    raise ShareCardRenderError("Only svg and png share-card modes are supported")


def normalize_share_card_png_preset(png_preset: str | None) -> Literal["performance", "balanced", "quality"]:
    normalized = (png_preset or DEFAULT_SHARE_CARD_PNG_PRESET).strip().lower()
    if normalized in SHARE_CARD_PNG_PRESETS:
        return normalized  # type: ignore[return-value]
    raise ShareCardRenderError("Only performance, balanced, and quality PNG presets are supported")


def normalize_share_card_legacy_format(image_format: str | None) -> Literal["svg", "png", "jpeg"] | None:
    normalized = (image_format or "").strip().lower()
    if not normalized:
        return None
    if normalized in {"svg", "png"}:
        return normalized  # type: ignore[return-value]
    if normalized in {"jpg", "jpeg"}:
        return "jpeg"
    raise ShareCardRenderError("Only svg, png, and jpg share-card formats are supported")


def resolve_share_card_png_preset(png_preset: str | None) -> ShareCardPngPreset:
    normalized_preset = normalize_share_card_png_preset(png_preset)
    return SHARE_CARD_PNG_PRESETS[normalized_preset]


def render_share_card_image(
    svg: str,
    mode: str | None = None,
    *,
    png_preset: str | None = None,
    legacy_format: str | None = None,
    jpeg_quality: int = DEFAULT_SHARE_CARD_JPEG_QUALITY,
) -> tuple[bytes, str]:
    normalized_mode = normalize_share_card_output_mode(mode) if mode is not None else None
    normalized_legacy_format = (
        normalize_share_card_legacy_format(legacy_format) if normalized_mode is None else None
    )

    if normalized_mode is None and normalized_legacy_format == "svg":
        return render_share_card_svg_bytes(svg), "image/svg+xml"

    if normalized_mode is None and normalized_legacy_format == "jpeg":
        png_bytes = render_share_card_png_bytes(svg, png_preset=png_preset)
        return convert_png_to_jpeg_bytes(png_bytes, jpeg_quality=jpeg_quality), "image/jpeg"

    effective_mode = normalized_mode or normalized_legacy_format or DEFAULT_SHARE_CARD_OUTPUT_MODE
    if effective_mode == "svg":
        return render_share_card_svg_bytes(svg), "image/svg+xml"
    return render_share_card_png_bytes(svg, png_preset=png_preset), "image/png"


def render_share_card_svg_bytes(svg: str) -> bytes:
    return svg.encode("utf-8")


def render_share_card_png_bytes(svg: str, *, png_preset: str | None = None) -> bytes:
    requested_at = perf_counter()
    with RENDER_SEMAPHORE:
        queue_duration_ms = (perf_counter() - requested_at) * 1000
        RENDER_METRICS.begin()
        render_started_at = perf_counter()
        succeeded = False
        try:
            preset = resolve_share_card_png_preset(png_preset)
            png_bytes = render_svg_to_png_bytes(svg, preset)
            finalized_png_bytes = finalize_png_bytes(png_bytes, preset)
            succeeded = True
            return finalized_png_bytes
        finally:
            RENDER_METRICS.finish(
                duration_ms=(perf_counter() - render_started_at) * 1000,
                queue_duration_ms=queue_duration_ms,
                succeeded=succeeded,
            )


def render_svg_to_png_bytes(svg: str, preset: ShareCardPngPreset) -> bytes:
    renderer = resolve_share_card_renderer()
    if renderer == "cairosvg":
        try:
            return render_svg_with_cairosvg(svg, preset)
        except Exception as error:
            raise ShareCardRenderError("Unable to render share card image with CairoSVG") from error
    browser_path = resolve_share_card_browser_path()
    return render_svg_with_chromium(svg, browser_path, preset)


def render_svg_with_cairosvg(svg: str, preset: ShareCardPngPreset) -> bytes:
    output_width = round(SHARE_CARD_IMAGE_WIDTH * preset.render_scale_factor)
    output_height = round(SHARE_CARD_IMAGE_HEIGHT * preset.render_scale_factor)
    return cairosvg.svg2png(
        bytestring=svg.encode("utf-8"),
        output_width=output_width,
        output_height=output_height,
    )


def render_svg_with_chromium(svg: str, browser_path: str, preset: ShareCardPngPreset) -> bytes:
    with TemporaryDirectory(prefix="cortex-share-card-") as temp_dir:
        temp_path = Path(temp_dir)
        svg_path = temp_path / "card.svg"
        png_path = temp_path / "card.png"
        svg_path.write_text(svg, encoding="utf-8")
        command = [
            browser_path,
            "--headless",
            "--hide-scrollbars",
            "--default-background-color=00000000",
            f"--virtual-time-budget={preset.virtual_time_budget_ms}",
            f"--force-device-scale-factor={preset.render_scale_factor}",
            f"--window-size={SHARE_CARD_IMAGE_WIDTH},{SHARE_CARD_IMAGE_HEIGHT}",
            f"--screenshot={png_path}",
            svg_path.as_uri(),
        ]
        if is_share_card_gpu_enabled():
            command.extend(["--enable-gpu-rasterization", "--ignore-gpu-blocklist"])
        else:
            command.append("--disable-gpu")
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise ShareCardRenderError("Unable to render share card image") from error
        if not png_path.exists():
            raise ShareCardRenderError("Unable to render share card image")
        return png_path.read_bytes()


def finalize_png_bytes(png_bytes: bytes, preset: ShareCardPngPreset) -> bytes:
    with Image.open(BytesIO(png_bytes)) as image_file:
        image = image_file.convert("RGBA")
    if image.size != (SHARE_CARD_IMAGE_WIDTH, SHARE_CARD_IMAGE_HEIGHT):
        image = image.resize(
            (SHARE_CARD_IMAGE_WIDTH, SHARE_CARD_IMAGE_HEIGHT),
            resample=PNG_RESAMPLE_FILTER,
        )
    buffer = BytesIO()
    save_kwargs: dict[str, object] = {
        "format": "PNG",
        "compress_level": preset.compress_level,
    }
    if preset.optimize:
        save_kwargs["optimize"] = True
    image.save(buffer, **save_kwargs)
    return buffer.getvalue()


def convert_png_to_jpeg_bytes(png_bytes: bytes, *, jpeg_quality: int) -> bytes:
    image = Image.open(BytesIO(png_bytes)).convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    flattened = Image.alpha_composite(background, image).convert("RGB")
    buffer = BytesIO()
    flattened.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    return buffer.getvalue()


def resolve_share_card_browser_path() -> str:
    configured_path = (os.getenv("CORTEX_SHARE_CARD_BROWSER") or "").strip()
    if configured_path:
        if Path(configured_path).exists():
            return configured_path
        discovered_path = shutil.which(configured_path)
        if discovered_path:
            return discovered_path

    executable_candidates = [
        "chrome",
        "chrome.exe",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "msedge",
        "msedge.exe",
    ]
    for candidate in executable_candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    static_candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ]
    for candidate in static_candidates:
        if candidate.exists():
            return str(candidate)

    edge_webview_root = Path(r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application")
    if edge_webview_root.exists():
        matches = sorted(edge_webview_root.glob(r"*\msedge.exe"))
        if matches:
            return str(matches[-1])

    raise ShareCardRenderError("No compatible browser was found for share-card rendering")


def get_share_card_render_metrics() -> dict[str, object]:
    return RENDER_METRICS.snapshot()
