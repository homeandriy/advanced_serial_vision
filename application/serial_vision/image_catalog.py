from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


SUPPORTED_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class CatalogImage:
    path: Path
    name: str


class ImageCatalog:
    def __init__(self, directory: Path | None) -> None:
        self.directory = directory.resolve() if directory and directory.is_dir() else None

    def images(self) -> list[CatalogImage]:
        if self.directory is None:
            return []
        files = [path for path in self.directory.rglob("*") if path.is_file() and self._is_owned(path) and path.suffix.lower() in SUPPORTED_EXTENSIONS]
        files.sort(key=lambda path: (-path.stat().st_mtime, path.name.lower()))
        return [CatalogImage(path, str(path.relative_to(self.directory))) for path in files]

    def page(self, page: int = 1, per_page: int = 48) -> tuple[list[CatalogImage], dict[str, int | bool]]:
        all_images = self.images()
        per_page = min(100, max(1, per_page))
        total = len(all_images)
        pages = max(1, (total + per_page - 1) // per_page)
        page = min(max(1, page), pages)
        start = (page - 1) * per_page
        return all_images[start:start + per_page], {"page": page, "pages": pages, "total": total, "has_more": page < pages}

    def rotate_clockwise(self, image: Path) -> None:
        self._require_owned(image)
        with Image.open(image) as source:
            rotated = source.rotate(-90, expand=True)
            rotated.save(image)

    def delete(self, image: Path) -> None:
        self._require_owned(image)
        image.unlink()

    def _require_owned(self, image: Path) -> None:
        if not self._is_owned(image):
            raise ValueError("Зображення знаходиться поза вибраною папкою.")

    def _is_owned(self, image: Path) -> bool:
        try:
            return self.directory is not None and self.directory in image.resolve().parents
        except OSError:
            return False
