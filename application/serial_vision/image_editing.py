from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps


class ImageEditSession:
    """Non-destructive operations on one photo for a recognition preview."""

    def __init__(self, source: Path) -> None:
        self.source = source
        with Image.open(source) as image:
            self._original = ImageOps.exif_transpose(image).convert("RGB")
        self._working = self._original.copy()
        self.brightness = 100
        self.contrast = 100
        self.color = 100
        self.sharpness = 100

    @property
    def size(self) -> tuple[int, int]:
        return self._working.size

    def reset(self) -> None:
        self._working = self._original.copy()
        self.brightness = self.contrast = self.color = self.sharpness = 100

    def rotate_clockwise(self) -> None:
        self._working = self._working.transpose(Image.Transpose.ROTATE_270)

    def rotate_degrees(self, degrees: int) -> None:
        if not -180 <= degrees <= 180:
            raise ValueError("editor_rotation_range")
        if degrees == 0:
            return
        width, height = self.size
        if abs(degrees) == 90:
            rotated_width, rotated_height = height, width
        elif abs(degrees) == 180:
            rotated_width, rotated_height = width, height
        else:
            radians = math.radians(degrees)
            rotated_width = math.ceil(
                abs(width * math.cos(radians)) + abs(height * math.sin(radians))
            )
            rotated_height = math.ceil(
                abs(width * math.sin(radians)) + abs(height * math.cos(radians))
            )
        if (
            rotated_width > 12000
            or rotated_height > 12000
            or rotated_width * rotated_height > 80_000_000
        ):
            raise ValueError("editor_rotation_invalid")
        if degrees == 90:
            self.rotate_clockwise()
        elif degrees == -90:
            self._working = self._working.transpose(Image.Transpose.ROTATE_90)
        elif abs(degrees) == 180:
            self._working = self._working.transpose(Image.Transpose.ROTATE_180)
        else:
            self._working = self._working.rotate(
                -degrees,
                resample=Image.Resampling.BICUBIC,
                expand=True,
                fillcolor=self._working.getpixel((0, 0)),
            )

    def crop(self, x: int, y: int, width: int, height: int) -> None:
        image_width, image_height = self.size
        if (
            x < 0
            or y < 0
            or width < 2
            or height < 2
            or x + width > image_width
            or y + height > image_height
        ):
            raise ValueError("editor_crop_invalid")
        self._working = self._working.crop((x, y, x + width, y + height))

    def resize(self, percent: int) -> None:
        if not 25 <= percent <= 300:
            raise ValueError("editor_resize_range")
        width = max(1, round(self.size[0] * percent / 100))
        height = max(1, round(self.size[1] * percent / 100))
        if width > 12000 or height > 12000 or width * height > 80_000_000:
            raise ValueError("editor_resize_invalid")
        self._working = self._working.resize((width, height), Image.Resampling.LANCZOS)

    def set_adjustments(
        self, *, brightness: int, contrast: int, color: int, sharpness: int
    ) -> None:
        values = (brightness, contrast, color, sharpness)
        if any(not 0 <= value <= 200 for value in values):
            raise ValueError("editor_adjustment_range")
        self.brightness, self.contrast, self.color, self.sharpness = values

    def _adjusted(self, image: Image.Image) -> Image.Image:
        for enhancer, value in (
            (ImageEnhance.Brightness, self.brightness),
            (ImageEnhance.Contrast, self.contrast),
            (ImageEnhance.Color, self.color),
            (ImageEnhance.Sharpness, self.sharpness),
        ):
            if value != 100:
                image = enhancer(image).enhance(value / 100)
        return image

    def preview_png(self, maximum_edge: int = 1600) -> tuple[bytes, tuple[int, int]]:
        image = self._working.copy()
        image.thumbnail((maximum_edge, maximum_edge), Image.Resampling.LANCZOS)
        image = self._adjusted(image)
        output = BytesIO()
        image.save(output, format="PNG")
        return output.getvalue(), image.size

    def save_snapshot(self, destination: Path) -> None:
        self._adjusted(self._working.copy()).save(destination, format="PNG")
