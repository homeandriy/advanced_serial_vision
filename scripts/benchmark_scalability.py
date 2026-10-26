"""Reproduce former and current gallery/statistics paths using temporary data only."""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import shutil
import statistics
import tempfile
import time
import tracemalloc
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtGui import QPixmap, QPixmapCache
from PySide6.QtWidgets import QApplication
from serial_vision.database import Database
from serial_vision.gallery import ThumbnailCache, load_gallery_page
from serial_vision.image_catalog import SUPPORTED_EXTENSIONS, ImageCatalog


def measure(callback, repeats=3):
    samples, peaks = [], []
    for _ in range(repeats):
        gc.collect()
        tracemalloc.start()
        start = time.perf_counter()
        result = callback()
        samples.append((time.perf_counter() - start) * 1000)
        peaks.append(tracemalloc.get_traced_memory()[1] / 1024 / 1024)
        tracemalloc.stop()
        del result
    return {
        "median_ms": round(statistics.median(samples), 2),
        "python_peak_mib": round(max(peaks), 2),
    }


def legacy_gallery(folder: Path):
    # Former ImageCatalog.page + synchronous QPixmap decoding in refresh_images.
    QPixmapCache.clear()
    files = [
        path
        for path in folder.rglob("*")
        if path.is_file()
        and folder in path.resolve().parents
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    files.sort(key=lambda path: (-path.stat().st_mtime, path.name.lower()))
    return [QPixmap(str(path)) for path in files[:48]]


def legacy_statistics(database: Database):
    operations = defaultdict(lambda: {"receipt": 0, "issue": 0})
    services, models = defaultdict(int), defaultdict(int)
    for row in database.statistics_rows():
        value = datetime.fromisoformat(row["registered_at"])
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        period = value.astimezone(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m")
        operations[period][row["operation_type"]] += 1
        services[row["service"]] += 1
        models[row["model_name"]] += 1
    return {
        "operations": dict(sorted(operations.items())),
        "services": dict(sorted(services.items())),
        "models": dict(sorted(models.items(), key=lambda item: (-item[1], item[0]))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--photos", type=int, default=5000)
    parser.add_argument("--records", type=int, default=100000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="serial-vision-benchmark-") as temporary:
        root = Path(temporary)
        photos = root / "photos"
        photos.mkdir()
        sample = root / "sample.jpg"
        Image.effect_noise((1600, 1000), 32).convert("RGB").save(sample, quality=80)
        for index in range(args.photos):
            shutil.copyfile(sample, photos / f"photo-{index:06}.jpg")
        database = Database(root / "benchmark.sqlite3")
        model = database.models()[0]
        with database.connection() as db:
            db.executemany(
                "INSERT INTO devices(recognized_text, contract_number, source_image_path, operation_type, device_model_id, registered_at) VALUES (?, '', '', ?, ?, ?)",
                (
                    (
                        f"SN-{index}",
                        "receipt" if index % 2 else "issue",
                        model["id"],
                        f"2026-{index % 12 + 1:02}-15T12:00:00+00:00",
                    )
                    for index in range(args.records)
                ),
            )
        catalog, cache = ImageCatalog(photos), ThumbnailCache()
        report = {
            "environment": {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "photos": args.photos,
                "records": args.records,
                "photo_size": "1600x1000",
            }
        }
        report["gallery_before"] = measure(lambda: legacy_gallery(photos))
        report["gallery_after_cold"] = measure(
            lambda: load_gallery_page(catalog, cache, 1), repeats=1
        )
        report["gallery_after_cached"] = measure(lambda: load_gallery_page(catalog, cache, 1))
        report["gallery_raster_mib"] = {
            "before_48_cards": round(48 * 1600 * 1000 * 4 / 1024**2, 2),
            "after_48_cards_upper_bound": round(48 * 300 * 190 * 4 / 1024**2, 2),
            "png_cache_mib": round(cache.byte_count / 1024**2, 2),
        }
        report["statistics_before"] = measure(lambda: legacy_statistics(database))
        report["statistics_after"] = measure(lambda: database.statistics_summary("month"))
        assert legacy_statistics(database) == database.statistics_summary("month")
        result = json.dumps(report, indent=2)
        if args.output:
            args.output.write_text(result + "\n", encoding="utf-8")
        print(result)
        app.processEvents()


if __name__ == "__main__":
    main()
