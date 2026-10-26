from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from PIL import Image

SUPPORTED_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True)
class CatalogImage:
    path: Path
    name: str
    modified_ns: int = 0
    size: int = 0


class ImageCatalog:
    def __init__(self, directory: Path | None) -> None:
        self.directory = directory.absolute() if directory else None
        self._snapshot: tuple[CatalogImage, ...] | None = None
        self._revision = 0
        self._lock = Lock()

    def invalidate(self) -> None:
        with self._lock:
            self._revision += 1
            self._snapshot = None

    def images(self, cancelled: Callable[[], bool] = lambda: False) -> list[CatalogImage]:
        with self._lock:
            snapshot, revision = self._snapshot, self._revision
        if snapshot is not None:
            return list(snapshot)
        if self.directory is None:
            return []
        files = []
        for path in self.directory.rglob("*"):
            if cancelled():
                raise InterruptedError()
            try:
                if (
                    path.suffix.lower() not in SUPPORTED_EXTENSIONS
                    or not path.is_file()
                    or not self._is_owned(path)
                ):
                    continue
                info = path.stat()
                files.append(
                    CatalogImage(
                        path, str(path.relative_to(self.directory)), info.st_mtime_ns, info.st_size
                    )
                )
            except OSError:
                continue  # A photo may disappear while a removable folder is indexed.
        files.sort(key=lambda image: (-image.modified_ns, image.name.lower()))
        with self._lock:
            if revision == self._revision:
                self._snapshot = tuple(files)
        return files

    def page(
        self, page: int = 1, per_page: int = 48, cancelled: Callable[[], bool] = lambda: False
    ) -> tuple[list[CatalogImage], dict[str, int | bool]]:
        all_images = self.images(cancelled)
        per_page = min(100, max(1, per_page))
        total = len(all_images)
        pages = max(1, (total + per_page - 1) // per_page)
        page = min(max(1, page), pages)
        start = (page - 1) * per_page
        return all_images[start : start + per_page], {
            "page": page,
            "pages": pages,
            "total": total,
            "has_more": page < pages,
        }

    def rotate_clockwise(self, image: Path) -> None:
        self._require_owned(image)
        with Image.open(image) as source:
            rotated = source.rotate(-90, expand=True)
            rotated.save(image)
        self.invalidate()

    def delete(self, image: Path) -> None:
        self._require_owned(image)
        image.unlink()
        self.invalidate()

    def _require_owned(self, image: Path) -> None:
        if not self._is_owned(image):
            raise ValueError("image_outside_folder")

    def _is_owned(self, image: Path) -> bool:
        try:
            return self.directory is not None and self.directory in image.resolve().parents
        except OSError:
            return False
