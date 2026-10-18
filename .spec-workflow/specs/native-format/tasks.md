# Tasks Document

- [x] 1. Shape and document encoders/decoders
  - Files: presstoshape/formats/p2s.py, tests/formats/test_p2s.py
  - Explicit per-type encode/decode for rect, ellipse, path (compact segment arrays), text, composite (parts + modes), style, transform (omitted when identity), layers, document; validation (types, finite numbers, known types/modes) raising `P2sError("damaged: <json path>")`
  - Purpose: exact, explicit document representation (Req 1.2, 1.3)
  - _Leverage: models/shapes.py, models/app_state.py_
  - _Requirements: 1.2, 1.3, 5.2_
  - _Prompt: Implement the task for spec native-format, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer focused on file formats | Task: Write the encoders/decoders per design.md (document.json section) with round-trip tests over every shape type, nested composites, transforms, None fill/stroke, hidden/empty layers, and failure tests naming the failing path | Restrictions: formats imports only models and geometry; no reflection over dataclass fields; speaking names, "type" not "kind" | Success: round trips equal, failures give readable P2sError. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Archive, SavedState, versioning and migrations
  - Files: presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, tests/formats/test_p2s.py, tests/formats/test_p2s_migrations.py, tests/formats/samples/v1.p2s
  - `SavedState`; `write_p2s(document, state, preview, app_version) -> bytes` (mimetype first and stored, document.json deflate, optional preview.png); `read_p2s(data) -> (Document, SavedState)` with name-only reads, size limits, version check, `upgrade()` chain; committed v1 sample file
  - Purpose: the container and its long-term compatibility (Req 2.1, 4, 5.3, 6.2, 6.4)
  - _Leverage: task 1 encoders_
  - _Requirements: 2.1, 4.1–4.4, 5.2, 5.3, 6.2, 6.4_
  - _Prompt: Implement the task for spec native-format, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer focused on file formats and robustness | Task: Implement the archive layer per design.md; tests: byte-stable save→open→save of document.json, every SavedState field, not-a-zip, wrong mimetype, newer version message, oversized entry (crafted archive), unknown extra entries ignored, v1 sample opens to the expected document | Restrictions: stdlib only; never extract to disk; limits checked while reading in chunks | Success: all tests green, sample committed. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Open/save operations: dispatch, atomic save, working state, preview
  - Files: presstoshape/editing/operations/documents.py, presstoshape/models/app_state.py, tests/editing/test_documents.py
  - Extension dispatch; atomic write (temp file in same folder, fsync, os.replace, cleanup on error); preview via render_png at ≤256 px; apply SavedState on open (tool styles, font size, new-part mode, zoom, restore_view_center, filtered selection/edit path); `save_file(..., view_center=None)`; `svg_hint_shown` status hint on first SVG save
  - Purpose: the user-facing behavior below views (Req 1, 2, 3.2–3.4, 5.1)
  - _Leverage: containers.valid_edit_path, queries.pickable_shapes, render/export.render_png, version.app_version_
  - _Requirements: 1.1, 1.4, 2.1–2.5, 3.2–3.4, 5.1, 5.2, 6.1_
  - _Prompt: Implement the task for spec native-format, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Extend documents.py per design.md; tests: dispatch by extension, atomic save keeps the old file on a failing write (monkeypatch), state restored and stale ids dropped, SVG hint once per session, opened SVG keeps saving SVG, undo history cleared and not dirty after open/save | Restrictions: operations take plain values; editing passes app_version into formats (formats can't import version) | Success: tests green, architecture test green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Dialogs, view restore and self-test
  - Files: presstoshape/views/main_window.py, presstoshape/views/canvas_view.py, presstoshape/app.py
  - Open filter (*.p2s *.svg) plus per-type filters; Save As types with extension from the selected filter; default name untitled.p2s; `CanvasView.view_center()` / `center_on(point)`; open_document restores or fits; save passes view_center; self-test adds a .p2s round trip
  - Purpose: complete UI flow (Req 1.1, 1.5, 2.2, 3.1)
  - _Leverage: task 3 operations, existing fit_artboard/center_artboard_
  - _Requirements: 1.1, 1.5, 2.2, 3.1_
  - _Prompt: Implement the task for spec native-format, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Wire dialogs and view restore per design.md; QTest scratch run offscreen and on the desktop: draw, zoom/scroll, select, enter a Composite, Save As .p2s, New, Open → same view, selection, edit bar; Save As .svg shows the hint once | Restrictions: views only offer dialogs and pass plain values; lambda for triggered/clicked; delete scratch files one command each | Success: flow verified on both renderers, self-test passes. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Format description, docs and final check
  - Files: docs/file-format.md, README.md, FAQ.md, CLAUDE.md, .spec-workflow/steering/tech.md, .spec-workflow/steering/structure.md
  - Format description (archive layout, every field, version history, migration rule); README/FAQ save flow and "own file format: yes, .p2s" (hedged); CLAUDE.md rule: every stored change bumps the format version with a migration and a sample; steering updates; check a saved file with unzip -l and json.tool against the doc; full suite and screenshot
  - Purpose: openness and truthful docs (Req 6.3)
  - _Requirements: 4.4, 6.3_
  - _Prompt: Implement the task for spec native-format, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on docs | Task: Write docs/file-format.md from the real output, update docs per design.md, run the final checks | Restrictions: hedged wording; no em dashes in user-facing prose; cleanup one command per deletion | Success: doc matches real files, suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
