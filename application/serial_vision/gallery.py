from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps

from serial_vision.image_catalog import CatalogImage, ImageCatalog


@dataclass(frozen=True)
class GalleryItem:
    image: CatalogImage
    thumbnail: bytes


@dataclass(frozen=True)
class GalleryPage:
    items: tuple[GalleryItem, ...]
    page: int
    pages: int
    total: int


class ThumbnailCache:
    """Bounded PNG cache. Access is confined to one gallery worker at a time."""

    def __init__(self, capacity: int = 256, max_bytes: int = 16 * 1024 * 1024) -> None:
        self.capacity = max(1, capacity)
        self.max_bytes = max(1, max_bytes)
        self._items: OrderedDict[tuple[str, int, int], bytes] = OrderedDict()
        self.byte_count = 0

    def thumbnail(self, image: CatalogImage) -> bytes:
        key = (str(image.path), image.modified_ns, image.size)
        if key in self._items:
            self._items.move_to_end(key)
            return self._items[key]
        try:
            with Image.open(image.path) as source:
                source.thumbnail((300, 190), Image.Resampling.LANCZOS)
                preview = ImageOps.exif_transpose(source).convert("RGBA")
                output = BytesIO()
                preview.save(output, format="PNG")
                data = output.getvalue()
        except (OSError, ValueError, Image.DecompressionBombError):
            return b""
        if len(data) <= self.max_bytes:
            self._items[key] = data
            self.byte_count += len(data)
            while len(self._items) > self.capacity or self.byte_count > self.max_bytes:
                _, removed = self._items.popitem(last=False)
                self.byte_count -= len(removed)
        return data


def load_gallery_page(
    catalog: ImageCatalog,
    cache: ThumbnailCache,
    page: int,
    cancelled: Callable[[], bool] = lambda: False,
) -> GalleryPage:
    images, metadata = catalog.page(page, cancelled=cancelled)
    items = []
    for image in images:
        if cancelled():
            raise InterruptedError()
        items.append(GalleryItem(image, cache.thumbnail(image)))
    if cancelled():
        raise InterruptedError()
    return GalleryPage(
        tuple(items), int(metadata["page"]), int(metadata["pages"]), int(metadata["total"])
    )
