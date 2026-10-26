# render/ — Skia drawing

```
render/
├── scene.py / picture.py # document, overlays; recorded-picture replay
├── images.py             # picture decode cache (LRU, mip levels for huge ones) and drawing; `PathCache.images`
├── paths.py / text.py    # cached shape paths, text outlines
├── hit_test.py / handles.py   # picking: shapes, selection frame, handles, nodes
├── viewport.py           # doc <-> screen mapping, zoom anchoring, scroll model
└── export.py             # PNG export
```

## Rules

- Paint defaults must match SVG so canvas, export and saved file look the same: nonzero (winding) fill, butt cap, miter join, miter limit 4, opacity 1 (defaults on `models/shapes.Style`, applied in `render/paths.py` / `render/scene.py`). Keep values in range through `models.shapes.sanitized`. Opacity layers (`saveLayerAlpha`) only for shapes with fill and stroke below full opacity; everything else must cost nothing extra per frame.
- The canvas redraws everything from state each frame. `PathCache` keys Skia geometry by shape id and rebuilds when the frozen shape changes.
- Per-frame cost is mostly Python→Skia call overhead: the canvas replays recorded pictures (`render/picture.py`) instead of drawing shapes one by one, and rects/ovals/text use `drawRect`/`drawOval`/`drawTextBlob` (fast GPU paths) rather than generic paths. Text outlines for hit-testing/bounds come from the same font setup (`render/text.py`).
- Reference images (`reference=True`) are dimmed, locked, left out of exports and saved SVG; `PathCache.drawing(zoom, references)` carries the zoom and the show-references switch into recorded pictures.
- Canvas performance: `uv run python scripts/bench_canvas.py` (10k shapes; `PRESSTOSHAPE_RENDERER=cpu` for the raster path).
