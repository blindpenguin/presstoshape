# Requirements Document

## Introduction

PressToShape becomes translatable and ships in **English and German**. Users can also **add their own translations**: fix or complete a shipped language, or add a new one. They can drop a file into a translations folder or import it from a Settings window.

To give the language choice, and the many settings still to come, a home, this spec also adds a **Settings window**: a list of categories on the left and the selected category's settings on the right.

Today every piece of UI text is an English literal, spread across views and also across the Qt-free layers:
- menu and operation labels in the registries;
- undo step names;
- status bar messages from operations;
- tool hints;
- error messages when a file can't be read.

All of that has to go through one translation function.

Translation files use the **gettext PO format** (`.po`), the most widely used format for open-source translations:
- it is plain text, editable in any editor;
- dedicated tools (Poedit, Lokalize, Weblate, Crowdin) handle it;
- it supports plural forms, which German status messages need ("1 Objekt" / "3 Objekte").

## Alignment with Product Vision

- **P3 "Localization (UI translations)"** in the feature gap list, and **Customization: preferences** in product.md's enhancements: this spec delivers the base of both.
- **Principle 2, Professional depth, approachable surface**: an app in the user's own language lowers the entry barrier, especially for artists who aren't comfortable in English.
- **Openness and community**: user-provided translation files let the community add languages without a code change or a release. A template file is available from inside the app, so translators don't need the source code.
- **Architecture**: the translation function is Qt-free, so operations and tools stay testable without a display (tech.md / CLAUDE.md layer rules).

## Requirements

### Requirement 1: Translatable user interface

**User Story:** As a user who prefers German, I want the whole interface in German, so that I can work without translating in my head.

#### Acceptance Criteria

1. WHEN German is the active language THEN all PressToShape text SHALL be shown in German:
   - menus, toolbar tooltips, panel titles and labels;
   - tool names and tool hints;
   - dialogs (open/save filters, export, about, unsaved changes);
   - status bar messages, undo/redo step names;
   - error messages for files that can't be opened.
2. WHEN German is active THEN Qt's own built-in texts SHALL also be German (standard dialog buttons such as "Abbrechen", file dialog texts, context menus of text fields), using the Qt translations that ship with PySide6.
3. Messages with counts SHALL use the language's plural rules (German: "1 Objekt kopiert" / "3 Objekte kopiert"), replacing today's "object(s)" wording also in English ("1 object" / "3 objects").
4. Menu mnemonics (the underlined `&` letter) SHALL be part of the translation, so each language can choose its own.
5. Keyboard shortcuts SHALL NOT change with the language.
6. Text stored in documents SHALL NOT be translated after the fact: e.g. a layer named "Layer 1" stays "Layer 1" when the language changes. Newly created defaults (the first layer of a new document, new layers) SHALL use the active language ("Ebene 1").
7. Files PressToShape writes (SVG, `.p2s`, PNG) SHALL NOT depend on the language. Numbers in files keep the `.` decimal separator.
8. Number fields in the UI (spin boxes) SHALL show and accept numbers in the active language's format (German: `2,5`).

### Requirement 2: Choosing the language

**User Story:** As a user, I want to choose the interface language, and have a sensible default on first start.

#### Acceptance Criteria

1. WHEN PressToShape starts for the first time THEN the language SHALL be the operating system's UI language if a translation for it is available, else English.
2. WHEN the user picks a language in Settings THEN it SHALL be saved in the app settings (the registry / `~/.config` / the portable `settings.ini`, as for the window placement) and used from then on.
3. The language list SHALL offer "System default" plus every available language, each by its own name ("Deutsch", "English"), with its completeness in percent for non-English languages.
4. WHEN the user changes the language THEN the Settings window SHALL say that the change takes effect after restarting PressToShape. The running window keeps its language until then.
5. IF the saved language is no longer available (its user file was removed) THEN PressToShape SHALL start in English and SHALL NOT fail.

### Requirement 3: User-provided translation files

**User Story:** As a translator or a user of a language PressToShape doesn't ship, I want to use my own translation file, so that I can use PressToShape in my language or improve an existing translation.

#### Acceptance Criteria

1. PressToShape SHALL read translation files (`<language code>.po`, e.g. `fr.po`, `pt_BR.po`) from a **user translations folder**:
   - next to the settings in installed builds: the platform's app-data location;
   - `translations/` next to the executable in the portable build, so nothing is written outside its folder.
