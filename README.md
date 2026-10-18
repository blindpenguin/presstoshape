# veccy

A small SVG editor built on PySide6.

```
uv sync
uv run python main.py
```

## Features

- Tools: select (V), bezier pen (P), rectangle (R), ellipse (E), text (T). Shift constrains rectangles/ellipses to squares/circles.
- Pen: click points for a smooth curve; double-click or Enter finishes, Esc cancels.
- Mouse wheel zooms under the cursor, middle-drag pans. Touchpad scrolling pans; Ctrl+scroll zooms.
- Union (Ctrl++) and difference (Ctrl+-) of selected shapes.
- Tool options panel (next to the tool strip) follows the active tool:
  - Select: properties of the selection — position/size (rectangle, ellipse), text content/position/size for a single object, fill / stroke / stroke width for one or many.
  - Drawing tools: the style that tool gives new shapes; text tool also sets font size.
- Layers: add, delete, rename (double-click), hide (checkbox).
- Undo/redo for all document edits.
- Opens and saves SVG (Inkscape-compatible layers). Imported shapes under rotate/skew/scale transforms are flattened to paths; gradients, clip paths, `<use>` and images aren't supported yet.

## Development

```
uv run pytest                                          # logic tests
uv run python scripts/screenshot_app.py                # offscreen screenshot -> dev-screenshots/app.png
uv run --group dev python scripts/generate_icons.py    # re-copy Tabler SVG icons
scripts/spec_dashboard.sh                              # spec-workflow approval dashboard (http://localhost:5000)
```
