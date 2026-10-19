# PressToShape

An experimental open-source vector drawing application for artists, built on PySide6. Early stage — see `.spec-workflow/steering/product.md` for where it is heading. Questions? See the [FAQ](FAQ.md).

## Try it

**Nightly builds** of the newest code are on the [nightly release page](https://github.com/blindpenguin/presstoshape/releases/tag/nightly), rebuilt every night when something changed. They're automatic development builds: they pass the tests and a start-up check, but nobody tried them by hand.

- Windows 10/11: the `.msi` installs PressToShape; the `-portable.zip` runs without installing and keeps its settings in its own folder. The builds aren't signed yet, so SmartScreen may warn (*More info* → *Run anyway*). Windows builds are only checked automatically, not by hand.
- Linux: download the `.AppImage`, make it executable, run it.

From source (needs [uv](https://docs.astral.sh/uv/)):

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
- Boolean operations on selected shapes: union (Ctrl++), difference (Ctrl+-), intersection (Ctrl+*), exclude (Ctrl+Alt+X) and divide (Ctrl+/), which splits overlapping shapes into separate pieces. The others also have Ctrl+Alt shortcuts that work on any keyboard layout: U, D, I and V.
- Composites (Path → Make Composite, Ctrl+Alt+C): non-destructive booleans. The selected shapes become parts of one shape, bottom to top, each set to add, subtract, intersect or exclude. Double-click (or Enter) to edit the parts with the usual tools while the result updates live; Esc, a double-click outside or Done on the bar above the canvas leaves. Composites can be nested. Release puts the parts back, Flatten bakes the result into a path.
- Object → Raise / Lower (Page Up / Page Down) and Raise to Top / Lower to Bottom (Home / End) reorder shapes, and the parts of a Composite while editing it.
- Tool options panel (next to the tool strip) follows the active tool:
  - Select: properties of the selection — position/size/rotation (rectangle, ellipse), text content/position/size/rotation for a single object, fill / stroke / stroke width for one or many.
  - Drawing tools: the style that tool gives new shapes; text tool also sets font size.
- Layers: add, delete, rename (double-click), hide (checkbox).
- Copy, cut and paste (Ctrl+C / Ctrl+X / Ctrl+V): Paste centers the shapes in the view, Paste in Place (Ctrl+Shift+V) keeps their position. Shapes go on the clipboard as SVG too, so pasting into and from Inkscape and other SVG-aware apps should work. Duplicate (Ctrl+D) copies the selection in place; Alt+drag a shape with the Select tool to drag off a copy.
- Undo/redo for all document edits.
- English (British) and German interface, following the system language by default. Edit → Settings (Ctrl+,) picks the language and the renderer. You can add or improve a translation with your own `.po` file, see [docs/translating.md](docs/translating.md).
- GPU-accelerated canvas (Skia over OpenGL; falls back to CPU rendering when no GPU is available).
- Export PNG (Ctrl+Shift+E) at any scale, transparent background.
- Saves in its own format, `.p2s` (File → Save, Ctrl+S): reopening should give back exactly the same drawing, plus the view, tool settings, selection and the Composite you were editing. The format is described in [docs/file-format.md](docs/file-format.md).
- Opens and saves SVG too (Save As → SVG; an opened SVG keeps saving as SVG), with Inkscape-compatible layers. Rotated rectangles, ellipses and text should keep their type, saved with a `transform` attribute; paths get transforms applied to their points. Composites are saved as their result path, with the parts stored in hidden metadata so other programs show the result. If another program changes the result, PressToShape should notice and open it as a plain path. Gradients, clip paths, `<use>` and images aren't supported yet.

## Development

```
uv run pytest                                          # logic tests
uv run python scripts/screenshot_app.py                # offscreen screenshot -> dev-screenshots/app.png (--language de)
uv run python scripts/update_translations.py           # after changing UI text: template + shipped .po files
uv run python scripts/bench_canvas.py                  # canvas frame times, 10k shapes (PRESSTOSHAPE_RENDERER=cpu|gl)
uv run --group dev python scripts/generate_icons.py    # re-copy Tabler SVG icons
scripts/spec_dashboard.sh                              # spec-workflow approval dashboard (http://localhost:5000)
uv run --group build python scripts/build_package.py linux   # AppImage -> dist/release/ (see --help; CI: .github/workflows/nightly.yml)
```

## License

GPL-3.0 (GPL-3.0-only) — see [LICENSE](LICENSE).
