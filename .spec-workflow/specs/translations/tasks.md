# Tasks Document

- [x] 1. Plural formulas and PO parser
  - Files: presstoshape/i18n/__init__.py (empty package marker for now), presstoshape/i18n/plural.py, presstoshape/i18n/po.py, tests/i18n/test_plural.py, tests/i18n/test_po.py, tests/test_architecture.py
  - `PluralRule`, `parse_plural_forms` (recursive descent over gettext's C subset, closure tree, length/depth limits, division by zero → 0); `Entry`, `PoFile`, `PoError`, `parse_po` (msgctxt/msgid/msgid_plural/msgstr[n], multi-line, escapes, comments, fuzzy, obsolete skipped, header, 5 MB limit, line numbers in errors, placeholder check into `ignored`), `write_po`; architecture test: `i18n` layer imports nothing from presstoshape and is allowed everywhere
  - Purpose: safe, strict reading of translation files (Req 4)
  - _Leverage: stdlib only (string.Formatter for placeholder fields)_
  - _Requirements: 3.3, 4.1–4.4, NFR Security_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer focused on parsers and robustness | Task: Implement plural.py and po.py per design.md with the tests listed there (English/German/French/Polish/Russian/Arabic plural tables, malformed formulas, every PO syntax element, errors with line numbers, placeholder rules: singular exact, plural subset, bad braces, format specs) | Restrictions: no eval/exec, no new dependencies, no Qt; speaking names, "type" not "kind" | Success: tests green, architecture test green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Catalog, public calls and language discovery
  - Files: presstoshape/i18n/__init__.py, presstoshape/i18n/catalog.py, presstoshape/i18n/languages.py, tests/i18n/test_catalog.py, tests/i18n/test_languages.py, tests/conftest.py
  - `_`, `ngettext`, `pgettext`, `npgettext`, `N_`, `install`, `active_language`; `Catalog` + `build_catalog` (entry-by-entry priority, per-entry plural rule, English fallback, completeness); `Language`, `available_languages`, `load_catalog` (broken files skipped with log warning), `resolve`, `code_for_import`; an autouse fixture resetting to the identity catalog and a `german` fixture
  - Purpose: lookup and merge order (Req 2.1, 2.5, 3.1–3.3, 3.6)
  - _Leverage: task 1 parser_
  - _Requirements: 2.1, 2.3, 2.5, 3.1, 3.2, 3.3, 3.6, NFR Performance_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement catalog.py, languages.py and the public calls per design.md; tests: identity English, user overrides shipped per entry, fallbacks, contexts, plural selection, completeness, discovery and code validation, broken file skipped, resolve (saved / system exact / by language part / fallback), code_for_import | Restrictions: the active catalog is the only module-level state, set by install; lookups are one dict access; no Qt | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. String extraction and update script
  - Files: scripts/update_translations.py, presstoshape/assets/translations/presstoshape.pot, tests/scripts/test_update_translations.py
  - AST walk of presstoshape/**/*.py for literal arguments of `_`, `N_`, `ngettext`, `pgettext`, `npgettext` with `#:` references; stable, dateless template; merge into shipped .po files (keep translations, add new untranslated, obsolete as `#~`); `--check` mode; non-literal arguments reported as errors; test that the committed template is current and that an f-string argument is reported
  - Purpose: keep template and translations in sync with the source (NFR Code Architecture)
  - _Leverage: task 1 write_po/parse_po, scripts/generate_icons.py as pattern_
  - _Requirements: 3.4 (template), NFR Code Architecture, NFR Reliability_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python tooling developer | Task: Write the script per design.md and its tests; generate the (still nearly empty) template | Restrictions: stdlib only; deterministic output; run with uv run python scripts/update_translations.py | Success: --check passes on the committed template, tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Mark all user-visible strings below views
  - Files: presstoshape/models/app_state.py, presstoshape/formats/*.py, presstoshape/editing/**/*.py, presstoshape/tools/*.py, affected tests
  - `N_()` for registry and tool labels; `_()` / `ngettext()` with named placeholders for status messages, undo labels, tool hints, P2sError and SVG reader notes, default layer names; "object(s)" → real plurals in English; regenerate the template
  - Purpose: everything the Qt-free layers show can be translated (Req 1.1, 1.3, 1.6)
  - _Leverage: task 2 calls, task 3 script_
  - _Requirements: 1.1, 1.3, 1.4, 1.6, 1.7_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer doing a careful mechanical conversion | Task: Convert every user-visible literal below views per design.md ("Converting the source"); update tests that assert "object(s)" wording; regenerate presstoshape.pot | Restrictions: no f-strings inside translation calls; do not translate ids, file keys, log messages, font family or mimetype; keyboard shortcuts unchanged | Success: suite green in English, update script --check passes, no untranslated literal left (grep review). Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Mark all strings in views and app, translate registry labels at use
  - Files: presstoshape/views/*.py, presstoshape/app.py, presstoshape/views/actions.py, presstoshape/views/keymap.py
  - `N_()` for WINDOW_COMMANDS, TITLES, submenu titles; translate labels in AppActions, menus, tool options, edit bar, layers panel, status bar, dialogs (open/save filters, export, about, unsaved changes); regenerate the template
  - Purpose: the Qt side shows translated text (Req 1.1, 1.4)
  - _Leverage: task 2 calls_
  - _Requirements: 1.1, 1.4, 1.5_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Mark and translate every view string per design.md; regenerate the template; screenshot in English unchanged | Restrictions: shortcuts and command ids unchanged; no Qt tr()/QT_TR_NOOP (one mechanism); keep views small | Success: suite green, --check passes, English screenshot looks as before. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. German translation
  - Files: presstoshape/assets/translations/de.po, tests/i18n/test_shipped.py
  - Complete German translation using the design's glossary (Komposit, Ebene, Kontur, Füllung, …), German mnemonics without clashes per menu, `Plural-Forms: nplurals=2; plural=(n != 1);`; test: parses with no ignored entries and 100 % complete; status messages under the `german` fixture
  - Purpose: ship German (Req 1, Usability)
  - _Leverage: task 3 template_
  - _Requirements: 1.1–1.4, NFR Usability_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Native-level German UI translator familiar with vector editors | Task: Translate every template entry following the glossary; keep placeholders; choose unique mnemonics per menu; add the shipped-file tests | Restrictions: established German UI terms, Sie-form avoided in favor of neutral imperative/noun style as in common German software; no em dashes | Success: 100 % complete, no ignored entries, tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Startup: settings, language resolution, Qt translator, locale
  - Files: presstoshape/app.py, presstoshape/views/app_settings.py, presstoshape/views/skia_surface.py, scripts/screenshot_app.py, tests/views/test_app_settings.py
  - `translations_folder`, `language`/`set_language`, `renderer`/`set_renderer`; App resolves the language, installs catalog + `QTranslator(qtbase_<code>)` + `QLocale.setDefault` before creating Session and MainWindow; `use_gpu(preference)` with the env var overriding; `--language` for screenshot and self-test; self-test checks German and qtbase_de; verify the PyInstaller bundle contains Qt's translations (add to datas if the hook doesn't)
  - Purpose: the chosen language and renderer take effect at start (Req 1.2, 1.8, 2.1, 2.2, 2.5, 5.2)
  - _Leverage: views/app_settings.open_settings, task 2 languages_
  - _Requirements: 1.2, 1.6, 1.8, 2.1, 2.2, 2.5, 5.2, NFR Reliability_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement the startup order per design.md; tests for the settings accessors and folder (portable vs installed); screenshot with --language de and read it (text fits in docks, toolbar, menus); self-test passes; check packaging spec for Qt translations | Restrictions: Session created after install; no defensive try/except around Qt calls; startup cost < 50 ms (measure) | Success: German UI on start with LANGUAGE set, numbers with decimal comma, tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. Settings window with Language and Canvas pages
  - Files: presstoshape/views/settings/__init__.py, presstoshape/views/settings/dialog.py, presstoshape/views/settings/pages.py, presstoshape/views/settings/language_page.py, presstoshape/views/settings/canvas_page.py, presstoshape/views/keymap.py, presstoshape/views/main_window.py, presstoshape/icons.py (+ scripts/generate_icons.py mapping if new icons), tests/views/test_settings.py
  - Dialog (category list + stack, Close, Esc, session-remembered category/size), `SettingsPage`/`SettingsContext`/`PAGES`; Language page (combo with native names and completeness, restart note, user translations list with Import/Remove/Open folder/Save template); Canvas page (renderer combo, restart note, env override hint); `edit.settings` window command `Ctrl+,` at the end of the Edit menu
  - Purpose: one place for settings (Req 2.3, 2.4, 3.4, 3.5, 5)
  - _Leverage: task 7 accessors, task 1–2 parsing and discovery, views/icon_engine_
  - _Requirements: 2.3, 2.4, 3.4, 3.5, 5.1–5.6_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 UI developer | Task: Build the dialog and pages per design.md; offscreen tests per the design's integration list; QTest scratch run offscreen and with GL: open via Ctrl+,, keyboard navigation, import valid and invalid files, remove, restart note; screenshot of the dialog in English and German | Restrictions: pages only talk to app_settings and i18n; message boxes for import results; lambda for clicked; delete scratch files one command each | Success: tests green, flows verified on both renderers. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Docs and final check
  - Files: README.md, FAQ.md, CLAUDE.md, docs/translating.md (new), .spec-workflow/steering/tech.md, .spec-workflow/steering/structure.md, FEATURE_GAPS.md (local)
  - How to translate (template from Settings or repo, file naming, folder, import, Poedit), README/FAQ language support (hedged), CLAUDE.md rules (wrap user-visible strings, no f-strings in calls, run update script, i18n module-level exception), steering updates; full suite, self-test, German screenshot, bench_canvas startup unaffected
  - Purpose: translators and contributors know the rules
  - _Requirements: all_
  - _Prompt: Implement the task for spec translations, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on docs | Task: Write docs/translating.md and update the listed docs; run uv run pytest, main.py --self-test, screenshots in en and de | Restrictions: hedged wording, no em dashes in user-facing prose; FEATURE_GAPS.md stays uncommitted | Success: docs match behavior, everything green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
