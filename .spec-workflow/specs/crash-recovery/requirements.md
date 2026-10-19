# Requirements Document

## Introduction

If PressToShape crashes, the computer loses power or the session is killed, all unsaved work is lost today. This spec adds two safety nets:

1. **Crash recovery.** While a document has unsaved changes, PressToShape regularly writes a **recovery snapshot** into its own recovery folder (every 5 minutes by default, configurable). Snapshots never touch the user's files. When PressToShape ends normally, its snapshots are removed. When it didn't (crash, power loss), the next start offers the snapshots for recovery.
2. **Backup on save.** When saving over an existing file, the previous version is kept as one backup copy next to it, so a bad save or an unwanted change can be undone outside the app.

Recovered documents open as **unsaved**; the first save asks where to save (Save As, suggesting the original name), so a recovered state never silently overwrites the original file.

## Alignment with Product Vision

- **Reliability metric, "no data loss"**: product.md lists it as a success metric; the feature gap list names autosave / crash recovery under P1 "Document and app" with "Principle: no data loss".
- **Own format for fidelity**: snapshots use the native `.p2s` format, so a recovered document has everything, including the view, tool settings, selection and the Composite being edited, even when the original was an SVG.
- **Offline, no telemetry**: everything stays in local files; nothing is sent anywhere.
- **Professional expectations**: Illustrator, Affinity, Inkscape and Krita all recover after crashes; Krita keeps a backup of the previous version on save.

## Requirements

### Requirement 1: Recovery snapshots

**User Story:** As an artist, I want my unsaved work written somewhere safe regularly, so that a crash costs me minutes at most.

#### Acceptance Criteria

1. WHILE the document has unsaved changes THEN PressToShape SHALL write a recovery snapshot at the chosen interval (default 5 minutes), counted from the first change after the last snapshot or save.
2. IF nothing changed since the last snapshot THEN no new snapshot SHALL be written.
3. Snapshots SHALL be complete `.p2s` files (document and working state, as saving writes them), also for documents opened from SVG and for untitled documents. Each snapshot SHALL record the original file path (if any) and the time it was taken.
4. Snapshots SHALL be written atomically (temporary file, then replace), so a crash during writing never leaves a broken snapshot in place of a good one.
5. Writing a snapshot SHALL NOT change the document, its dirty state, the undo history or the status bar, and SHALL NOT interrupt drawing. For a typical document it SHALL take less than 200 ms.
6. IF writing a snapshot fails (disk full, no permission) THEN PressToShape SHALL show one status message about it and keep trying at the next interval, without dialogs.
7. Snapshots SHALL live in a recovery folder of their own, next to the other app data (the platform's app data location; `recovery/` next to the executable in the portable build). The user's own folders SHALL NOT be written to by recovery.

### Requirement 2: Removing snapshots that are no longer needed

**User Story:** As a user, I want old recovery data to disappear once my work is safe, so that recovery only offers what was really lost.

#### Acceptance Criteria

1. WHEN the document is saved successfully THEN its snapshot SHALL be removed.
2. WHEN the document is closed without saving on purpose (Discard in the unsaved-changes question, or New/Open replacing it after confirmation) THEN its snapshot SHALL be removed.
3. WHEN PressToShape quits normally THEN all snapshots of this run SHALL be removed.
4. Each running PressToShape (if several run at once) SHALL only manage its own snapshots and SHALL NOT offer or remove snapshots of another running instance.

### Requirement 3: Recovering after a crash

**User Story:** As a user whose PressToShape crashed, I want to get my last work back at the next start, and decide what to do with it.

#### Acceptance Criteria

1. WHEN PressToShape starts AND snapshots exist from runs that didn't end normally (and aren't running any more) THEN a **Recover Documents** dialog SHALL appear over the main window, before the New Document dialog.
2. The dialog SHALL list each snapshot with:
   - the document's name ("Untitled" for never-saved ones);
   - the original location, if any;
   - when the snapshot was taken;
   - a small preview.
3. For the selected snapshot the user SHALL be able to:
   - **Recover**: open it, then close the dialog;
   - **Discard**: delete it, after confirmation.

   **Close** (or Esc) SHALL keep the remaining snapshots for the next start.
