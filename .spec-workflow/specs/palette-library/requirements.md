# Requirements Document

## Introduction

Today the personal swatch library is one palette. This spec turns it into a **collection of named palettes**, kept one file per palette in the app's data folder, and adds a **Palettes** category to the Settings window to manage them: import single files, **batch import** many files at once (for example a set of palettes downloaded from Lospec), rename, duplicate, delete, reorder, preview and export. The Colour panel's Library tab shows one palette at a time, picked from a dropdown.

It builds on spec `colour-panel` (swatches, library, palette file formats). Palette files are read with the formats added there (GIMP `.gpl`, `.hex`, JASC `.pal`, Paint.NET `.txt`, PNG palette images). Nothing is fetched from the internet.

## Alignment with Product Vision

- **Pillar 2, Rich paint** and **Potential Enhancements "swatches and color libraries"**: a real palette collection, as Illustrator's swatch libraries, Affinity's palettes and Krita's resource manager offer.
- **Principle 1, Artists first**: pixel and illustration artists collect many palettes (Lospec); importing a folder of them in one go and switching between them in the panel keeps them at hand.
- **Principle 2, approachable surface**: the panel stays simple (one dropdown); managing many palettes happens in Settings, where it doesn't crowd the canvas.
- **Offline by principle**: palettes come from files the user chose; nothing is downloaded.

## Requirements

### Requirement 1: A collection of named palettes

**User Story:** As an artist, I want several named palettes instead of one library, so that I can keep palettes for different projects and styles apart.

#### Acceptance Criteria

1. The library SHALL be an ordered collection of palettes; each palette SHALL have a name (not empty, unique in the collection, compared without regard to case) and an ordered list of swatches (name, colour, opacity) as library swatches have today.
2. One palette SHALL be the **current palette**: the one the Library tab shows and adds to. The choice SHALL be remembered between runs.
3. WHEN the collection is empty and a swatch is added to the library (the "+" cell, "Add to Library") THEN a palette named "My swatches" (translated) SHALL be created and become current.
4. Palette changes SHALL not be undo steps (as library changes today); destructive ones (delete palette, replace on import) SHALL ask first.
5. WHEN the app starts for the first time after this change and the old single library file (`swatches.json`) exists THEN its swatches SHALL become a palette "My swatches", and the old file SHALL be kept, renamed, not deleted.

### Requirement 2: Library tab in the Colour panel

**User Story:** As an illustrator, I want to switch between my palettes right in the Colour panel, so that I can pick colours from any of them while I draw.

#### Acceptance Criteria

1. The Library tab SHALL show a dropdown of all palettes in collection order above the swatch grid; choosing one makes it the current palette.
2. Clicking, right-clicking and the "+" cell SHALL work on the current palette as the library does today (apply, rename, replace, move, delete, copy to document).
3. "Add to Library" on a document swatch SHALL add it to the current palette.
4. The tab's `…` menu SHALL offer **New Palette…**, **Rename Palette…**, **Import Palettes…** (as Requirement 4), **Export Palette…** (the current one) and **Manage Palettes…**, which opens Settings on the Palettes page.
5. With no palettes, the tab SHALL show a short note with **New Palette…** and **Import Palettes…** instead of an empty grid.

### Requirement 3: Palettes page in Settings

**User Story:** As a user with many palettes, I want one place to see and tidy them, so that the panel's dropdown stays useful.

#### Acceptance Criteria

1. The Settings window SHALL have a **Palettes** category listing all palettes in collection order with their swatch count; several can be selected.
2. Selecting one palette SHALL show its swatches as a preview grid with the same tooltips as the panel. In the preview, swatches can be renamed, moved and deleted through their context menu; picking and replacing colours stays in the Colour panel, where the picker is.
3. The page SHALL offer: **New**, **Rename** (one selected), **Duplicate** (one selected, named "`<name> copy`"), **Delete** (all selected, after confirming with their names and count), **Import…**, **Export…** and **Open Palettes Folder** (the folder in the system file manager).
4. Palettes SHALL be reorderable by dragging in the list; the order is the panel dropdown's order.
5. Changes SHALL apply immediately, as every other Settings page does, and the Colour panel SHALL follow while the Settings window is open.

