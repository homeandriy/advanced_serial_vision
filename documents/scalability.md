# Scalability measurements

Run from the project root:

```sh
uv run --locked python scripts/benchmark_scalability.py --photos 5000 --records 100000 --output documents/scalability-benchmark.json
```

The script creates and removes its own temporary data. It does not touch user
app-data. The baseline reproduces the former full folder scan + QPixmap gallery
path and Python statistics aggregation. The current path uses catalog/thumbnail
caches and SQL grouping; summaries are asserted equal.

Measured on 2026-10-26 with Windows CPython 3.11.9, 5000 JPEGs at 1600×1000
and 100 000 equipment records. Raw results and OS details are in
[scalability-benchmark.json](scalability-benchmark.json).

| Operation | Before, ms | After, ms | Python peak before/after, MiB |
| --- | ---: | ---: | ---: |
| Gallery cold page | 2035.32 | 2319.11 | 9.72 / 10.32 |
| Gallery same page from cache | 2035.32 | 0.12 | 9.72 / 0.04 |
| Monthly statistics | 3465.61 | 2360.91 | 36.38 / 0.02 |

Times are medians of three runs except the single cold-cache run. They include
tracemalloc overhead and are local observations, not CI thresholds or estimates
for every machine. OS filesystem caches are not flushed. The cold path is
slightly slower because it prepares thumbnails; it now runs in a worker and
keeps the GUI event loop free. Cached-page timing excludes GUI card construction.

Tracemalloc measures Python allocations, not native Qt/Pillow memory or total
process RSS. As a separate calculated bound, 48 original 1600×1000 RGBA rasters
occupy approximately 292.97 MiB; 48 thumbnails at most 300×190 occupy at most
10.44 MiB. The measured PNG cache after this page was 2.38 MiB. The cache has
hard limits of 256 entries and 16 MiB; the catalog snapshot still scales with
the number of photos. Original photo preview decoding is separate from gallery
thumbnails and remains synchronous when a photo is selected.

UI regression tests hold thumbnail decoding and statistics queries behind a
threading event and verify that a Qt timer continues firing. They also verify
stale-result rejection, folder switching during a load, selection preservation,
thumbnail invalidation and full CSV export beyond the visible equipment page.
