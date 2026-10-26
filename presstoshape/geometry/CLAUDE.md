# geometry/ — pure shape math, no state

```
geometry/
├── affine.py             # 2D affine tuples (SVG matrix order)
├── boxes.py              # Point, Rect, drag boxes
├── align.py / snapping.py / rulers.py   # align/distribute offsets, snap targets and queries, ruler ticks
├── aspect.py             # preserveAspectRatio: align/meet/slice for the SVG viewport and pictures (`fitted_rect`, `visible_box`)
├── segments.py           # building/mapping path segments
├── pen_paths.py          # Pen nodes (point + optional handles) → line/cubic segments, open or closed
├── booleans.py           # ordered-parts booleans, divide, regions (skia-pathops)
├── transforms.py         # outline, translate, canonical shape transforms
├── nodes.py              # path node editing
├── path_edit.py          # path structure: node types, break/join, close/open, reverse, combine/split
├── corners.py            # live corners: rounded outline (used by transforms.outline), corner widget math
└── fitting.py            # freehand strokes → cubic beziers (Pencil)
```

## Rules

- **skia-pathops** in `booleans.py`: `combine_parts` (ordered parts with add/subtract/intersect/exclude modes; also computes Composite results), `divide`, `split_regions`. Works in float32; `_from_skia` rounds results. Booleans, divide and Composite parts take `transforms.area_outline` (even-odd shapes made nonzero-safe), never `outline`, which stays the drawn contour.
- Per-node data (`corner`, `rounding`) lives on the segment that ends at the node and survives edits through `dataclasses.replace`.
