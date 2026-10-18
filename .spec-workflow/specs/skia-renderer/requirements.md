# Requirements Document

## Introduction

Replace the canvas's QGraphicsScene/QPainter rendering with a GPU-accelerated Skia renderer (skia-python), and use the same renderer for a new PNG export. The first iteration reaches **feature parity** with today's canvas — shapes, styles, text, layers, selection, drawing previews, navigation — and adds no new paint features. Everything the canvas draws, including selection highlights, rubber band and drawing previews, is drawn with Skia.

The renderer is a Qt-free module (`veccy/render/`) that turns the model into Skia draw calls. Qt keeps the window, widgets and input; the canvas becomes a thin Qt surface that hosts a Skia GPU context and forwards input to gesture handling. Because QGraphicsScene currently also provides hit-testing, rubber-band selection and item dragging, these move into Qt-free logic as part of this spec.

## Alignment with Product Vision

- **Performance (product success metric)**: fluid pan/zoom/drag on documents with tens of thousands of shapes needs GPU rendering.
- **Rich paint, effects, brushes (core pillars)**: gradients, blend modes, live effects and variable-width strokes need Skia's feature set; this spec lays the foundation so those pillars become incremental additions.
- **What you see is what you export (principle 6)**: one renderer for canvas and raster export guarantees matching output.
- **Raster export (key feature 7)**: PNG export is delivered here.
- **tech.md decision 4** (commit to Skia) and **structure.md** (`veccy/render/`, Qt-free) are implemented by this spec.

## Requirements

### Requirement 1 — Skia canvas rendering at visual parity

**User Story:** As an artist, I want the canvas to look exactly as it does today after the renderer switch, so that nothing I've drawn changes appearance.

#### Acceptance Criteria

1. WHEN the canvas is shown THEN the system SHALL render the pasteboard, the artboard fill and the artboard border with the colors defined in `views/theme.py`.
2. WHEN a document contains rectangles, ellipses, paths and text THEN the system SHALL render each with its fill, stroke and stroke width, using the nonzero fill rule, flat caps and miter joins (SVG defaults).
3. WHEN a shape has `fill=None` or `stroke=None` or stroke width 0 THEN the system SHALL omit that paint.
4. WHEN layers are rendered THEN the system SHALL paint shapes in document order (layers bottom to top, shapes in list order) and SHALL skip hidden layers.
5. WHEN text shapes are rendered THEN the system SHALL draw them with Skia text rendering at the shape's font size and baseline position, and hit-testing, booleans and selection bounds SHALL use the same text outline.
6. WHEN the document changes THEN the canvas SHALL update on the next frame without restarting or flicker.
7. WHEN the display has a device pixel ratio > 1 THEN the system SHALL render at native resolution (crisp edges, no upscaling blur).
8. WHEN all shapes are antialiased THEN the result SHALL match current antialiased rendering.

### Requirement 2 — GPU rendering with CPU fallback

**User Story:** As an artist, I want the canvas to be GPU-accelerated, so that large documents stay fluid; and as a developer, I want it to work without a GPU, so that headless screenshots and CI keep working.

#### Acceptance Criteria

1. WHEN an OpenGL context is available THEN the canvas SHALL render through a Skia GPU (GL) context into the widget's framebuffer.
2. IF GPU context creation fails OR the Qt platform is `offscreen` THEN the system SHALL fall back to CPU (raster) Skia rendering, displayed in the same widget, with identical visible output.
3. WHEN the fallback is used THEN the system SHALL report it once (status message or log), not crash or show an error dialog.
4. WHEN the canvas widget is destroyed or the app closes THEN the system SHALL release the Skia GPU context and surfaces before the GL context is destroyed (no crash on exit).
5. WHEN `scripts/screenshot_app.py` runs with `QT_QPA_PLATFORM=offscreen` THEN it SHALL produce a screenshot that includes the rendered canvas.
6. WHEN running on Linux, Windows and macOS THEN GPU rendering SHALL work on each (macOS via its OpenGL 4.1 core profile).

### Requirement 3 — Overlays drawn in Skia

**User Story:** As an artist, I want selection feedback and drawing previews to stay clear and consistent, so that I always see what I'm editing.

#### Acceptance Criteria

