# Tasks Document

- [x] 1. Colour model and colour math
  - Files: presstoshape/models/colours.py, presstoshape/models/app_state.py, presstoshape/geometry/colours.py, tests/geometry/test_colours.py
  - `Swatch`, `ColourState`, `PaintSlot`, `NumberMode`; `Document.swatches`, `AppState.colours`, `Tool.EYEDROPPER` (enum value only; the registry entry comes in task 6); hex/RGB/HSV conversions, `hsv_for` (keeps hue on grey, hue + saturation on black), `parse_hex_input` with a keyword callback
  - Purpose: the data and pure math everything else builds on (Req 2.3, 2.5, 2.6, 4.1, 4.8)
  - _Leverage: models/layout.py as the sub-dataclass pattern_
  - _Requirements: 2.3, 2.5, 2.6, 4.1, 4.8_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement per design.md "Data Models" and "Colour picker and numbers" (geometry part); tests: no-drift round trip for every 8-bit grey and a colour grid, hue kept on grey/black, hex input cases (#rgb, rrggbb, keywords via callback, garbage) | Restrictions: no Qt; geometry must not import formats; existing constructors and tests keep working | Success: full suite green, ruff clean, architecture test passes. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Colour queries and operations
  - Files: presstoshape/editing/queries.py, presstoshape/editing/operations/colours.py, presstoshape/editing/operations/__init__.py, tests/editing/test_colours.py
  - `colour_target`, `target_style`, `target_paint` (MIXED), `document_colours`; `_restyle` dispatch; `set_active_paint`, `toggle_active_paint`, `apply_colour`, `apply_sampled_colour`, `set_paint_none`, `swap_paints`, `default_paints`, `pick_up_style`, `remember_colour`, `clear_recent_colours`, `set_number_mode`, `set_library`; registered `colour.toggle_active`, `colour.swap`, `colour.none`, `colour.default` with `can_run`
  - Purpose: every colour change in one place (Req 1, 3, 6.2–6.3)
  - _Leverage: style.restyle_shape, display_style, _document.map_selected, view.set_tool_style, Session.edit merge_key/end_merge_
  - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 3.1, 3.2, 3.3, 6.2, 6.3, 6.6_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer familiar with the session/operations architecture | Task: Implement per design.md "Target and active paint", "Recent colours" and the operation part of "Eyedropper"; tests per Testing Strategy (each target incl. groups, masked groups, images-only; merge and undo counts; swap/none/default; gradients replaced; recent order/dedupe/limit 16; pick_up_style keeps geometry and selection; current-colour path) | Restrictions: reach shapes through editing/containers and map_selected; plain values in; view-state changes notify without undo | Success: tests green, ruff clean. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Swatch operations
  - Files: presstoshape/editing/operations/colours.py (or presstoshape/editing/operations/swatches.py if colours.py grows past ~300 lines), tests/editing/test_swatches.py
  - `add_swatch`, `rename_swatch`, `replace_swatch`, `delete_swatch`, `move_swatch`, `delete_all_swatches`, `copy_swatch`, `import_swatches`, `add_document_colours`, with `palette: "document" | "library"`; document ids from `next_id`, library ids local; document variants are labelled undo steps, library variants notify only
  - Purpose: managing both palettes (Req 4.1–4.3, 5.2)
  - _Leverage: task 2's operations, queries.document_colours_
  - _Requirements: 4.1, 4.2, 4.3, 4.8, 5.2_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement per design.md "Swatches"; tests: each operation on both palettes, undo only for document, duplicate skipping on copy/import, add_document_colours with gradients, groups, Composite parts and hidden layers, ids unique with shapes and guides | Restrictions: no Qt; frozen Swatch changed via replace | Success: tests green, ruff clean. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Files: .p2s v13 and SVG swatches
  - Files: presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, presstoshape/formats/svg_swatches.py, presstoshape/formats/svg.py, presstoshape/formats/svg_reader.py, presstoshape/formats/svg_names.py, presstoshape/formats/svg_notes.py, docs/file-format.md, tests/formats/samples/v13.p2s, tests/formats/test_p2s.py, tests/formats/test_p2s_migrations.py, tests/formats/test_svg_swatches.py, tests/formats/test_svg_generator.py
  - `.p2s` `swatches` field (validated, ids checked with shapes/guides), version 13, no-op migration, sample, docs row; SVG writes `inkscape:swatch="solid"` gradients in `<defs>` from `write_svg` only; reader reads `inkscape:swatch` and `osb:paint` solid swatches (href chains), notes gradient swatches; clipboard carries none
  - Purpose: swatches travel with files and to/from Inkscape (Req 4.4–4.7)
  - _Leverage: PaintDefs.new_id, svg_gradients stop reading, existing note pattern_
  - _Requirements: 4.4, 4.5, 4.6, 4.7_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced in file formats and SVG | Task: Implement per design.md "Files"; tests: p2s round trip and damaged values, v12 sample opens, SVG round trip incl. names and opacity, Inkscape 1.x and 0.92 snippets, shapes using url(#swatch) get the flat colour, resvg generator check unchanged with swatches; if Inkscape is installed, open a saved file and check the Swatches panel (adjust ids from names if labels aren't shown) | Restrictions: explicit encoders; everything saved must open again | Success: tests green, ruff clean. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Palette and library files
  - Files: presstoshape/formats/gpl.py, presstoshape/formats/swatch_library.py, tests/formats/test_gpl.py, tests/formats/test_swatch_library.py
  - `read_gpl` / `write_gpl` (tolerant reader, header required), library JSON read/write with version and validation
  - Purpose: personal library storage and palette exchange (Req 5.1, 5.3, 5.4)
  - _Leverage: svg_values.parse_color is not needed here (gpl is RGB numbers); geometry/colours for hex_
  - _Requirements: 5.1, 5.3, 5.4_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement per design.md "Swatches" (library file, .gpl) and "Error Handling" 2–3; tests with GIMP, Inkscape and Krita style palettes (comments, Columns, tabs, unnamed colours, CRLF), malformed files raise ValueError, library round trip, malformed JSON | Restrictions: formats uses only models + geometry; no I/O beyond text in/out (callers read and write files) | Success: tests green, ruff clean. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. Eyedropper: sampling, leaf hit-test and tool
  - Files: presstoshape/render/sample.py, presstoshape/render/hit_test.py, presstoshape/tools/eyedropper.py, presstoshape/tools/base.py, presstoshape/tools/registry.py, presstoshape/views/canvas_view.py (sample_color hook), presstoshape/views/cursors.py, presstoshape/views/keymap.py, presstoshape/views/tool_options_view.py, presstoshape/icons.py, scripts/generate_icons.py, presstoshape/assets/icons, tests/render/test_sample.py, tests/render/test_hit_test.py, tests/tools/test_eyedropper.py
  - `color_at` (1×1 surface, page colour, transparent → None), `leaf_at` (deepest, groups yes, Composites stop, locked yes, hidden no, mask objects skipped), `EyedropperTool` press logic, `ToolContext.sample_color`, `CursorType.EYEDROPPER` (badge cursor), `tool.eyedropper` with `I`, icon, tool options page with hint
  - Purpose: picking up styles and colours (Req 6)
  - _Leverage: draw_document, hit_test._contains, cursor badge pattern, ToolDriver_
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced in Skia and editor input | Task: Implement per design.md "Eyedropper"; tests: pixel colour over shapes, semi-transparent shape on page, empty pasteboard; leaf_at cases; ToolDriver click/Shift+click/image/empty/no selection with a stubbed sample_color | Restrictions: tools and render Qt-free; no per-frame cost when the tool is idle | Success: tests green, ruff clean, mnemonic test passes. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Colour picker, paint pair and swatch grid widgets
  - Files: presstoshape/views/colour_picker.py, presstoshape/views/paint_pair.py, presstoshape/views/swatch_grid.py, presstoshape/icons.py, scripts/generate_icons.py, presstoshape/assets/icons, tests/views/test_colour_picker.py, tests/views/test_swatch_grid.py
  - `ColourPicker` (SV square + hue strip painted with gradients, `dragged` / `released`, `set_hsv` silent), `PaintPair` (fill/stroke, None, gradient, mixed; swap/none/default buttons), `SwatchGrid` (flow of squares, tooltip, click, context menu hooks, optional "+" cell)
  - Purpose: reusable widgets for the panel and later gradient stops (Req 1.1, 2.1, 3.1, 4.2)
  - _Leverage: views/icon_engine.icon, theme colours, widgets.ColorButton gradient strip code_
  - _Requirements: 1.1, 2.1, 3.1, 4.2_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement per design.md "Colour picker and numbers" and "Panel layout"; widget tests with QTest (mouse drag on the square emits dragged then released with expected HSV; set_hsv emits nothing; grid click/tooltip) | Restrictions: views only; plain values out via signals; no defensive try/except around Qt | Success: tests green, ruff clean. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. Colour panel, dock, preview and persistence
  - Files: presstoshape/views/colour_panel.py, presstoshape/views/main_window.py, presstoshape/views/canvas_view.py, presstoshape/views/app_settings.py, presstoshape/views/keymap.py, presstoshape/views/widgets.py, presstoshape/views/style_editor.py, presstoshape/views/selection_view.py, presstoshape/views/tool_options_view.py, tests/views/test_colour_panel.py, tests/views/test_app_settings.py
  - Panel assembly (pair, picker, number mode, hex, alpha, Recent/Document/Library sections with menus, import/export dialogs); `refresh` cheap and idempotent; HSV kept across refreshes; drag preview via `CanvasView.set_style_preview`; dock above Layers; recent colours and number mode in settings, library loaded/saved via `swatch_library_path` + `write_atomically`; ColorButton click activates the slot instead of the dialog; Object → Colour submenu, X and Shift+X
  - Purpose: the user-facing feature (Req 1–5)
  - _Leverage: _OpacityRow, MainWindow._remember_view, Overlay.moving/live, app_settings._data_folder_
  - _Requirements: 1.1–1.9, 2.1–2.4, 3.2–3.4, 4.2–4.3, 5.1–5.5_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement per design.md "Panel layout", "Drag preview" and persistence parts; tests: panel follows targets, field edits merge, library load failure leaves file alone, settings round trip, style editor click opens no dialog; QTest scratch script offscreen and on the desktop (GL): picker drag with 100 of 10k shapes selected (print frame times, target < 16 ms after the first), one undo step, eyedropper click and Shift+click; screenshots at minimum dock width in English and German read by eye | Restrictions: blockSignals on refresh; views never assign to AppState; tests and screenshots pass their own folders and touch no real library file | Success: suite green incl. mnemonic tests, frame target met or reported. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Translations, docs and final check
  - Files: presstoshape/assets/translations/*, README.md, FAQ.md, FEATURE_GAPS.md, docs/file-format.md, .spec-workflow/steering/product.md, .spec-workflow/steering/structure.md, CLAUDE.md, presstoshape/app.py (self-test if new data files)
  - German for all new texts; docs describe the colour panel, swatches, library and eyedropper; FEATURE_GAPS P1 colour picker and eyedropper ticked (and the stale Level 5 / drag-and-drop entries corrected); structure trees list the new modules; full suite, ruff, self-test, screenshots en/de
  - Purpose: complete, documented feature
  - _Requirements: all_
  - _Prompt: Implement the task for spec colour-panel, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on docs | Task: Translate, update docs, run all checks; tell the user what to try by hand | Restrictions: British English, hedged wording, no em dashes in user-facing prose | Success: suite green, docs match behaviour. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
