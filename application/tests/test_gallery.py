from __future__ import annotations

import ctypes
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from serial_vision.gallery import ThumbnailCache, load_gallery_page
from serial_vision.image_catalog import ImageCatalog


class GalleryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for index in range(3):
            Image.new("RGB", (600, 400), (index * 80, 0, 0)).save(self.root / f"{index}.png")
        self.catalog = ImageCatalog(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_pagination_reuses_snapshot_until_explicit_invalidation(self) -> None:
        self.catalog.page(1, 1)
        with patch.object(Path, "rglob", side_effect=AssertionError("unexpected scan")):
            images, metadata = self.catalog.page(2, 1)
        self.assertEqual(1, len(images))
        self.assertEqual(3, metadata["total"])
        Image.new("RGB", (20, 20)).save(self.root / "new.png")
        self.assertEqual(3, len(self.catalog.images()))
        self.catalog.invalidate()
        self.assertEqual(4, len(self.catalog.images()))

    def test_root_is_canonical_before_owned_path_comparison(self) -> None:
        child = self.root / "child"
        child.mkdir()
        alias = child / ".."
        catalog = ImageCatalog(alias)
        self.assertEqual(self.root.resolve(), catalog.directory)
        self.assertEqual(3, len(catalog.images()))

    @unittest.skipUnless(os.name == "nt", "Windows short paths")
    def test_windows_short_root_accepts_its_owned_photos(self) -> None:
        get_short_path = ctypes.windll.kernel32.GetShortPathNameW
        get_short_path.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
        get_short_path.restype = ctypes.c_uint
        buffer = ctypes.create_unicode_buffer(32768)
        length = get_short_path(str(self.root), buffer, len(buffer))
        if not length or length >= len(buffer) or buffer.value == str(self.root):
            self.skipTest("8.3 aliases are unavailable on this volume")
        catalog = ImageCatalog(Path(buffer.value))
        self.assertEqual(self.root.resolve(), catalog.directory)
        self.assertEqual(3, len(catalog.images()))

    def test_cached_thumbnail_avoids_decoding_and_changed_file_gets_new_preview(self) -> None:
        cache = ThumbnailCache()
        original = self.catalog.images()[0]
        before = cache.thumbnail(original)
        with patch(
            "serial_vision.gallery.Image.open", side_effect=AssertionError("unexpected decode")
        ):
            self.assertEqual(before, cache.thumbnail(original))
        Image.new("RGB", (600, 400), "blue").save(original.path)
        os.utime(
            original.path, ns=(original.modified_ns + 1_000_000, original.modified_ns + 1_000_000)
        )
        self.catalog.invalidate()
        after = next(item for item in self.catalog.images() if item.path == original.path)
        self.assertNotEqual(before, cache.thumbnail(after))

    def test_cache_is_bounded_by_count_and_bytes(self) -> None:
        cache = ThumbnailCache(capacity=1, max_bytes=4096)
        for image in self.catalog.images():
            cache.thumbnail(image)
        self.assertLessEqual(len(cache._items), 1)
        self.assertLessEqual(cache.byte_count, 4096)

    def test_cancelled_scan_does_not_publish_partial_snapshot(self) -> None:
        with self.assertRaises(InterruptedError):
            self.catalog.images(cancelled=lambda: True)
        self.assertIsNone(self.catalog._snapshot)
        self.assertEqual(3, len(self.catalog.images()))

    def test_corrupt_thumbnail_keeps_card_without_aborting_page(self) -> None:
        (self.root / "broken.png").write_bytes(b"not an image")
        page = load_gallery_page(self.catalog, ThumbnailCache(), 1)
        self.assertEqual(4, page.total)
        self.assertEqual(
            b"", next(item.thumbnail for item in page.items if item.image.name == "broken.png")
        )

    def test_rotation_and_delete_invalidate_snapshot(self) -> None:
        first = self.catalog.images()[0]
        self.catalog.rotate_clockwise(first.path)
        self.assertIsNone(self.catalog._snapshot)
        self.catalog.images()
        self.catalog.delete(first.path)
        self.assertEqual(2, len(self.catalog.images()))
