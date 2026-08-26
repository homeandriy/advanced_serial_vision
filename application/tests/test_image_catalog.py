from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from serial_vision.image_catalog import ImageCatalog


class ImageCatalogTest(unittest.TestCase):
    def test_lists_and_rotates_owned_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            image_path = folder / "label.png"
            Image.new("RGB", (10, 20), "white").save(image_path)
            catalog = ImageCatalog(folder)

            self.assertEqual(["label.png"], [image.name for image in catalog.images()])
            catalog.rotate_clockwise(image_path)
            with Image.open(image_path) as rotated:
                self.assertEqual((20, 10), rotated.size)