### Requirement 4: Import and batch import

**User Story:** As a pixel artist, I want to import a whole set of palettes at once, so that I don't import forty files one by one.

#### Acceptance Criteria

1. **Import…** SHALL accept one or several files at once (multi-selection in the file dialog) in any supported palette format. (Changed after implementation review: no separate folder import; selecting many files covers batch import.)
2. Each file SHALL become its own palette. Its name SHALL be the name stored in the file (GIMP `Name:` or Lospec's `#Palette Name:`, Paint.NET `;Palette Name:`), else the file name without extension.
3. IF imported names clash with existing palettes or with each other THEN, before anything is changed, a dialog SHALL list every clash and let the user choose per palette **Keep both** (the new one gets a number: "PICO-8 (2)"), **Replace** (the existing palette's swatches are replaced, its place in the order kept) or **Skip**, with buttons to apply one choice to all, and **Cancel** to import nothing.
4. Files that can't be read SHALL not stop the others; after a batch the user SHALL see a summary: how many palettes were imported, replaced and skipped, and which files failed with the reason.
5. A batch SHALL be limited to 1000 files and each palette to 1024 swatches; a selection with more files SHALL be refused with a message rather than imported in part.
6. Imported palettes SHALL be added at the end of the collection; the first one becomes current if the collection was empty.

### Requirement 5: Export

**User Story:** As a user, I want to export palettes to share them or use them in other programs.

#### Acceptance Criteria

1. Exporting one palette SHALL ask for a file and a format (`.gpl`, `.hex`, `.pal`, `.txt`, as today), proposing the palette's name as the file name.
2. Exporting several palettes SHALL ask for a folder and one format, and write one file per palette named after it (characters that file names can't hold replaced). IF files of those names exist THEN the user SHALL be asked once whether to replace them or cancel.
3. The palette's name SHALL be written into formats that hold one (GIMP, Paint.NET).

### Requirement 6: Storage

**User Story:** As a user, I want my palettes kept safely and in a form I can back up, so that a crash or a bad file never costs me all of them.

#### Acceptance Criteria

1. Palettes SHALL be stored in a `palettes` folder in the app's data folder (next to `settings.ini` for portable builds), one file per palette, plus a small index file holding the collection order.
2. Writing SHALL be atomic per file, and only palettes that changed SHALL be rewritten.
3. A palette file that can't be read SHALL be left untouched and out of the collection, and the user SHALL be told once at start which files were skipped; the other palettes load normally.
4. Palette files found in the folder but missing from the index (for example copied in from a backup) SHALL be loaded and added at the end; index entries without a file SHALL be dropped.
5. Tests, screenshots and the self-test SHALL never touch the user's palettes folder.

## Non-Functional Requirements

### Code Architecture and Modularity
- The palette collection is plain data in `models/colours.py` (replacing the single `library` tuple), changed only by operations in `editing/operations/` (Qt-free, unit-tested): create, rename, duplicate, delete, reorder, set current, add swatches, import plans (name clash detection and resolution as data).
- The palette file codec and the folder index are Qt-free in `formats/`; file and folder I/O happens in views, as for the library file today.
- The Settings page is one `SettingsPage` subclass; the clash dialog and the summary are their own small view modules.

### Performance
- Starting the app with 500 stored palettes SHALL add no noticeable delay (target under 200 ms to load them); the panel dropdown and the Settings list stay responsive with that many.
- A batch import of 500 Lospec files SHALL finish within a few seconds and show progress if it takes longer than a second.

### Reliability
- No palette data is lost by a failed write, a damaged file, or cancelling a dialog; the migration keeps the old library file.

### Usability
- All texts translated (German); British English source. No new keyboard shortcuts.
- **Out of scope**: online palette sources, palette folders/groups inside the collection, linked (global) swatches, editing colours in Settings (picking stays in the Colour panel), sorting palettes or swatches automatically, Adobe `.ase`/`.aco`.