1. WHEN shapes are selected THEN the system SHALL draw a selection indicator for each (at least equivalent to today's dashed selection outline) in Skia, at constant screen thickness independent of zoom.
2. WHEN the user drags a rubber band with the Select tool THEN the system SHALL draw the rubber band rectangle in Skia.
3. WHEN the user drags with the Rectangle or Ellipse tool THEN the system SHALL draw a live preview with that tool's style; IF the tool style has no stroke THEN the preview SHALL show a hairline outline in `theme.PREVIEW_STROKE`.
4. WHEN the user places pen points THEN the system SHALL draw the smoothed preview curve through the placed points and the cursor, with the pen tool style (hairline fallback as in 3.3).
5. WHEN a selection is being dragged THEN the system SHALL draw the selected shapes at their live offset positions.
6. WHEN overlays are drawn THEN they SHALL not be part of the document and SHALL never appear in PNG export.

### Requirement 4 — Interaction parity without QGraphicsScene

**User Story:** As an artist, I want selecting, moving and drawing to behave exactly as before, so that my workflow is unchanged.

#### Acceptance Criteria

1. WHEN the user clicks a shape with the Select tool THEN the system SHALL select the top-most visible shape whose fill area or stroke contains the point (a shape without fill is hit only on its stroke).
2. WHEN the user clicks empty canvas THEN the system SHALL clear the selection.
3. WHEN the user Ctrl-clicks a shape THEN the system SHALL toggle it in the selection.
4. WHEN the user drags from empty canvas THEN the system SHALL select all visible shapes intersecting the rubber band rectangle (Ctrl-drag adds to the selection).
5. WHEN the user drags a selected shape THEN the selection SHALL move live, and on release the system SHALL call `controller.move_selection(dx, dy)` once (one undo step).
6. WHEN the user presses Esc THEN the system SHALL cancel an in-progress preview, or otherwise clear the selection.
7. WHEN the user zooms (wheel notches, Ctrl+scroll, zoom actions, fit) or pans (middle-drag, touchpad scroll, scrollbars) THEN behavior SHALL match today's: zoom anchored under the cursor without drift, middle-button wheel ticks ignored during pan, scroll range covering the artboard plus margin, drawing staying fixed on screen when docks resize the viewport.
8. WHEN the user uses the Pen, Rectangle, Ellipse and Text tools THEN their gestures (Shift constraints, double-click/Enter finish, Esc cancel, text dialog) SHALL behave as today.
9. WHEN hit-testing and rubber-band selection are computed THEN the logic SHALL be Qt-free and covered by pytest.

### Requirement 5 — PNG export

**User Story:** As an artist, I want to export my artwork as a PNG, so that I can share and use it outside veccy.

#### Acceptance Criteria

1. WHEN the user chooses File → Export PNG… THEN the system SHALL ask for a file path and an export resolution (scale factor, with the resulting pixel size shown) and remember the last scale for the session.
2. WHEN exporting THEN the system SHALL render the artboard area of all visible layers with the same renderer as the canvas, without overlays, pasteboard or artboard border.
3. WHEN exporting THEN the background SHALL be transparent (the artboard's white canvas fill is a view aid, not document content).
4. WHEN the export completes THEN the system SHALL report success in the status bar; IF writing fails THEN it SHALL report the error in the status bar and not crash.
5. WHEN a path without `.png` extension is chosen THEN the system SHALL append `.png`.
6. WHEN exporting THEN the document and undo history SHALL be unchanged (export is not an edit).
7. WHEN the export is rendered at scale 1 THEN its pixels SHALL match the canvas rendering of the artboard at 100% zoom (excluding overlays and background).

### Requirement 6 — Qt-free renderer module and removal of QGraphicsScene

**User Story:** As a developer, I want rendering logic separated from Qt, so that it is testable headless and reusable for future exporters.

#### Acceptance Criteria

1. WHEN the renderer is implemented THEN it SHALL live in `veccy/render/`, import only models (and skia), and contain no Qt imports.
2. WHEN this spec is complete THEN `CanvasView` SHALL no longer use QGraphicsScene, QGraphicsItem or QPainter for document rendering.
3. WHEN the renderer is tested THEN pytest SHALL cover it headless via CPU surfaces (e.g. a filled rectangle colors the expected region, hidden layers don't render, export size matches scale).
4. WHEN skia-python is added THEN it SHALL be pinned with `==` in `pyproject.toml` via `uv add`.

## Non-Functional Requirements

### Code Architecture and Modularity
- **Dependency direction**: `views → controllers → models`, `views → render → models`, and controllers may use `render` for export; `render` never imports views or controllers' state mutation.
- **No Qt in `models/`, `controllers/`, `render/`.**
- **Single source of truth**: rendering is a pure function of `AppState` plus transient view state (viewport transform, overlays); the renderer holds only caches.
- **Transient gesture state** (drag offset, rubber band, previews, pan) stays in the view layer until committed via a controller call.
- **Modularity**: canvas Qt surface, gesture handling and renderer are separate modules; `canvas_view.py` stays within the structure.md size guideline.

### Performance
- Pan, zoom and selection dragging SHALL stay fluid (target 60 fps, no visible lag) with 10,000 shapes on a typical integrated GPU; a benchmark script under `scripts/` SHALL measure frame time for a generated large document.
- Per-shape Skia geometry SHALL be cached and rebuilt only when the frozen shape changes.
- Hit-testing a click SHALL stay under 10 ms with 10,000 shapes.

### Security
- No change to file parsing; export writes only to the user-chosen path.

### Reliability
- No crash when GPU initialization fails, on context loss, on window close, or when the widget is resized to zero.
- Existing pytest suite keeps passing; new logic is covered by tests.

### Usability
- No visible change in behavior or appearance besides the new Export PNG command.
- Export PNG is reachable from the File menu with a keyboard shortcut (Ctrl+Shift+E).
