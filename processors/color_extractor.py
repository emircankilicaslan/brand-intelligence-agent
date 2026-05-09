from __future__ import annotations

import colorsys
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans

from agent.logging_setup import get_logger
from agent.models import ColorSwatch

logger = get_logger(__name__)

COLOR_NAMES = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "off-white": (245, 240, 235),
    "cream": (255, 253, 220),
    "beige": (245, 225, 200),
    "sand": (220, 195, 160),
    "camel": (190, 140, 80),
    "tan": (210, 180, 140),
    "brown": (139, 90, 43),
    "chocolate": (80, 40, 20),
    "red": (200, 30, 30),
    "burgundy": (130, 20, 40),
    "coral": (240, 120, 100),
    "orange": (230, 120, 30),
    "mustard": (210, 170, 30),
    "yellow": (240, 220, 30),
    "olive": (110, 110, 30),
    "khaki": (190, 185, 110),
    "sage": (150, 175, 130),
    "green": (50, 140, 60),
    "forest": (30, 90, 40),
    "teal": (40, 140, 140),
    "mint": (180, 230, 210),
    "sky blue": (135, 195, 225),
    "light blue": (170, 210, 240),
    "blue": (40, 90, 200),
    "navy": (20, 30, 100),
    "cobalt": (0, 70, 200),
    "lavender": (200, 180, 230),
    "lilac": (190, 160, 210),
    "purple": (100, 40, 160),
    "pink": (240, 170, 190),
    "blush": (250, 210, 210),
    "dusty rose": (210, 160, 160),
    "grey": (130, 130, 130),
    "light grey": (200, 200, 200),
    "charcoal": (70, 70, 70),
    "silver": (192, 192, 192),
    "gold": (212, 175, 55),
}


def _nearest_color_name(r: int, g: int, b: int) -> str:
    best_name = "unknown"
    best_dist = float("inf")
    for name, (nr, ng, nb) in COLOR_NAMES.items():
        dist = ((r - nr) ** 2 + (g - ng) ** 2 + (b - nb) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best_name = name
    return best_name


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def _is_near_white_or_black(r: int, g: int, b: int) -> bool:
    if r > 240 and g > 240 and b > 240:
        return True
    if r < 15 and g < 15 and b < 15:
        return True
    return False


def extract_palette(image_paths: list[str], n_colors: int = 8) -> list[ColorSwatch]:
    all_pixels: list[np.ndarray] = []

    for path in image_paths[:40]:
        try:
            with Image.open(path) as img:
                img_rgb = img.convert("RGB").resize((100, 100), Image.LANCZOS)
                arr = np.array(img_rgb).reshape(-1, 3)
                mask = ~np.apply_along_axis(lambda p: _is_near_white_or_black(*p), 1, arr)
                filtered = arr[mask]
                if len(filtered) > 0:
                    all_pixels.append(filtered)
        except Exception as exc:
            logger.debug("palette_read_failed", path=path, error=str(exc))

    if not all_pixels:
        logger.warning("no_pixels_for_palette")
        return []

    pixels = np.vstack(all_pixels)
    sample_size = min(50000, len(pixels))
    idx = np.random.choice(len(pixels), sample_size, replace=False)
    sample = pixels[idx]

    try:
        km = KMeans(n_clusters=n_colors, n_init=10, random_state=42)
        km.fit(sample)
        centers = km.cluster_centers_.astype(int)
        labels = km.labels_
        counts = np.bincount(labels)
        total = counts.sum()

        swatches = []
        for i, center in enumerate(centers):
            r, g, b = int(center[0]), int(center[1]), int(center[2])
            swatches.append(
                ColorSwatch(
                    hex=_rgb_to_hex(r, g, b),
                    rgb=(r, g, b),
                    frequency=round(float(counts[i]) / total, 4),
                    name=_nearest_color_name(r, g, b),
                )
            )

        swatches.sort(key=lambda s: -s.frequency)
        logger.info("palette_extracted", colors=len(swatches))
        return swatches

    except Exception as exc:
        logger.error("palette_extraction_failed", error=str(exc))
        return []
