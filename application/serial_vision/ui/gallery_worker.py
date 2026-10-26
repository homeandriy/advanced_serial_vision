from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from serial_vision.gallery import ThumbnailCache, load_gallery_page
from serial_vision.image_catalog import ImageCatalog


class GalleryWorker(QThread):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self, catalog: ImageCatalog, cache: ThumbnailCache, page: int, parent=None
    ) -> None:
        super().__init__(parent)
        self.catalog, self.cache, self.page = catalog, cache, page

    def run(self) -> None:
        try:
            result = load_gallery_page(
                self.catalog, self.cache, self.page, self.isInterruptionRequested
            )
            self.completed.emit(result)
        except InterruptedError:
            pass
        except Exception as error:
            self.failed.emit(str(error))
