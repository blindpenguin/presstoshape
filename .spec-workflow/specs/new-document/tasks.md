# Tasks Document

- [x] 1. Units, document fields and presets
  - Files: presstoshape/geometry/units.py, presstoshape/models/app_state.py, presstoshape/models/document_presets.py, tests/geometry/test_units.py, tests/models/test_document_presets.py
  - `Unit` literal and `Document.unit`/`dpi` (defaults px/96); `UNITS`, `PER_INCH`, `DECIMALS`, `MIN_DPI`/`MAX_DPI`, `MAX_DOCUMENT_PX`, `to_px`, `from_px`, `convert`; `DocumentPreset`, `PRESETS` (Requirement 2.1 list), `DEFAULT`
  - Purpose: the pure base everything else converts with (Req 2.1, 3.2, 6.1)
  - _Leverage: models/app_state.py, i18n.N__
  - _Requirements: 2.1, 2.3, 3.2, 3.3, 6.1_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement units, document fields and presets per design.md; tests: A4 at 72/96/300 DPI, in/mm/pt/cm conversions and round trips, px identity; presets have unique ids, fit limits, print presets portrait | Restrictions: no Qt; models hold data only (conversion math in geometry); preset names and categories N_()-marked; British English | Success: tests green, architecture test green, existing tests unchanged. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. new_document operation with a setup
  - Files: presstoshape/editing/operations/documents.py, tests/editing/test_documents.py
  - `DocumentSetup`, `DEFAULT_SETUP`; `new_document(session, setup=DEFAULT_SETUP)` validates, converts to px, creates the sized document via `_reset` (not dirty, history cleared)
  - Purpose: one operation creates documents from the dialog or the default (Req 1.3, 1.5, 1.7, 3.5)
  - _Leverage: task 1 units, documents._reset_
  - _Requirements: 1.3, 1.5, 1.7, 3.5_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement per design.md with tests (A4 300 DPI → 2480.31 px wide, unit/dpi set, default unchanged, invalid setups raise ValueError) | Restrictions: operations take plain values; no Qt | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. .p2s format version 2
  - Files: presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, tests/formats/test_p2s.py, tests/formats/test_p2s_migrations.py, tests/formats/samples/v2.p2s, docs/file-format.md
  - Encode/decode `unit` and `dpi` (validated); `CURRENT_VERSION = 2`; migration 1 → 2 adds px/96; v2 sample; file-format doc updated (fields, version table)
  - Purpose: native files keep unit and DPI (Req 7.1)
  - _Leverage: existing codecs, migration rule, v1 sample_
  - _Requirements: 7.1, NFR Reliability_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer focused on file formats | Task: Follow the native format rules in CLAUDE.md and docs/file-format.md; tests: v2 round trip, v1 sample opens as px/96, v2 sample opens, bad unit/DPI refused | Restrictions: explicit codecs; generate the v2 sample with a small committed-free script, check it into tests/formats/samples | Success: tests green, doc matches real output. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. SVG keeps the physical size
  - Files: presstoshape/formats/svg.py, tests/formats/test_svg.py
  - Write width/height in the document unit (plain px for px documents), viewBox in document pixels, `presstoshape:unit`/`presstoshape:dpi`; read: own attributes exactly, else physical units with density rule (≥ 72 keep coordinates, else scale content to 96 DPI through the base matrix), else px/96
  - Purpose: interop with real sizes (Req 7.2–7.4)
  - _Leverage: _document_frame, _Reader base matrix, PRESSTOSHAPE_NS_
  - _Requirements: 7.2, 7.3, 7.4_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer focused on SVG interop | Task: Implement per design.md; tests: physical units written, exact own round trip, Inkscape-style mm document (viewBox in mm) opens as mm scaled to 96 DPI with stroke widths scaled and same physical size on export, 300 DPI viewBox keeps coordinates, px files unchanged, clipboard SVG unaffected | Restrictions: formats uses only models, geometry, i18n; keep svg.py split in mind (it's past 400 lines; moving the reader into its own module is fine if it helps) | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. PNG export in DPI
  - Files: presstoshape/render/export.py, presstoshape/views/export_dialog.py, presstoshape/models/app_state.py (ExportSettings), presstoshape/editing/operations/documents.py, tests/render/test_export.py
  - `render_png(doc, scale, dpi=None)` writes a pHYs chunk; export dialog with linked DPI ↔ Scale (default doc DPI); export operation passes the DPI
  - Purpose: print documents export at their resolution (Req 8)
  - _Leverage: render_png, ExportPngDialog_
  - _Requirements: 8.1, 8.2, 8.3_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python/PySide6 developer | Task: Implement per design.md; tests: pHYs present with pixels per metre = DPI / 0.0254, PNG still valid (Pillow or skia decode), size from DPI; dialog linking checked offscreen | Restrictions: stdlib zlib for CRC; no new dependencies | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. Lengths in the document unit in the panels
  - Files: presstoshape/views/unit_fields.py, presstoshape/views/selection_view.py, presstoshape/views/style_editor.py, presstoshape/views/tool_options_view.py, tests/views/test_unit_fields.py
  - Spin box helper (decimals, suffix, range, px ↔ unit); selection X/Y/W/H/centre/radius and stroke width in the document unit; tool style stroke width likewise; font size in pt for physical units, px for px documents; reconfigure on unit/DPI change
  - Purpose: users read and type their unit (Req 6.2–6.4)
  - _Leverage: task 1 units, existing spin boxes_
  - _Requirements: 6.2, 6.3, 6.4_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement per design.md; offscreen test: rectangle in an A4 300 DPI mm document shows 210 mm, typing 100 mm stores 1181.1 px; px documents look exactly as before (screenshot) | Restrictions: operations keep receiving document pixels; blockSignals while writing values back; translatable suffixes not needed (unit symbols are international) | Success: tests green, px screenshot unchanged. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Recent files and start settings
  - Files: presstoshape/views/app_settings.py, presstoshape/views/settings/general_page.py, presstoshape/views/settings/dialog.py, presstoshape/views/keymap.py, presstoshape/views/menu_bar_view.py, presstoshape/views/main_window.py, presstoshape/icons.py (+ generate_icons.py if new icons), tests/views/test_recent_files.py, tests/views/test_settings.py
  - Accessors (recent list with pure `updated_recent`, show-start-dialog, last new-document setup); General settings page first in PAGES; File → Open Recent dynamic submenu (numbered entries, Clear, disabled empty entry); `MainWindow.open_path` shared by Open/Open Recent, recent list updated on open and save, missing entries removed with a status message
  - Purpose: Req 4.4, 4.5, 5
  - _Leverage: app_settings accessors pattern, settings pages, open_document_
  - _Requirements: 4.4, 4.5, 5.1–5.5_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement per design.md; tests: updated_recent moves to top/dedupes/limits, accessors survive bad values, General page toggles the setting, Open Recent menu content (offscreen) | Restrictions: no shortcuts for recent entries (CLAUDE.md shortcut rule); paths stored absolute; lambda for triggered | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. New Document dialog, startup and New
  - Files: presstoshape/views/new_document_dialog.py, presstoshape/views/main_window.py, presstoshape/app.py, presstoshape/icons.py (+ generate_icons.py: portrait/landscape icons), tests/views/test_new_document_dialog.py
  - Dialog per design (preset tree, form, hint, validation, orientation, startup-only recent list, Open…, show-at-startup); `MainWindow.new_document` and `show_start_dialog` flows (confirm discard after Create, cancel behaviour, Open… returning to the dialog, recent errors in place); App schedules the start dialog
  - Purpose: Req 1–4
  - _Leverage: tasks 1, 2, 7; fit_artboard; _confirm_discard_
  - _Requirements: 1.1–1.7, 2.2, 2.4, 3.1–3.6, 4.1–4.3, 4.5_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 UI developer | Task: Build the dialog and flows per design.md; offscreen tests per the design's integration list; QTest scratch run on the real window offscreen and with GL (startup dialog over the window, A4 → fitted, New → Cancel no change, unsaved changes asked after Create, recent file opens, missing recent shows error, show-at-startup off → no dialog); screenshots in English and German | Restrictions: no new shortcuts; dialog collects values only, document creation via documents.new_document; keep the file under ~400 lines (split the startup part into its own widget if needed); delete scratch files one command each | Success: tests green, flows verified on both renderers. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Translations, docs and final check
  - Files: presstoshape/assets/translations/presstoshape.pot, presstoshape/assets/translations/de.po, README.md, FAQ.md, CLAUDE.md, .spec-workflow/steering/*.md, FEATURE_GAPS.md (local)
  - Regenerate template, complete German; README/FAQ (new-document dialog, units, recent files, Inkscape size interop, hedged); CLAUDE.md (document coordinates are document pixels, units only at the view boundary); steering updates; full suite, self-test, screenshots en/de
  - Purpose: complete and documented feature
  - _Requirements: all_
  - _Prompt: Implement the task for spec new-document, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on docs and release quality | Task: Translate new texts (German complete), update docs per this task, run uv run pytest, main.py --self-test, screenshots; list manual checks for the user (Inkscape A4 round trip) | Restrictions: British English, hedged wording, no em dashes in user-facing prose; FEATURE_GAPS.md stays uncommitted | Success: suite green, docs match behaviour. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
