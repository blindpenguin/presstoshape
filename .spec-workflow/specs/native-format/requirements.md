# Requirements Document

## Introduction

PressToShape gets its own file format, **`.p2s`**, so that a saved drawing reopens exactly as it was left: every shape, style, transform, layer and Composite. On top of that it stores the working state that SVG can't hold: view (zoom and scroll), the drawing tools' styles and settings, the selection and the entered Composite.

A `.p2s` file is a **ZIP archive** with:

- a type marker
- the document as **JSON**
- a small preview image
- room for embedded resources later (images, fonts, brushes)

That keeps it easy to inspect and debug, and gives a clear path for versioning.

The native format becomes the default for saving. SVG stays fully supported for exchange: open, Save As, and Ctrl+S on a file that was opened as SVG.

## Alignment with Product Vision

- **Principle 4, Own format for fidelity, SVG for exchange**: "the native format stores everything PressToShape supports without compromise". This spec creates that format now, while the model is still small, so every later feature (gradients, brushes, effects, symbols) gets a lossless home from day one.
- **Reliability metric**: "no data loss: every edit undoable, native format reloads exactly what was saved". The round trip is exact by requirement and by test.
- **tech.md, Data Storage**: "versioned with forward migration, exact reload of what was saved, able to embed resources". ZIP + JSON was one of the two candidates named there.
- **Principle 5, Inkscape interop**: unchanged; SVG open/save keeps working, including Composites.

## Requirements

### Requirement 1: Save and open `.p2s`

**User Story:** As an artist, I want to save my work in PressToShape's own format and reopen it exactly as it was, so that nothing I made gets lost or changed.

#### Acceptance Criteria

1. WHEN the user saves a new, never-saved document (File → Save, Ctrl+S) THEN the system SHALL ask for a file name with `.p2s` as the default type and write a `.p2s` file.
2. WHEN a `.p2s` file is opened THEN the document SHALL be identical to the one saved:
   - artboard size
   - layers (name, visibility, order)
   - every shape with its type, geometry, transform, style and id
   - path segments
   - text content and size
   - Composites with their parts, modes and nesting
3. WHEN a document is saved and reopened any number of times without edits THEN the saved content SHALL NOT drift. Numbers are stored exactly as in memory, with no rounding.
4. WHEN a `.p2s` file is opened or saved THEN the window title, dirty flag, status message and undo history SHALL behave as they do for SVG today: a fresh undo history after opening, not dirty after saving.
5. WHEN the user opens a file (File → Open) THEN the dialog SHALL show `.p2s` and `.svg` together by default, plus a filter for each type.

### Requirement 2: Working state in the file

**User Story:** As an artist, I want to continue exactly where I stopped, so that reopening a file doesn't cost me time finding my place and settings again.

#### Acceptance Criteria

1. WHEN a `.p2s` file is saved THEN it SHALL store:
   - the **view**: zoom level and scroll position
   - the **tool settings**: each drawing tool's style, font size and new-part mode
   - the **selection**
   - the **entered Composite path** (edit mode)
2. WHEN a `.p2s` file is opened THEN the system SHALL restore that state. The view SHALL show the same document area at the same zoom, adjusted if the window is a different size. A selection or edit path that no longer matches the document (e.g. hand-edited file) SHALL be dropped rather than causing an error.
3. Changes to working state only (zooming, selecting, entering a Composite, changing tool styles) SHALL NOT mark the document dirty, as today; they are saved with the next save.
4. The undo history SHALL NOT be stored.
5. The active tool SHALL NOT be stored; the app opens with the Select tool, as today.

### Requirement 3: Save flow between `.p2s` and SVG

**User Story:** As a user exchanging files with other tools, I want SVG to keep working naturally, while the native format is the default for my own work.

#### Acceptance Criteria

1. WHEN the user chooses File → Save As THEN the dialog SHALL offer "PressToShape (*.p2s)" (default) and "SVG (*.svg)". The chosen type, or the extension typed by the user, SHALL decide the format. A name without an extension SHALL get the extension of the selected type.
2. WHEN a document was opened from an SVG file, or last saved as SVG, AND the user presses Ctrl+S THEN the system SHALL save SVG to that file again (as today).
3. WHEN a document is saved as SVG for the first time in a session THEN the status bar SHALL say once that view, tool settings and selection are only kept in `.p2s` files. No dialog SHALL interrupt the save.
4. WHEN a `.p2s` document is saved via Save As with SVG chosen THEN the current file SHALL become that SVG file, as with any Save As.
5. PNG export SHALL stay unchanged.

