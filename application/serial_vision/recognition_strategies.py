"""Ordered, non-destructive image variants for local recognition."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

from PIL import Image, ImageFilter, ImageOps


@dataclass(frozen=True)
class RecognitionOptions:
    rotate: bool = True
    enhance: bool = True


class ImageStrategy(Protocol):
    def variants(self, image: Image.Image) -> Iterator[Image.Image]: ...


class OriginalStrategy:
    def variants(self, image: Image.Image) -> Iterator[Image.Image]:
        yield image


class RotationStrategy:
    def variants(self, image: Image.Image) -> Iterator[Image.Image]:
        for angle in (180, 90, 270):
            yield image.rotate(angle, expand=True)


class ClarityStrategy:
    def variants(self, image: Image.Image) -> Iterator[Image.Image]:
        gray = ImageOps.autocontrast(ImageOps.grayscale(image))
        yield gray.filter(ImageFilter.UnsharpMask(radius=1.2, percent=130, threshold=3))
        scale = min(2.0, 3000 / max(gray.size))
        if scale > 1.2:
            enlarged = gray.resize(
                (int(gray.width * scale), int(gray.height * scale)), Image.Resampling.LANCZOS
            )
            yield enlarged.filter(ImageFilter.UnsharpMask(radius=1.4, percent=125, threshold=3))


def normalized_image(image: Image.Image) -> Image.Image:
    return ImageOps.exif_transpose(image).convert("RGB")


def fallback_strategies(options: RecognitionOptions) -> tuple[ImageStrategy, ...]:
    strategies: list[ImageStrategy] = []
    if options.rotate:
        strategies.append(RotationStrategy())
    if options.enhance:
        strategies.append(ClarityStrategy())
    return tuple(strategies)
