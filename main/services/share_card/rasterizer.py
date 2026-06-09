from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
from typing import Literal

from PIL import Image


SHARE_CARD_IMAGE_WIDTH = 1200
SHARE_CARD_IMAGE_HEIGHT = 630
DEFAULT_SHARE_CARD_OUTPUT_MODE = "png"
DEFAULT_SHARE_CARD_PNG_PRESET = "balanced"
DEFAULT_SHARE_CARD_JPEG_QUALITY = 82
PNG_RESAMPLE_FILTER = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS


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
        virtual_time_budget_ms=1800,
    ),
    "balanced": ShareCardPngPreset(
        render_scale_factor=1.5,
        compress_level=6,
        optimize=True,
        virtual_time_budget_ms=2800,
    ),
    "quality": ShareCardPngPreset(
        render_scale_factor=2.0,
        compress_level=8,
        optimize=True,
        virtual_time_budget_ms=4200,
    ),
}


class ShareCardRenderError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


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
    browser_path = resolve_share_card_browser_path()
    preset = resolve_share_card_png_preset(png_preset)
    png_bytes = render_svg_to_png_bytes(svg, browser_path, preset)
    return finalize_png_bytes(png_bytes, preset)


def render_svg_to_png_bytes(svg: str, browser_path: str, preset: ShareCardPngPreset) -> bytes:
    with TemporaryDirectory(prefix="cortex-share-card-") as temp_dir:
        temp_path = Path(temp_dir)
        svg_path = temp_path / "card.svg"
        png_path = temp_path / "card.png"
        svg_path.write_text(svg, encoding="utf-8")
        command = [
            browser_path,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            "--default-background-color=ffffffff",
            f"--virtual-time-budget={preset.virtual_time_budget_ms}",
            f"--force-device-scale-factor={preset.render_scale_factor}",
            f"--window-size={SHARE_CARD_IMAGE_WIDTH},{SHARE_CARD_IMAGE_HEIGHT}",
            f"--screenshot={png_path}",
            svg_path.as_uri(),
        ]
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
