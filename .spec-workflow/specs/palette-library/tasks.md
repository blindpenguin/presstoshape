# Tasks Document

- [x] 1. Palette model and collection operations
  - Files: presstoshape/models/colours.py, presstoshape/editing/operations/palettes.py, presstoshape/editing/operations/__init__.py, presstoshape/editing/operations/swatches.py, presstoshape/editing/operations/colours.py, tests/editing/test_palettes.py, tests/editing/test_swatches.py
  - `Palette`; `ColourState.palettes` / `current_palette` replacing `library`; `unique_name`, `new_palette`, `rename_palette`, `duplicate_palette`, `delete_palettes`, `set_palette_order`, `set_current_palette`, `set_palettes`; swatch operations: `"library"` = current palette (created as "My swatches" on demand), optional `palette_id`
  - Purpose: the collection as plain data and operations (Req 1, 3.3–3.4)
  - _Leverage: swatches._change, its library id counter_
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.3, 3.4_
  - _Prompt: Implement the task for spec palette-library, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer familiar with the session/operations architecture | Task: Implement per design.md "Model" and "Operations" (without import); tests per Testing Strategy; keep existing swatch tests passing with the library meaning the current palette | Restrictions: no Qt; notify once per operation; no undo steps for palettes | Success: full suite green except views that still use `library` (fixed in task 4/5), ruff clean. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Import planning and palette names from files
  - Files: presstoshape/editing/operations/palettes.py, presstoshape/formats/palettes.py, tests/editing/test_palettes.py, tests/formats/test_palettes.py
  - `ImportItem`, `Choice`, `ImportCounts`, `clashes`, `apply_import`; `read_named_palette` (GIMP `Name:` / `#Palette Name:`, Paint.NET `;Palette Name:`)
  - Purpose: batch import logic without dialogs (Req 4.2, 4.3, 4.6)
  - _Leverage: unique_name, read_palette_
  - _Requirements: 4.2, 4.3, 4.6_
  - _Prompt: Implement the task for spec palette-library, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement per design.md "Import" and "Reading names from files"; tests: clashes against existing and within the batch, keep/replace/skip incl. replacing an earlier batch item, counts, first import becomes current, names per format incl. Lospec | Restrictions: no Qt, one notify | Success: tests green, ruff clean. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Palette files and the store
  - Files: presstoshape/formats/palette_files.py, presstoshape/views/palette_store.py, presstoshape/views/app_settings.py, tests/formats/test_palette_files.py, tests/views/test_palette_store.py
  - Codec (palette JSON, index, `file_name`), `PaletteStore.load/save` (order, unknown files, damaged files untouched, changed-only writes, deletes), migration from `swatches.json` → "My swatches" + `swatches.migrated.json`; `app_settings.palettes_folder`, current palette name setting
  - Purpose: one file per palette, safely (Req 1.5, 6)
  - _Leverage: swatch_library validation, documents.write_atomically, app_settings._data_folder_
  - _Requirements: 1.5, 6.1, 6.2, 6.3, 6.4_
  - _Prompt: Implement the task for spec palette-library, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced in file handling | Task: Implement per design.md "Storage"; tests with tmp_path for every rule in Req 6 and the migration; measure loading 500 palettes | Restrictions: codec Qt-free in formats; I/O in views; never touch the real data folder in tests | Success: tests green, ruff clean, 500 palettes load < 200 ms. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Import and export flows
  - Files: presstoshape/views/palette_import.py, presstoshape/views/palette_export.py, presstoshape/views/colour_panel.py (move `_read_palette_file` and export code out), tests/views/test_palette_import.py, tests/views/test_palette_export.py
  - selected files (1000 limit; folder import dropped after review), `read_items` (progress dialog, 1024-colour cap, failures), `ClashDialog`, summary, `import_palettes(parent, session, paths)`; `export_one`, `export_many` (folder, format choice, one replace question)
  - Purpose: the dialogs both the panel and Settings use (Req 4, 5)
  - _Leverage: formats.palettes, palette_files.file_name, panel import/export code_
  - _Requirements: 4.1, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3_
  - _Prompt: Implement the task for spec palette-library, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement per design.md "Import flow" and "Export"; tests with a temp folder of Lospec-style files: folder recursion and limit, failures listed, clash dialog choices (Keep/Replace/Skip all, per row, cancel), export of several files with existing-file question | Restrictions: views only; plain values into operations; no try/except around Qt calls, only file I/O | Success: tests green, ruff clean. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Settings Palettes page and Colour panel Library tab
  - Files: presstoshape/views/settings/palettes_page.py, presstoshape/views/settings/pages.py, presstoshape/views/settings/dialog.py, presstoshape/views/colour_panel.py, presstoshape/views/main_window.py, presstoshape/icons.py, scripts/generate_icons.py, presstoshape/assets/icons, tests/views/test_palettes_page.py, tests/views/test_colour_panel.py, tests (MainWindow callers: `palettes_folder`)
  - Palettes page (list with counts, multi-select, drag reorder, buttons, preview with swatch context menu, Open Palettes Folder); `SettingsContext.session` / `palettes_folder`; Library tab dropdown, menu, empty state, Manage Palettes → `open_settings(page)`; MainWindow uses `PaletteStore` (load at start with problems shown once, save on change, current palette name)
  - Purpose: the user-facing feature (Req 2, 3)
  - _Leverage: SettingsPage/PAGES, SwatchGrid, existing panel tab code_
  - _Requirements: 2.1–2.5, 3.1–3.5, 6.5_
  - _Prompt: Implement the task for spec palette-library, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement per design.md "Settings page" and "Colour panel Library tab"; tests for buttons, reorder, delete confirmation, preview actions, dropdown, empty state, Manage Palettes page; scratch script offscreen: batch import of 500 generated files with clashes, load time, screenshots of the page and tab in English and German read by eye | Restrictions: blockSignals on refresh; tests/screenshots pass their own palettes folder | Success: suite green incl. mnemonic tests. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. Translations, docs and final check
  - Files: presstoshape/assets/translations/*, README.md, FAQ.md (if it mentions the library), FEATURE_GAPS.md, .spec-workflow/steering/structure.md, .spec-workflow/steering/product.md, CLAUDE.md
  - German for all new texts; docs describe palettes, Settings page, batch import and the palettes folder; structure trees list the new modules; CLAUDE.md: tests pass `palettes_folder`; full suite, ruff, self-test
  - Purpose: complete, documented feature
  - _Requirements: all_
  - _Prompt: Implement the task for spec palette-library, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on docs | Task: Translate, update docs, run all checks; tell the user what to try by hand | Restrictions: British English, hedged wording | Success: suite green, docs match behaviour. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