4. WHEN a snapshot is recovered THEN the New Document dialog SHALL NOT appear for that start.
5. WHEN no snapshots are left or the user closes the dialog without recovering THEN startup SHALL continue as usual (New Document dialog if enabled).
6. Snapshots that can't be read (damaged) SHALL be listed as damaged and can only be discarded.

### Requirement 4: Working with a recovered document

**User Story:** As a user, I want a recovered document to be clearly marked and never overwrite my original file by accident.

#### Acceptance Criteria

1. A recovered document SHALL open with its document, view, tool settings, selection and edit state as in the snapshot, marked as having unsaved changes.
2. The window title SHALL show "(recovered)" after the name until the document is saved.
3. WHEN the user saves a recovered document THEN Save As SHALL appear, suggesting the original file name and folder (or "untitled" for never-saved documents) and the original type (`.p2s` or SVG).
4. The recovered snapshot SHALL stay on disk until the recovered document is saved or deliberately discarded, so a second crash before saving loses nothing. From then on the recovered document is protected by new snapshots like any other.
5. The status bar SHALL say that the document was recovered and from when.

### Requirement 5: Backup of the previous version on save

**User Story:** As a user, I want the previous version of a file kept when I save over it, so that I can go back one step outside the app.

#### Acceptance Criteria

1. WHEN saving over an existing file THEN the previous file SHALL first be kept as a backup next to it, named `<name>.backup.<extension>` (e.g. `poster.backup.p2s`, `logo.backup.svg`), replacing an older backup of the same file. Backups keep their extension, so they open in PressToShape (and SVG backups elsewhere) directly.
2. IF the backup can't be written THEN the save SHALL still happen, and the status bar SHALL say that no backup could be made.
3. Saving a new file (nothing to overwrite) SHALL create no backup.
4. A setting SHALL turn backups off (on by default).
5. The save itself stays atomic as today: a failed save leaves both the file and its backup as they were.

### Requirement 6: Settings

**User Story:** As a user, I want to choose how often recovery data is written and whether backups are kept.

#### Acceptance Criteria

1. Settings → General SHALL offer:
   - **"Save recovery data every"**: 1, 2, 5 (default) or 10 minutes, or **Off**;
   - **"Keep a backup of the previous version when saving"** (default on).
2. Changes SHALL apply immediately, without a restart.
3. WHEN recovery is turned Off THEN existing snapshots of this run SHALL be removed and no new ones written. Snapshots from earlier crashes SHALL still be offered at the next start.

## Non-Functional Requirements

### Code Architecture and Modularity
- **Snapshot bookkeeping, Qt-free and tested:**
  - writing snapshots through the existing `.p2s` writer;
  - the metadata (original path, time, run id);
  - listing, reading and deleting snapshots;
  - deciding which snapshots belong to dead runs.
- **The views own the timer and the dialog.** The current run is identified by a lock file, so a crashed run's snapshots can be told apart from a running instance's.
- **Backups:** part of the existing atomic save in `documents.py`.
- **Recovered state:** "recovered" is document state (title, Save As behaviour), kept in `AppState` like `file_path`.

### Performance
- A snapshot of a 10,000-shape document SHOULD be written in under 1 second. Snapshots skip the preview image if needed to stay fast. Snapshots are only written when something changed.
- Checking for snapshots at startup SHALL take only a directory listing and reading small metadata, not loading documents (except previews when the dialog shows).

### Security and privacy
- Snapshots contain the user's drawings, so they stay in the user's own app data folder with default permissions, are never uploaded, and are deleted as described.

### Reliability
- **Unit tests:**
  - snapshot write, read and delete;
  - metadata;
  - dead-run detection;
  - backup naming and replacement;
  - backup failure not blocking the save;
  - the recovered-document save flow.
- **A scripted crash test:** a child process with a dirty document is killed; the next start offers its snapshot and recovers the exact document.

### Usability
- No new shortcuts.
- All texts translatable; German complete.
- **Out of scope:**
  - saving automatically into the user's own file;
  - a version history with more than one backup;
  - recovery of several documents at once in separate windows (the app has one document window);
  - cloud or sync features.