2. WHEN a user file exists for a language PressToShape also ships (e.g. `de.po`) THEN the user file SHALL take precedence entry by entry. Entries it doesn't translate fall back to the shipped translation, then to English.
3. WHEN a translation lacks an entry THEN that text SHALL be shown in English; an incomplete translation is never an error.
4. The Settings window SHALL:
   - **import** a `.po` file chosen in a file dialog: validate it, copy it into the user translations folder, and ask before replacing an existing user file for that language;
   - **remove** an imported user translation, after confirmation;
   - **open the user translations folder** in the system file manager;
   - **save a translation template** (`presstoshape.pot`) that lists every translatable text, so translators can start a new language without the source code.
5. WHEN a user file is imported or removed THEN the language list SHALL update immediately; using the language still needs a restart (Requirement 2.4).
6. The language code SHALL come from the file name; the shown name comes from the system's locale names (e.g. `fr` → "Français"), so translators don't have to provide it.

### Requirement 4: Robust handling of translation files

**User Story:** As a user, I want a broken or malicious translation file to never break PressToShape.

#### Acceptance Criteria

1. Translation files SHALL be treated as text data only: nothing in them is executed, and files over a sane size limit are refused.
2. WHEN a file can't be parsed as PO THEN import SHALL refuse it with a message naming the line, and a broken file already in the folder SHALL be skipped at startup (with a log entry), with the language falling back as in Requirement 3.3.
3. WHEN a translated entry's placeholders don't match the original (e.g. `{count}` missing, or an unknown `{name}`) THEN that entry SHALL be ignored and the English text used, so a typo in a translation can never crash a message. Import SHALL report how many entries were ignored and why.
4. Plural forms SHALL be read from the file's `Plural-Forms` header. IF the header is missing or invalid THEN the file SHALL be refused on import (and skipped at startup); the plural formula SHALL be evaluated safely, never with `eval`.

### Requirement 5: Settings window

**User Story:** As a user, I want one place for PressToShape's settings, organized by category, so that I find options without searching through menus.

#### Acceptance Criteria

1. WHEN the user chooses Edit → Settings… (`Ctrl+,`) THEN a Settings window SHALL open with a list of categories on the left and the selected category's page on the right.
2. The first version SHALL have these categories:
   - **Language**: language choice (Requirement 2) and translation management (Requirement 3.4).
   - **Canvas**: renderer choice "Automatic / GPU (OpenGL) / CPU", which today is only reachable through the `PRESSTOSHAPE_RENDERER` environment variable; takes effect after a restart. The environment variable keeps overriding the setting.
3. Settings SHALL apply when changed (no OK/Apply step); the window has a Close button. Settings that need a restart SHALL say so next to the control.
4. The window SHALL remember the last selected category and its size during the session.
5. The categories SHALL be defined so a later feature adds a category by adding one page, without changing the window (e.g. units, nudge distance, autosave, shortcuts).
6. The window SHALL be usable by keyboard only: Up/Down in the category list, Tab into the page, Esc closes.

## Non-Functional Requirements

### Code Architecture and Modularity
- **One Qt-free translation module** importable from every layer, with the usual gettext-style calls:
  - `_("text")`;
  - `ngettext("singular", "plural", n)`;
  - a context variant for short, ambiguous words (e.g. "Add" as a mode vs. as a command).
- Registries keep **untranslated source strings** and translate when building menus and messages, so the active language is looked up at use time, not at import time.
- PO parsing, plural formulas and file discovery are plain Python, unit-tested without Qt. Only the Settings window, `QTranslator` for Qt's own strings, `QLocale` for number formats and the folder/file dialogs are in `views/`.
- Extraction of translatable strings into the `.pot` template is a script (`scripts/`), run like `generate_icons.py`. A test fails when the committed template is out of date with the source.
- The English text in the source stays the source of truth. The shipped German file is `presstoshape/assets/translations/de.po`.

### Performance
- Loading translations SHALL add less than 50 ms to startup.
- A translation lookup SHALL be a dictionary access; no per-call file or locale work.

### Security
- PO files are parsed by a small, strict parser with size limits; no `eval`; the plural formula has its own safe evaluator for the C-expression subset gettext allows.
- Imported files are copied (not linked) into the translations folder under a sanitized name derived from the language code; path components in the chosen name are ignored.

### Reliability
- Tests:
  - every shipped translation parses;
  - placeholders match;
  - plural rules are correct for English and German;
  - user files override entry by entry;
  - broken files are skipped;
  - the template contains every string the source passes to the translation functions.
- The packaged build includes the shipped translations and Qt's `qtbase_de.qm`; `--self-test` checks that German loads.

### Usability
- The German translation SHALL be complete at release and use the established German terms of vector editors (e.g. Ebene, Pfad, Kontur, Füllung). A Composite is a **Komposit** in German. The design lists the full glossary.
- Out of scope:
  - switching the language without a restart;
  - right-to-left layouts;
  - translating the README, FAQ and docs;
  - online translation platforms (Weblate) setup;
  - more settings than the two categories above.
