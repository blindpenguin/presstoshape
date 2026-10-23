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

- Tools: select (V), node (N), bezier pen (P), pencil (F), rectangle (R), ellipse (E), text (T). Shift constrains rectangles/ellipses to squares/circles.
- Select tool handles: drag a handle to scale (Shift keeps proportions, Alt scales from the center), drag just outside a corner to rotate (Shift snaps to 15°). The cursor shows what a press will do.
- Node tool: drag path nodes and their bezier handles, Shift+click or box-select several, double-click a segment to add a node, Delete removes nodes. Path → Object to Path (Ctrl+Shift+C) turns rectangles, ellipses and text into editable paths.
- Pen: click points for a smooth curve; double-click or Enter finishes, Esc cancels.
- Pencil: drag to draw freehand; on release the stroke becomes a smooth path with few nodes, ready for node editing. A Smoothing slider sets how calm the line comes out; ending near the start closes the shape. Drawing tablets work like a mouse (no pressure yet).
- Mouse wheel zooms under the cursor, middle-drag pans. Touchpad scrolling pans; Ctrl+scroll zooms.
- Boolean operations on selected shapes: union (Ctrl++), difference (Ctrl+-), intersection (Ctrl+*), exclude (Ctrl+Alt+X) and divide (Ctrl+/), which splits overlapping shapes into separate pieces. The others also have Ctrl+Alt shortcuts that work on any keyboard layout: U, D, I and V.
- Composites (Path → Make Composite, Ctrl+Alt+C): non-destructive booleans. The selected shapes become parts of one shape, bottom to top, each set to add, subtract, intersect or exclude. Double-click (or Enter) to edit the parts with the usual tools while the result updates live; Esc, a double-click outside or Done on the bar above the canvas leaves. Composites can be nested. Release puts the parts back, Flatten bakes the result into a path.
- Groups (Object → Group, Ctrl+G; Ungroup, Ctrl+Shift+G): the selected shapes move, scale, rotate, copy and arrange as one object, each keeping its own style. A group's opacity applies to the group as a whole; other style changes reach every shape in it. Double-click (or Enter) to work on the shapes inside, like a Composite; Esc or Done leaves. Groups can hold Composites and other groups.
- Arrow keys nudge the selection (with the Node tool: the selected nodes) by a small step in the document's unit, Shift by ten steps, Alt by one screen pixel. Object → Flip Horizontal / Flip Vertical (Shift+H / Shift+V) mirrors the selection about its centre; text keeps reading forwards.
- Precision: align and distribute objects from the Align panel (below Layers) or Object → Align / Distribute, relative to the selection or the artboard. Rulers along the canvas (View → Show Rulers, Ctrl+R) in the document's unit; drag a guide out of a ruler, drag it back onto the ruler to remove it, double-click it to type a position. A grid with adjustable spacing (View → Show Grid, #; View → Grid Settings…). Snapping (View → Snapping, %, or the magnet button) to the grid, guides, the artboard, other objects' edges and centres (also far away, with a line showing what lines up) and path nodes, while moving, scaling, drawing and editing nodes; hold Ctrl while dragging to ignore it. Guides and the grid are saved in the file and in SVG in the format Inkscape uses.
- Object → Raise / Lower (Page Up / Page Down) and Raise to Top / Lower to Bottom (Home / End) reorder shapes, and the shapes inside an entered group or Composite.
- Tool options panel (next to the tool strip) follows the active tool:
  - Select: properties of the selection — position/size/rotation (rectangle, ellipse), text content/position/size/rotation for a single object, corner radius for rectangles, alignment (left, centre, right) for text, and the style for one or many: fill and stroke with their own opacity, stroke width, object opacity, fill rule (for paths), line ends, corners and dashes.
  - Drawing tools: the style that tool gives new shapes (including opacity, line ends, corners and dashes); text tool also sets font size.
