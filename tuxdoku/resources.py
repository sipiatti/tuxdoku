"""Loading bundled fonts and images (works from a source tree, wheel or .deb)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pygame

ASSETS = Path(__file__).resolve().parent / "assets"

FONT_FILES = {"medium": "Baloo2-Medium.ttf", "bold": "Baloo2-Bold.ttf", "black": "Baloo2-ExtraBold.ttf"}


@lru_cache(maxsize=None)
def font(size: int, weight: str = "bold") -> pygame.font.Font:
    path = ASSETS / "fonts" / FONT_FILES[weight]
    try:
        return pygame.font.Font(str(path), size)
    except (OSError, FileNotFoundError):
        return pygame.font.SysFont("sans", size, bold=weight != "medium")


@lru_cache(maxsize=None)
def _raw_image(rel: str) -> pygame.Surface:
    surf = pygame.image.load(str(ASSETS / rel))
    return surf.convert_alpha() if pygame.display.get_surface() else surf


@lru_cache(maxsize=512)
def image(rel: str, size: int | None = None) -> pygame.Surface:
    """Image from assets, optionally smooth-scaled to a square of ``size`` px."""
    surf = _raw_image(rel)
    if size is None:
        return surf
    size = max(1, int(size))
    return pygame.transform.smoothscale(surf, (size, size))


def icon_path() -> Path:
    return ASSETS / "icons" / "tuxdoku.png"
