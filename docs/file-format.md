# The PressToShape file format (`.p2s`)

PressToShape's own files use the extension `.p2s`. They store everything PressToShape can do, plus the working state SVG can't hold (view, tool settings, selection, entered Composite). This page describes format version **7**. Sample files of every version live in [`tests/formats/samples/`](../tests/formats/samples/).

## The archive

A `.p2s` file is a ZIP archive with these entries:

| Entry | Content |
|---|---|
| `mimetype` | `application/x-presstoshape`. Always the first entry, stored uncompressed, so the type can be recognized from the file's first bytes (the OpenDocument/OpenRaster convention). |
| `document.json` | The document and working state as UTF-8 JSON (described below). Deflate-compressed. |
| `preview.png` | Optional. The artboard rendered like PNG export, at most 256 px on the longer side. |
| `resources/` | Reserved for embedded images, fonts and brushes. Not written by version 1. |

Readers ignore entries they don't know. To look inside:

```
unzip -l drawing.p2s
unzip -p drawing.p2s document.json | python -m json.tool
```

## `document.json`

```json
{
  "format": "presstoshape",
  "format_version": 1,
  "app_version": "0.1.0.dev20261019+g6ba15e8",
  "document": { … },
  "state": { … }
}
```

- `format`: always `"presstoshape"`.
- `format_version`: an integer. It increases whenever what files store changes (see [Versions](#versions)).
- `app_version`: the PressToShape version that wrote the file, for information only.

All numbers are JSON numbers (written as floats where the model holds floats). `NaN` and infinities are not allowed. Colors are strings as used in SVG (`"#3b82f6"`); `null` means "none".

### `document`

| Field | Type | Meaning |
|---|---|---|
| `width`, `height` | number > 0 | Artboard size in document pixels. All coordinates are document pixels. |
| `unit` | string | Unit lengths are shown and entered in: `"px"`, `"mm"`, `"cm"`, `"in"` or `"pt"`. Display only; it doesn't change coordinates. |
| `dpi` | number, 1 to 9600 | Document pixels per inch: converts between pixels and physical units, and is the default PNG export resolution. |
| `next_id` | integer | The next free shape id. Readers raise it above the highest id in the file. |
| `layers` | list, at least one | Bottom to top, like SVG document order. |

Each layer: `{"name": string, "visible": bool, "shapes": [shape, …]}`, shapes bottom to top, plus an optional `"locked": true` when nothing in the layer can be selected.

Optional precision aids on the document:

| Field | Type | Meaning |
|---|---|---|
| `guides` | list | `{"id": integer, "orientation": "horizontal" or "vertical", "position": number}`. The position is the y of a horizontal guide or the x of a vertical one, in document pixels. Guide ids share the shape ids' range. |
| `grid` | object | `{"spacing": number > 0, "major_every": integer ≥ 1}`: minor line distance in document pixels and the major line interval. Left out when the document uses the default grid for its unit. |

### Shapes

Every shape has:

| Field | Type | Meaning |
|---|---|---|
| `type` | string | `"rect"`, `"ellipse"`, `"path"`, `"text"`, `"composite"` or `"group"`. |
| `id` | integer ≥ 0 | Unique in the whole document, Composite parts included. |
| `style` | object | `{"fill": paint, "stroke": paint, "stroke_width": number ≥ 0}`, plus the optional fields below; a paint is a colour string, `null` (none) or a gradient object (see below). Groups have none. |
| `transform` | list of 6 numbers | Optional. Affine `[a, b, c, d, e, f]` as in SVG's `matrix()`, applied on top of the geometry. Left out when it's the identity. |
| `hidden` | bool | Optional, written only as `true`. The shape isn't drawn or exported; inside a group or Composite it hides just that child or part (a hidden part is left out of the Composite's result). |
| `locked` | bool | Optional, written only as `true`. The shape is drawn but can't be selected; a locked group or Composite can't be entered. |

Optional style fields, written only when they differ from the default (which is SVG's default):

| Field | Type | Default | Meaning |
|---|---|---|---|
| `opacity` | number 0 to 1 | `1.0` | Opacity of the whole shape: fill and stroke are flattened first, then made transparent. |
| `fill_opacity`, `stroke_opacity` | number 0 to 1 | `1.0` | Opacity of the fill or stroke paint alone. |
| `fill_rule` | string | `"nonzero"` | `"nonzero"` or `"evenodd"`, as SVG's `fill-rule`. |
| `cap` | string | `"butt"` | `"butt"`, `"round"` or `"square"`. |
| `join` | string | `"miter"` | `"miter"`, `"round"` or `"bevel"`. |
| `miter_limit` | number ≥ 1 | `4.0` | As SVG's `stroke-miterlimit`. |
| `dashes` | list of numbers ≥ 0 | `[]` | Dash and gap lengths in document pixels; empty is a solid line. Readers repeat an odd-length list and treat an all-zero list as solid, as SVG does. |
| `dash_offset` | number | `0.0` | Where the dash pattern starts along the stroke. |

Gradient paint (version 8), an object in `fill` or `stroke`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type` | string | `"linear"` | `"linear"` (`x1`, `y1`, `x2`, `y2`) or `"radial"` (`cx`, `cy`, `r`, `fx`, `fy`); numbers, required. |
| `stops` | list of objects | required | `{"offset": 0 to 1, "color": string, "opacity": 0 to 1}`, offsets not decreasing; `opacity` is optional (default `1.0`). At least one stop, readers drop a gradient without any. |
| `units` | string | `"objectBoundingBox"` | `"objectBoundingBox"` (coordinates are fractions of the shape's own box) or `"userSpaceOnUse"` (in the shape's coordinates), as SVG's `gradientUnits`. |
| `spread` | string | `"pad"` | `"pad"`, `"reflect"` or `"repeat"`, as SVG's `spreadMethod`. |
| `transform` | list of 6 numbers | identity | As SVG's `gradientTransform`. |

Geometry per type:

| `type` | Fields |
|---|---|
| `rect` | `x`, `y`, `width` ≥ 0, `height` ≥ 0; optional `rx`, `ry` ≥ 0 (corner radii, default 0, clamped to half the size when drawn) |
| `ellipse` | `cx`, `cy`, `rx` ≥ 0, `ry` ≥ 0 |
| `path` | `segments`: list of `["M", x, y]` (move), `["L", x, y]` (line), `["C", c1x, c1y, c2x, c2y, x, y]` (cubic bezier), `["Z"]` (close). Paths keep an identity transform: transforms are applied to the points. |
| `text` | `x`, `y` (the anchor point on the baseline), `text` (single line), `font_size` > 0; optional `anchor`: `"start"` (default), `"middle"` or `"end"`, which point of the line sits at `x`, as SVG's `text-anchor` |
| `composite` | `parts`: list of shapes, bottom to top (may include Composites); `modes`: one per part, each `"add"`, `"subtract"`, `"intersect"` or `"exclude"`. The first part is the base, so its mode is ignored. Composites keep an identity transform; their parts carry the transforms. |
| `group` | `children`: list of shapes, bottom to top (any type, including groups and Composites), at least one; optional `opacity`, a number from 0 to 1 (default 1), applied to the children flattened together. Groups have no `style` and no `transform`: each child keeps its own, and transforms are applied to the children. Optional `masking` (see below) turns the group into a clipping or opacity mask. |

`masking` on a group (all keys but `mask` optional):

| Key | Type | Meaning |
|---|---|---|
| `mask` | list of ints | Ids of the children that are the mask objects; the other children are the content. May be empty (then the content is not shown). |
| `type` | string | `"clip"` (default: the content is cut to the fill area of the mask objects), `"luminance"` (the mask objects are drawn like artwork and their luminance times alpha is the content's alpha) or `"alpha"` (their alpha alone). |
| `inverted` | bool | Optional, written only as `true`: the mask works the other way round. |
| `region` | list of 4 numbers | Optional, opacity masks only: `x, y, width, height` in the group's space outside which nothing is shown. |

Example (from the sample file):

```json
{
  "type": "composite", "id": 3,
  "parts": [
    {"type": "rect", "id": 4, "x": 0.0, "y": 0.0, "width": 100.0, "height": 60.0,
     "style": {"fill": "#ff0000", "stroke": null, "stroke_width": 0.0}},
    {"type": "ellipse", "id": 5, "cx": 80.0, "cy": 30.0, "rx": 25.0, "ry": 25.0,
     "style": {"fill": "#ff0000", "stroke": null, "stroke_width": 0.0}}
  ],
  "modes": ["add", "subtract"],
  "style": {"fill": "#ff0000", "stroke": null, "stroke_width": 0.0}
}
```

### `state`

Working state. Everything here is optional. Readers drop values that don't match the document (for example, a selected id that no longer exists) instead of failing.

```json
{
  "view": {"zoom_percent": 150, "center": [160.0, 100.0]},
  "tools": {
    "styles": {"rectangle": {"fill": "#ff0000", "stroke": null, "stroke_width": 0.0}},
    "font_size": 20.0,
    "new_part_mode": "exclude"
  },
  "selection": [4],
  "selected_layer": 1,
  "edit_path": [3]
}
```

| Field | Meaning |
|---|---|
| `view.zoom_percent` | Zoom level in percent. |
| `view.center` | Document point shown in the middle of the window. |
| `tools.styles` | Style each drawing tool gives new shapes, keyed by tool name (`pen`, `pencil`, `rectangle`, `ellipse`, `text`). Unknown tool names are ignored. |
| `tools.font_size` | Font size for new text. |
| `tools.new_part_mode` | Mode for parts drawn inside a Composite. |
| `tools.pencil_smoothing` | Pencil smoothing, 0 to 100. Optional (default 50). |
| `selection` | Selected shape ids. |
| `selected_layer` | Index of the active layer. |
| `edit_path` | Ids of the entered Composites and groups, outer to inner; empty when none is entered. |
| `view.show_grid`, `view.show_guides`, `view.lock_guides` | Whether the grid and guides were shown and the guides locked. |

Undo history and the active tool are not stored.

## Versions

| Version | PressToShape | Changes |
|---|---|---|
| 1 | nightlies from October 2026 | First version. |
| 2 | nightlies from October 2026 | `document.unit` and `document.dpi`. Version 1 files open as `"px"` at 96 DPI. |
| 3 | nightlies from October 2026 | `state.tools.pencil_smoothing`; the Pencil's style is stored under `tools.styles.pencil`. Version 2 files need no change. |
| 4 | nightlies from October 2026 | Optional style fields `opacity`, `fill_opacity`, `stroke_opacity`, `fill_rule`, `cap`, `join`, `miter_limit`, `dashes`, `dash_offset`; rect `rx`/`ry`; text `anchor`. Version 3 files need no change. |
| 5 | nightlies from October 2026 | Shape type `group`. `state.edit_path` may now name groups too. Version 4 files need no change. |
| 6 | nightlies from October 2026 | Optional `document.guides` and `document.grid`, and their view state in `state.view`. Version 5 files need no change. |
| 7 | nightlies from October 2026 | Optional `hidden` and `locked` on shapes, optional `locked` on layers. Version 6 files need no change (everything shown and unlocked). |
| 8 | nightlies from October 2026 | `style.fill` and `style.stroke` may be a gradient object (`linear` or `radial`) instead of a colour. Version 7 files need no change. |
| 9 | nightlies from October 2026 | Optional `masking` on groups: the group is a clipping or opacity mask. Version 8 files need no change. |

Rules for changing the format:

- Any change to what files store increases `format_version`.
- PressToShape opens files of every older version by upgrading them step by step (`presstoshape/formats/p2s_migrations.py`). Saving writes the current version.
- Files with a newer version than the running PressToShape understands are refused with a message asking to update.
- Each version keeps a sample file in `tests/formats/samples/` that must open correctly in every later version.