- Layers panel: a tree of layers and the objects in them (groups and Composites expand to their contents). Add, delete and rename layers (double-click); the eye and lock on each row hide or lock that layer or object. Clicking an object's row selects it, entering the groups around it. Object → Hide Selection (Ctrl+3) / Show All (Ctrl+Alt+3) and Lock Selection (Ctrl+2) / Unlock All (Ctrl+Alt+2) do the same from the menu: hidden objects aren't drawn or exported, locked ones stay visible but can't be selected, so you can draw over a sketch without grabbing it.
- Copy, cut and paste (Ctrl+C / Ctrl+X / Ctrl+V): Paste centers the shapes in the view, Paste in Place (Ctrl+Shift+V) keeps their position. Shapes go on the clipboard as SVG too, so pasting into and from Inkscape and other SVG-aware apps should work. Duplicate (Ctrl+D) copies the selection in place; Alt+drag a shape with the Select tool to drag off a copy.
- Pictures: File → Place Image… (or drop PNG, JPEG, WebP or GIF files on the window, or paste a bitmap) puts a picture on the page at its pixel size. Scale, rotate, flip and fade it like other objects; Object → Picture has Reset Size, Fit to Page, Replace… and reference images (File → Place as Reference…: dimmed, locked guide pictures that stay out of exports and of saved SVG; View → Show References hides them). Pictures are stored inside `.p2s` files and embedded in saved SVG; PressToShape never fetches anything from the internet. Opening an SVG with `<image>` elements should bring in the pictures (embedded data, or files next to the SVG); SVG files used as pictures aren't supported, and the import dialog lists what was left out.
- Undo/redo for all document edits.
- Crash recovery: while a document has unsaved changes, PressToShape keeps a recovery copy in its own data folder (every 5 minutes by default, adjustable or off in Settings). After a crash or power loss, the next start offers it; recovered documents open unsaved and ask where to save. Saving over a file keeps the previous version as `name.backup.p2s` (or `.backup.svg`), which can be turned off.
- English (British) and German interface, following the system language by default. Edit → Settings picks the language and the renderer. You can add or improve a translation with your own `.po` file, see [docs/translating.md](docs/translating.md).
- GPU-accelerated canvas (Skia over OpenGL; falls back to CPU rendering when no GPU is available).
- New Document dialog at startup and on File → New: presets for print (A3 to A6, US Letter, …), screens, social media and icons, or a custom size in px, mm, cm, in or pt with a resolution (DPI). At startup it also lists recent files and offers Open…; it can be turned off there or in Settings. File → Open Recent lists the last ten files.
- Documents remember their unit: positions, sizes and stroke widths show in it (font sizes in pt for print units).
- Export PNG (Ctrl+Shift+E) at any resolution (DPI) or scale, transparent background; the PNG records its DPI.
- Saves in its own format, `.p2s` (File → Save, Ctrl+S): reopening should give back exactly the same drawing, plus the view, tool settings, selection and the group or Composite you were editing. The format is described in [docs/file-format.md](docs/file-format.md).
- Opens and saves SVG too (Save As → SVG; an opened SVG keeps saving as SVG), with Inkscape-compatible layers. Rotated rectangles, ellipses and text should keep their type, saved with a `transform` attribute; paths get transforms applied to their points. Groups are saved as `<g>`, and groups in other files open as groups (a group's opacity included). Composites are saved as their result path, with the parts stored in hidden metadata so other programs show the result. If another program changes the result, PressToShape should notice and open it as a plain path. SVG files keep their physical size: an A4 document is saved as `width="210mm"`, and A4 files from Inkscape should open as A4 in mm. Hidden and locked objects and layers are saved the way Inkscape stores them, and hidden objects in other files open as hidden objects rather than being dropped. Files from other programs should keep CSS class styles (as Illustrator writes them), opacity, even-odd fills, dashes, line ends and corners, rounded rectangles, `<use>` copies and symbols, and multi-line text (each line becomes its own text object). Gradients, clip paths, masks, filters and markers aren't supported yet: when a file contains them, a dialog lists what couldn't be imported, since saving it as SVG would leave those parts out.

## Development

```
uv run pytest                                          # logic tests
uv run ruff check . && uv run ruff format --check .   # lint + formatting (drop --check to reformat)
uv run python scripts/screenshot_app.py                # offscreen screenshot -> dev-screenshots/app.png (--language de)
uv run python scripts/update_translations.py           # after changing UI text: template + shipped .po files
uv run python scripts/bench_canvas.py                  # canvas frame times, 10k shapes (PRESSTOSHAPE_RENDERER=cpu|gl)
uv run --group dev python scripts/generate_icons.py    # re-copy Tabler SVG icons
scripts/spec_dashboard.sh                              # spec-workflow approval dashboard (http://localhost:5000)
uv run --group build python scripts/build_package.py linux   # AppImage -> dist/release/ (see --help; CI: .github/workflows/nightly.yml)
```

## License

GPL-3.0 (GPL-3.0-only) — see [LICENSE](LICENSE).
