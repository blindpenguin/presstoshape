# Tasks Document

- [x] 1. Add skia-python dependency and export settings model
  - Files: pyproject.toml, uv.lock (via `uv add`), veccy/models/app_state.py
  - Add `skia-python==144.0.post2` with `uv add`; add `ExportSettings(scale: float = 1.0)` dataclass and `AppState.export` field
  - Purpose: Make Skia available and hold the session's last export scale
  - _Leverage: veccy/models/app_state.py (nested per-feature dataclass pattern)_
  - _Requirements: 6.4, 5.1_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer familiar with uv | Task: Add skia-python pinned with == via `uv add skia-python==144.0.post2`, and add an ExportSettings dataclass nested into AppState as `export` per design.md Data Models | Restrictions: Never hand-edit uv.lock, no Qt imports in models, keep AppState plain data | Success: `uv sync` works, `uv run python -c "import skia"` succeeds, existing pytest suite passes. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Implement Viewport math in veccy/render/viewport.py
  - Files: veccy/render/__init__.py, veccy/render/viewport.py, tests/test_viewport.py
  - Frozen `Viewport` dataclass: to_screen/to_doc, matrix(dpr) -> skia.Matrix, scroll_range (centered when scene smaller than view), zoom_at(new_zoom, anchor, residual)
  - Purpose: Qt-free replacement for QGraphicsView transform and scrollbar math
  - _Leverage: veccy/views/canvas_view.py `_apply_zoom` (anchor + scroll residual algorithm), `_SCENE_MARGIN`_
  - _Requirements: 4.7, 1.7_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with 2D graphics math experience | Task: Create veccy/render/viewport.py per design.md (Viewport component), porting the zoom-anchor and sub-pixel residual logic from CanvasView._apply_zoom, with pytest coverage (round trip, anchor stays fixed across repeated zoom steps, centered small scene, scroll range) | Restrictions: No Qt imports in veccy/render, only skia + stdlib + veccy.models; frozen dataclass; follow code style (no comments unless non-obvious why) | Success: tests/test_viewport.py passes, behavior matches the current zoom anchoring. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Implement text outlines and PathCache
  - Files: veccy/render/text.py, veccy/render/paths.py, tests/test_paths.py
  - `typeface()` (FontMgr match for "sans-serif", cached), `text_path(TextShape) -> skia.Path`; `PathCache.get/stroke_path/bounds/prune`, winding fill type, keyed by id and invalidated by frozen-shape inequality
  - Purpose: One cached geometry source for drawing, hit-testing, bounds and export
  - _Leverage: veccy/controllers/geometry.py `outline()`, veccy/models/shapes.py_
  - _Requirements: 1.2, 1.5, NFR Performance (cache)_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python graphics developer experienced with Skia | Task: Create render/text.py and render/paths.py per design.md, converting model segments to skia.Path (MoveTo/LineTo/CubicTo/Close, kWinding) and text to glyph outlines at font_size with baseline (x, y); test cache identity on unchanged shapes, rebuild on change, prune, non-empty text path, stroke_path width | Restrictions: No Qt imports; reuse geometry.outline instead of re-deriving rect/ellipse geometry; booleans keep excluding text (geometry.outline unchanged) | Success: tests pass, text path bounds scale with font_size. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Implement document drawing in veccy/render/scene.py
  - Files: veccy/render/scene.py, veccy/render/overlay.py, tests/test_render_scene.py
  - `CanvasColors` dataclass (pasteboard, artboard, border, preview, selection — passed in by views since render can't import views/theme), `Overlay` dataclass, `parse_color`, `draw_background`, `draw_document(canvas, doc, cache, overrides)`
  - Purpose: Pixel-parity drawing of the document on any skia.Canvas
  - _Leverage: veccy/views/canvas_view.py `_apply_style` (paint semantics), veccy/render/paths.py_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.8, 3.5, 6.1, 6.3_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python graphics developer experienced with Skia | Task: Implement render/overlay.py and the background/document part of render/scene.py per design.md: antialiased fill then stroke, butt cap, miter join, miter limit 4, skip None paints and zero width, visible layers bottom-to-top, overrides substitute shapes; CPU-surface pytest with sampled pixels (filled interior, no-fill interior transparent, stroke edge, hidden layer skipped, top shape wins, override position) | Restrictions: No Qt imports; render must not import veccy.views or controller state mutation; pixel assertions only on render CPU output | Success: tests pass; colors match model hex values. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [-] 5. Implement overlay drawing
  - Files: veccy/render/scene.py (continue), tests/test_render_scene.py (extend)
  - `draw_overlays(canvas, overlay, cache, vp, colors)`: dashed selection boxes at 1 screen px, rubber band (translucent fill + outline), preview path with tool style or hairline preview color
  - Purpose: All canvas feedback drawn in Skia, never in export
  - _Leverage: veccy/render/paths.py bounds, veccy/render/viewport.py_
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.6_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python graphics developer | Task: Add draw_overlays to render/scene.py per design.md with constant screen-space line widths regardless of zoom; extend tests (selection box pixels present at bounds, rubber band drawn, preview hairline when style has no stroke, draw_document never draws overlays) | Restrictions: No Qt; overlays use only Overlay + CanvasColors inputs | Success: tests pass at zoom 0.5, 1 and 4. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [ ] 6. Implement hit-testing in veccy/render/hit_test.py
  - Files: veccy/render/hit_test.py, tests/test_hit_test.py
  - `shape_at(doc, cache, point, tolerance)`, `shapes_in_rect(doc, cache, rect)` with bounds pre-check
  - Purpose: Replace QGraphicsScene picking and rubber-band selection
  - _Leverage: veccy/render/paths.py (paths, stroke_path, bounds)_
  - _Requirements: 4.1, 4.4, 4.9, NFR Performance (hit test < 10 ms)_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with computational geometry experience | Task: Implement hit_test.py per design.md: top-most visible shape wins, fill hit only if fill set, stroke hit via stroked outline of width max(stroke_width, 2*tolerance), text hit on glyph area, hidden layers ignored, rect intersection for rubber band; tests including a 10,000-shape click under 10 ms | Restrictions: No Qt; no state mutation | Success: tests pass including timing. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [ ] 7. Implement PNG export in render and controller
  - Files: veccy/render/export.py, veccy/controllers/app_controller.py, tests/test_export.py
  - `export_size(doc, scale)`, `render_png(doc, scale) -> bytes | None` (transparent, no overlays); `AppController.export_png(path, scale) -> bool` storing `state.export.scale`, status message, no checkpoint/dirty change, OSError handled
  - Purpose: Raster export using the canvas renderer
  - _Leverage: veccy/render/scene.py draw_document, AppController.save_file (I/O + status pattern)_
  - _Requirements: 5.2, 5.3, 5.4, 5.6, 5.7_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement render/export.py and AppController.export_png per design.md; tests: size per scale, transparent corner pixel, PNG decodes via skia.Image.MakeFromEncoded with expected dimensions, controller writes file, sets status, leaves undo stack and dirty unchanged, failure on unwritable path returns False with "Export failed" status | Restrictions: No Qt in controllers/render; follow existing controller method shape (status message, _notify) | Success: tests pass, full suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [ ] 8. Implement Skia surface widgets and GL format setup
  - Files: veccy/views/skia_surface.py, veccy/app.py
  - `SkiaGLWidget` (QOpenGLWidget, GrDirectContext.MakeGL, wraps default FBO, flushAndSubmit/resetContext, release on aboutToBeDestroyed, `gl_failed` signal), `SkiaRasterWidget` (CPU surface → QImage blit with DPR), `create_surface(paint_cb, parent)` honoring offscreen platform and `VECCY_RENDERER`; default QSurfaceFormat (stencil 8, macOS 4.1 core) set in App before QApplication
  - Purpose: GPU drawing with CPU fallback behind one paint-callback interface
  - _Leverage: spike in design.md Overview; CLAUDE.md lifetime rules_
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.6, 1.7_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Qt/OpenGL developer experienced with PySide6 and Skia | Task: Implement views/skia_surface.py per design.md and set the default QSurfaceFormat in App.run before QApplication creation; verify with a scratch script on desktop (GL) and offscreen (raster) that a paint callback drawing a red rect shows up (grabFramebuffer / grab) | Restrictions: Paint callback signature (canvas, width_px, height_px, dpr); QPainter only for blitting the raster image; zero-size early return; no defensive try/except around Qt calls; give widgets parents | Success: both widgets render the callback output; closing the window does not crash or warn. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [ ] 9. Implement CanvasGestures
  - Files: veccy/views/canvas_gestures.py
  - Per-tool gesture state machine producing `Overlay` and committing via controller: select (click, Ctrl toggle, move drag with overrides, rubber band, empty click clears), rectangle/ellipse with Shift, pen (dedupe, double-click/Enter finish), text dialog, Esc cancel
  - Purpose: Interaction logic separated from the scroll/paint shell
  - _Leverage: veccy/views/canvas_view.py gesture code (mousePress/Move/Release, _pen_tuples, _finish_pen, _cancel_gesture), veccy/render/hit_test.py, veccy/controllers/geometry.py (translate, box_from_drag, smooth_segments)_
  - _Requirements: 3.3, 3.4, 3.5, 4.1–4.6, 4.8_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Create views/canvas_gestures.py per design.md, porting existing gesture behavior; it receives doc-space points + modifiers from CanvasView, holds transient state, exposes `overlay` and a repaint callback, and commits through AppController (move_selection once per drag, set_selection, add_*) | Restrictions: Never mutate AppState directly; transient state stays here until commit; use lambda wrappers for Qt signal connections where relevant | Success: module compiles and is exercised by task 10 integration; behavior parity reviewed against old canvas_view.py. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [ ] 10. Rewrite CanvasView on QAbstractScrollArea + Skia
  - Files: veccy/views/canvas_view.py, veccy/views/theme.py, veccy/views/main_window.py
  - Scroll area with Skia surface viewport, Viewport-driven scrollbars, wheel/pan/zoom/resize rules ported, paint callback calling draw_background/draw_document/draw_overlays, GL→raster swap on `gl_failed`, `shutdown()` releases GL; add `theme.SELECTION`; remove QGraphicsScene usage
  - Purpose: Integrate renderer, gestures and surfaces with unchanged public API
  - _Leverage: existing CanvasView (wheelEvent, resizeEvent, fit/center), veccy/render/*, veccy/views/canvas_gestures.py, veccy/views/skia_surface.py_
  - _Requirements: 1.6, 2.2, 2.4, 2.5, 4.7, 6.2_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Rewrite views/canvas_view.py per design.md keeping refresh/center_artboard/fit_artboard/shutdown; prune PathCache on refresh; verify with scripts/screenshot_app.py (visual parity with the pre-change screenshot) and a QTest scratch script for click/Ctrl-click/rubber band/drag-move (one undo step)/rect with Shift/pen/Esc/wheel anchor/middle-drag pan, on raster and on GL | Restrictions: No QGraphicsScene/QGraphicsItem/QPainter document rendering; refresh(state) idempotent and cheap; keep file ≤ ~400 lines; disconnect signals during teardown | Success: app runs with GL on desktop and raster offscreen, screenshot matches previous appearance, QTest checks pass, pytest green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [ ] 11. Add Export PNG UI
  - Files: veccy/views/export_dialog.py, veccy/views/actions.py, veccy/views/menu_bar_view.py (+ veccy/views/main_window.py window command)
  - `ExportPngDialog` (scale 0.1–16, live W × H label, max side 16384 cap), `AppActions.export_png` (Ctrl+Shift+E), File menu entry after Save As, `MainWindow.export_png()` (dialog → file dialog → `.png` suffix → controller)
  - Purpose: Make PNG export reachable for users
  - _Leverage: MainWindow.save_document_as (file dialog + suffix pattern), AppActions._make, WindowCommands protocol, render.export.export_size_
  - _Requirements: 5.1, 5.5, Usability_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement the export UI per design.md; dialog pre-filled from state.export.scale; check with screenshot of the dialog (offscreen) and an end-to-end scratch run exporting the demo document | Restrictions: Dialogs live in views; controller receives plain path + scale; connect action via the existing lambda pattern | Success: File → Export PNG… exports a correctly sized transparent PNG; status bar reports result. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [ ] 12. Add canvas benchmark script
  - Files: scripts/bench_canvas.py
  - Generate 10,000 shapes, drive pan/zoom/drag repaints, report average/95th-percentile frame time for GL and CPU (`VECCY_RENDERER`)
  - Purpose: Verify the performance requirement and catch regressions
  - _Leverage: scripts/screenshot_app.py (App bootstrapping), AppController.add_*_
  - _Requirements: NFR Performance_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python performance engineer | Task: Write scripts/bench_canvas.py per design.md Testing Strategy; run it on GL and CPU and record results in the implementation log; if GL frame time exceeds 16 ms, profile and optimize the renderer (e.g. picture caching) within render/ | Restrictions: Dev-only script, not imported by veccy; no new runtime deps | Success: script runs, GL average ≤ 16 ms at 10,000 shapes on this machine (or documented gap with cause). Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [ ] 13. Update documentation
  - Files: CLAUDE.md, README.md, .spec-workflow/steering/tech.md (+ structure.md if needed)
  - CLAUDE.md: render/ in architecture tree, Skia/GL lifetime notes, `VECCY_RENDERER`, drop AnchorUnderMouse note, refine pixel-assertion rule (allowed on render CPU output); README: Export PNG; steering: Skia renderer implemented, controllers → render dependency
  - Purpose: Keep contributor and agent docs accurate
  - _Leverage: design.md Follow-up Documentation_
  - _Requirements: All_
  - _Prompt: Implement the task for spec skia-renderer, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Technical writer familiar with the codebase | Task: Apply the documentation updates listed in design.md Follow-up Documentation, matching each file's existing tone and density | Restrictions: Don't restate what code makes obvious; keep CLAUDE.md rules terse | Success: docs match the implemented code; no stale QGraphicsScene references. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