### Requirement 4: Versioning and compatibility

**User Story:** As a long-term user, I want files from older PressToShape versions to keep opening in newer ones, and a clear message when a file is too new.

#### Acceptance Criteria

1. Every `.p2s` file SHALL record:
   - a **format version** (an integer, starting at 1)
   - the **app version** that wrote it, for information
2. WHEN a file with an older format version is opened THEN the system SHALL migrate it step by step to the current version in memory and open it. A later save SHALL write the current version.
3. WHEN a file with a newer format version than the app supports is opened THEN the system SHALL refuse to open it with a clear message naming both versions ("made with a newer PressToShape, please update"), and SHALL NOT crash or open a partial document.
4. Every change to what is stored SHALL increase the format version and add a migration, with a test that opens a stored sample file of every older version. Version 1's sample is added by this spec.

### Requirement 5: Safe saving and robust opening

**User Story:** As a user, I want saving to never destroy my file, and broken files to fail gracefully.

#### Acceptance Criteria

1. WHEN saving THEN the system SHALL write to a temporary file in the same folder and replace the target only after the write fully succeeded. IF writing fails (disk full, no permission) THEN the existing file SHALL remain unchanged and the status bar SHALL show the reason.
2. WHEN a file is not a valid `.p2s` (not a ZIP, missing or wrong type marker, malformed JSON, unknown shape type, invalid values) THEN opening SHALL fail with a clear status message and the current document SHALL stay open, as for broken SVG today.
3. WHEN reading a `.p2s` THEN the system SHALL only read the entries it knows by name, and SHALL refuse entries or totals beyond sane size limits, so hostile archives (zip bombs, path tricks) can't exhaust memory or write anywhere.
4. Opening a file SHALL never execute anything from it.

### Requirement 6: Preview and openness

**User Story:** As a user, I want to recognize files at a glance and be able to read my own data without PressToShape.

#### Acceptance Criteria

1. WHEN a `.p2s` file is saved THEN it SHALL contain a PNG preview of the artboard, at most 256 px on the longer side, rendered like PNG export. This is the base for future file-manager thumbnails; thumbnailer integration itself is out of scope.
2. The ZIP's first entry SHALL be an uncompressed `mimetype` file containing `application/x-presstoshape`, so tools can identify the type without unpacking (the OpenDocument/OpenRaster convention).
3. The document JSON SHALL be readable: stable key names, documented in a committed format description (`docs/file-format.md`) that lists every field and the version history.
4. Reserved for later: a `resources/` folder in the archive for embedded images, fonts and brushes. Version 1 SHALL write none, and readers SHALL ignore entries they don't use.

## Non-Functional Requirements

### Code Architecture and Modularity
- The format lives in `presstoshape/formats/` next to `svg.py`: one module for reading and writing, one for migrations. It uses only models and geometry, following the layer rules. The preview image is rendered by the editing layer, which may use render, and passed in as bytes.
- Serialization is explicit per type (no generic pickling or reflection over dataclasses that would silently change the format when a model field is renamed).
- Save/open operations in `editing/operations/documents.py` pick the format by file type; views only offer the dialogs.

### Performance
- Saving or opening a 10,000-shape document SHOULD take under 1 second on a typical machine, including the preview.
- Files SHOULD stay compact: deflate compression for JSON; a 10,000-shape file in the low megabytes at most.

### Security
- No `eval`, pickle or code from the file; JSON only, with validated types and value ranges.
- Size limits for archive entries and decompressed totals (Requirement 5.3).

### Reliability
- Round-trip tests over every shape type, nested Composites, transforms, rotated text, styles with no fill or no stroke, empty layers, hidden layers and every piece of working state.
- An atomic save, tested with a simulated failed write.

### Usability
- No new dialogs beyond the type choice in Save As; messages go to the status bar like today.
- Out of scope: file associations for `.p2s` in the MSI and desktop entry (later, together with `.svg`), file-manager thumbnailers, autosave/recovery (separate feature), embedding images or fonts (no such objects exist yet).
