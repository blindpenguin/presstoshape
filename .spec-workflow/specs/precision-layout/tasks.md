# Tasks Document

All tasks: write everything independently for PressToShape. Do not copy, translate or follow code from Inkscape, inkex or other projects; interop uses only format facts and common UI conventions (see design, "Independent implementation"). Names use "type"/"target", never "kind".

- [x] 1. Model: guides, grid, view options, snap settings
  - Files: presstoshape/models/layout.py (new), presstoshape/models/app_state.py, tests/models/test_layout.py
  - `Guide`, `GridSettings`, `default_grid`, `grid_of`, `SnapSettings`, `ViewOptions`; `Document.guides/grid`; `AppState.view/snapping/align_reference`
  - Purpose: data for everything else (Req 3–6)
  - _Leverage: models/shapes.py frozen style, geometry/units_
  - _Requirements: 4.6, 5.2, 5.5, 6.1, 6.5_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement Component 1 of design.md with tests (defaults per unit, grid_of fallback, undo snapshot carries guides/grid through Session) | Restrictions: no Qt; independent implementation; no "kind" in names | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Geometry: align, distribute, snapping, ruler ticks
  - Files: presstoshape/geometry/align.py, presstoshape/geometry/snapping.py, presstoshape/geometry/rulers.py (all new), tests/geometry/test_align.py, test_snapping.py, test_rulers.py
  - Pure functions and value types per Component 2; snapping lookups by bisection; feedback lines
  - Purpose: the math, testable without Qt (Req 1, 2, 3.2, 6)
  - _Leverage: geometry/boxes (Rect, Point)_
  - _Requirements: 1.3, 1.4, 2.2, 3.2, 6.2, 6.3, 6.5, 6.7, 6.8_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced in computational geometry | Task: Implement Component 2 of design.md with the unit tests listed in the testing strategy, including a speed test (10k targets, 1000 queries) | Restrictions: no Qt; independent implementation; speaking names | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Operations: align/distribute, guides, grid, view toggles
  - Files: presstoshape/editing/operations/align.py, presstoshape/editing/operations/guides.py (new), presstoshape/editing/operations/view.py, presstoshape/editing/operations/__init__.py, presstoshape/editing/registry.py (checked callback), tests/editing/test_align.py, test_guides.py, test_view.py
  - Registered commands with can_run and labels; checkable view commands; guide/grid edits as undo steps (guide moves merge)
  - Purpose: everything users trigger (Req 1, 2, 4, 5, 6.1)
  - _Leverage: map_selected, transforms.translate, PathCache.geometry_bounds, registry.operation_
  - _Requirements: 1.1–1.6, 2.1–2.4, 4.1–4.5, 5.3, 6.1, 6.5_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement Component 3 of design.md with tests (labels, artboard reference for single objects, inside groups, can_run rules, guide add/move merge/delete/clear, grid undo, toggles not undoable) | Restrictions: operations take plain values; independent implementation | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Snapper and tool integration
  - Files: presstoshape/tools/snapper.py (new), presstoshape/tools/base.py, presstoshape/tools/select.py, presstoshape/tools/shapes.py, presstoshape/tools/pen.py, presstoshape/tools/text.py, presstoshape/tools/node.py, presstoshape/render/overlay.py, tests/tools/*
  - Per-gesture targets from the visible area; move, scale handle, drawing, node drags snap; Ctrl bypass; overlay feedback; guide dragging and deletion over a ruler in the Select tool; guide cursors
  - Purpose: snapping where users drag (Req 4.2, 6)
  - _Leverage: geometry/snapping, ToolContext, existing gesture code_
  - _Requirements: 4.2, 6.2–6.8_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement Component 4 of design.md; ToolDriver tests per the testing strategy (move to guide/edge/grid, Ctrl bypass, scale, rect drawing, node drag excludes itself, guide drag/delete, feedback) and a timing test for target building with 10k shapes | Restrictions: tools stay Qt-free; pencil, rotation, handles, nudge don't snap; independent implementation | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Rendering: guides, grid, snap feedback
  - Files: presstoshape/render/guides.py (new), presstoshape/render/scene.py, presstoshape/views/canvas_view.py (draw order, colours, visible rect), presstoshape/views/theme.py, scripts/bench_canvas.py, tests/render/*
  - Hairline guides, visible-area grid with density limits, snap feedback lines/labels; nothing in export; benchmark scenarios (snapping drag, grid shown)
  - Purpose: users see guides, grid and what snapped (Req 4.4, 5.1, 5.4, 6.7)
  - _Leverage: scene.draw_overlays, Viewport, CanvasColors_
  - _Requirements: 4.4, 4.6, 5.1, 5.4, 6.7, NFR Performance_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced with Skia | Task: Implement Component 5 of design.md; pixel tests for guides/grid, dense grid hiding, export unaffected; bench_canvas before/after CPU and GL | Restrictions: no cost when hidden; independent implementation | Success: tests green, benchmark within noise when hidden. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. Native format v6 and SVG namedview
  - Files: presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, tests/formats/samples/v6.p2s, docs/file-format.md, presstoshape/formats/svg_page.py, presstoshape/formats/svg.py, presstoshape/formats/svg_reader.py, tests/formats/*, tests/formats/samples/svg/inkscape_guides_grid.svg (hand-written)
  - Guides, grid and view options in `.p2s` v6; namedview guides (y from the viewBox bottom), grid (user units or unit suffix), showgrid/showguides/lockguides in and out; notes for angled guides and broken grids
  - Purpose: guides and grid survive saving and travel to Inkscape (Req 4.6, 5.3, 5.5)
  - _Leverage: p2s codec and migration rule, svg_page.read_page/page_attributes, NoteCollector_
  - _Requirements: 4.6, 5.3, 5.5, NFR Reliability_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement Component 7 of design.md with round-trip tests, v5 sample still opens, v6 sample, damaged data, and a hand-written Inkscape-style namedview fixture in mm | Restrictions: follow the native format rules in CLAUDE.md; fixture written by hand from format knowledge, not copied; independent implementation | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Rulers and guide creation
  - Files: presstoshape/views/ruler_view.py (new), presstoshape/views/canvas_view.py, presstoshape/views/guide_dialog.py (new), tests/views/*
  - Rulers from ruler_ticks with pointer marker and selection band, viewport margins, theme colours; drag out a guide; guide dialog on double-click
  - Purpose: rulers and guides usable (Req 3, 4.1, 4.3)
  - _Leverage: Viewport, geometry/rulers, theme_
  - _Requirements: 3.1–3.4, 4.1, 4.3_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python/PySide6 developer | Task: Implement the ruler and guide-dialog parts of Component 6 of design.md; view tests (ruler visible toggling margins, labels in units); QTest scratch run offscreen and with GL dragging a guide out of each ruler and back | Restrictions: views never assign AppState; independent implementation | Success: tests green, verified on both renderers. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. Align panel, menus, shortcuts, toolbar, settings
  - Files: presstoshape/views/align_panel.py, presstoshape/views/grid_dialog.py (new), presstoshape/views/main_window.py, presstoshape/views/keymap.py, presstoshape/views/actions.py, presstoshape/views/toolbar_view.py, presstoshape/views/settings/canvas_page.py, presstoshape/views/app_settings.py, presstoshape/app.py, presstoshape/icons.py, scripts/generate_icons.py, presstoshape/assets/icons/*, tests/views/*
  - Align panel below Layers (dock state remembered), checkable View commands, Snap To submenu, magnet toggle, shortcuts (Ctrl+R, %, #, |), grid dialog, snap distance setting, app-settings persistence of view/snap options
  - Purpose: everything reachable (Req 1.2, 2.3, 5.3, 6.1, 6.5, 7)
  - _Leverage: LayersPanel docking, AppActions, keymap, Settings pages_
  - _Requirements: 1.2, 2.3, 3.1, 4.5, 5.3, 6.1, 6.5, 7.1–7.3_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python/PySide6 developer | Task: Implement the panel, menu, toolbar, dialog and settings parts of Component 6 of design.md; tests for keymap clashes and mnemonics, checkable sync, panel enabling, persistence; QTest scratch runs offscreen and with GL (align/distribute from the panel, toggle grid/rulers/snapping by shortcut); screenshots en/de | Restrictions: no other new shortcuts; independent implementation; icons only from Tabler via generate_icons.py | Success: tests green, flows verified on both renderers. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Translations, docs and final check
  - Files: presstoshape/assets/translations/*, README.md, FAQ.md, CLAUDE.md, .spec-workflow/steering/product.md, .spec-workflow/steering/structure.md, FEATURE_GAPS.md (local)
  - German complete; README/FAQ precision features (hedged); CLAUDE.md notes (snapper per gesture, guides on the document); steering docs; full suite, self-test, bench, screenshots en/de; manual Inkscape round-trip list for the user
  - Purpose: complete, documented feature
  - _Requirements: all_
  - _Prompt: Implement the task for spec precision-layout, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on docs | Task: Translate, update docs, run all checks; tell the user what to try by hand | Restrictions: British English, hedged public wording, no em dashes in user-facing prose; FEATURE_GAPS.md stays uncommitted | Success: suite green, docs match behaviour. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
