# The PressToShape file format (`.p2s`)

PressToShape's own files use the extension `.p2s`. They store everything PressToShape can do, plus the working state SVG can't hold (view, tool settings, selection, entered Composite). This page describes format version **1**. A sample file lives in [`tests/formats/samples/v1.p2s`](../tests/formats/samples/v1.p2s).

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
| `width`, `height` | number > 0 | Artboard size in document units (px). |
| `next_id` | integer | The next free shape id. Readers raise it above the highest id in the file. |
| `layers` | list, at least one | Bottom to top, like SVG document order. |

Each layer: `{"name": string, "visible": bool, "shapes": [shape, …]}`, shapes bottom to top.

### Shapes

Every shape has:

| Field | Type | Meaning |
|---|---|---|
| `type` | string | `"rect"`, `"ellipse"`, `"path"`, `"text"` or `"composite"`. |
| `id` | integer ≥ 0 | Unique in the whole document, Composite parts included. |
| `style` | object | `{"fill": color or null, "stroke": color or null, "stroke_width": number ≥ 0}`. |
| `transform` | list of 6 numbers | Optional. Affine `[a, b, c, d, e, f]` as in SVG's `matrix()`, applied on top of the geometry. Left out when it's the identity. |

Geometry per type:

| `type` | Fields |
|---|---|
| `rect` | `x`, `y`, `width` ≥ 0, `height` ≥ 0 |
| `ellipse` | `cx`, `cy`, `rx` ≥ 0, `ry` ≥ 0 |
| `path` | `segments`: list of `["M", x, y]` (move), `["L", x, y]` (line), `["C", c1x, c1y, c2x, c2y, x, y]` (cubic bezier), `["Z"]` (close). Paths keep an identity transform: transforms are applied to the points. |
| `text` | `x`, `y` (baseline start), `text` (single line), `font_size` > 0 |
| `composite` | `parts`: list of shapes, bottom to top (may include Composites); `modes`: one per part, each `"add"`, `"subtract"`, `"intersect"` or `"exclude"`. The first part is the base, so its mode is ignored. Composites keep an identity transform; their parts carry the transforms. |

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
| `tools.styles` | Style each drawing tool gives new shapes, keyed by tool name (`pen`, `rectangle`, `ellipse`, `text`). Unknown tool names are ignored. |
| `tools.font_size` | Font size for new text. |
| `tools.new_part_mode` | Mode for parts drawn inside a Composite. |
| `selection` | Selected shape ids. |
| `selected_layer` | Index of the active layer. |
| `edit_path` | Ids of the entered Composites, outer to inner; empty when none is entered. |

Undo history and the active tool are not stored.

## Versions

| Version | PressToShape | Changes |
|---|---|---|
| 1 | nightlies from October 2026 | First version. |

Rules for changing the format:

- Any change to what files store increases `format_version`.
- PressToShape opens files of every older version by upgrading them step by step (`presstoshape/formats/p2s_migrations.py`). Saving writes the current version.
- Files with a newer version than the running PressToShape understands are refused with a message asking to update.
- Each version keeps a sample file in `tests/formats/samples/` that must open correctly in every later version.
