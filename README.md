# PressToShape

An experimental open-source vector drawing application for artists, built on PySide6. Early stage — see `.spec-workflow/steering/product.md` for where it is heading. Questions? See the [FAQ](FAQ.md).

```
uv sync
uv run python main.py
```

## Features

- Tools: select (V), node (N), bezier pen (P), rectangle (R), ellipse (E), text (T). Shift constrains rectangles/ellipses to squares/circles.
- Select tool handles: drag a handle to scale (Shift keeps proportions, Alt scales from the center), drag just outside a corner to rotate (Shift snaps to 15°). The cursor shows what a press will do.
- Node tool: drag path nodes and their bezier handles, Shift+click or box-select several, double-click a segment to add a node, Delete removes nodes. Path → Object to Path (Ctrl+Shift+C) turns rectangles, ellipses and text into editable paths.
- Pen: click points for a smooth curve; double-click or Enter finishes, Esc cancels.
- Mouse wheel zooms under the cursor, middle-drag pans. Touchpad scrolling pans; Ctrl+scroll zooms.
- Union (Ctrl++) and difference (Ctrl+-) of selected shapes.
- Tool options panel (next to the tool strip) follows the active tool:
  - Select: properties of the selection — position/size/rotation (rectangle, ellipse), text content/position/size/rotation for a single object, fill / stroke / stroke width for one or many.
  - Drawing tools: the style that tool gives new shapes; text tool also sets font size.
- Layers: add, delete, rename (double-click), hide (checkbox).
- Undo/redo for all document edits.
- GPU-accelerated canvas (Skia over OpenGL; falls back to CPU rendering when no GPU is available).
- Export PNG (Ctrl+Shift+E) at any scale, transparent background.
- Opens and saves SVG (Inkscape-compatible layers). Rotated rectangles, ellipses and text should keep their type, saved with a `transform` attribute; paths get transforms applied to their points. Gradients, clip paths, `<use>` and images aren't supported yet.

## Development

```
uv run pytest                                          # logic tests
uv run python scripts/screenshot_app.py                # offscreen screenshot -> dev-screenshots/app.png
uv run python scripts/bench_canvas.py                  # canvas frame times, 10k shapes (PRESSTOSHAPE_RENDERER=cpu|gl)
uv run --group dev python scripts/generate_icons.py    # re-copy Tabler SVG icons
scripts/spec_dashboard.sh                              # spec-workflow approval dashboard (http://localhost:5000)
```

## License

GPL-3.0 (GPL-3.0-only) — see [LICENSE](LICENSE).
