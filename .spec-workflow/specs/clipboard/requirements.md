# Requirements Document

## Introduction

PressToShape gets the editing basics every user reaches for in the first minutes: **Copy, Cut, Paste, Paste in Place and Duplicate**, plus **Alt+drag to duplicate** with the Select tool.

Copied shapes go to the system clipboard in two forms:

- PressToShape's own data, so a paste is exact: shapes, styles, transforms, Composites with their parts and modes.
- SVG, so shapes can be pasted into Inkscape, browsers, text editors and other apps that accept SVG.

Paste accepts both, so shapes also come in from Inkscape and other apps that put SVG on the clipboard, and move between two PressToShape windows or documents.

Today the only way to repeat a shape is to draw it again; there is no clipboard or duplicate at all.

## Alignment with Product Vision

- **P1 in the feature gap list**: clipboard and duplicate are first on the suggested order ("daily-use basics"); their absence feels broken.
- **Principle 2, Professional depth, approachable surface**: standard shortcuts (Ctrl+C/X/V/D) and menu entries behave the way users know from Illustrator, Affinity and Inkscape.
- **Principle 4, Own format for fidelity, SVG for exchange**: inside PressToShape the paste is lossless (the native shape data), towards other apps it is SVG.
- **Principle 5, Inkscape interop**: shapes copied in Inkscape paste into PressToShape and the other way round.
- **Reliability metric**: every clipboard edit is one undo step.
- **Groundwork for later features**: shape copying with fresh ids is what groups, symbols and the shape builder will need too.

## Requirements

### Requirement 1: Copy

**User Story:** As a designer, I want to copy selected shapes, so that I can reuse them in this or another document, or in another app.

#### Acceptance Criteria

1. WHEN shapes are selected AND the user chooses Edit → Copy (Ctrl+C) THEN the system SHALL put the selected shapes on the system clipboard, in paint order, and SHALL show a status message ("Copied 3 objects").
2. The clipboard content SHALL contain:
   - PressToShape data that preserves everything the native `.p2s` format stores about a shape: type, geometry, transform, style, text, Composite parts and part modes;
   - an SVG document with the same shapes, as Save As SVG would write them, sized to the copied shapes' bounds.
3. WHEN a Composite is being edited AND parts are selected THEN Copy SHALL copy those parts as shapes.
4. Copy SHALL NOT change the document, the selection or the undo history, and SHALL NOT mark the document dirty.
5. IF nothing is selected THEN Copy (and Cut) SHALL be disabled in the menu and do nothing on the shortcut.
6. WHEN the Node tool is active THEN Copy SHALL copy the whole selected shapes (copying single nodes is out of scope).

### Requirement 2: Cut

**User Story:** As a designer, I want to cut shapes, so that I can move them to another layer, document or app.

#### Acceptance Criteria

1. WHEN shapes are selected AND the user chooses Edit → Cut (Ctrl+X) THEN the system SHALL copy them as in Requirement 1 and remove them from the document.
2. Cut SHALL be one undo step labelled "Cut". Undo SHALL restore the shapes; the clipboard keeps the cut content.
3. WHEN parts of an entered Composite are cut THEN the Composite's result SHALL update as when parts are deleted today.

### Requirement 3: Paste

**User Story:** As a designer, I want to paste shapes where I am looking, so that I can place copies quickly.

#### Acceptance Criteria

1. WHEN the clipboard holds PressToShape data or SVG AND the user chooses Edit → Paste (Ctrl+V) THEN the system SHALL add the shapes to the active container and center them as a whole on the visible canvas area.
2. The active container SHALL be the same one new drawn shapes go into: the active layer, or the entered Composite, where pasted shapes become parts with the mode set for new parts.
3. Pasted shapes SHALL be placed above all existing shapes of that container, keep their relative order and positions, and become the new selection. The previously selected shapes SHALL be deselected.
4. Every pasted shape and every part inside a pasted Composite SHALL get a new, unique id. Pasting the same content twice SHALL never produce duplicate ids.
5. Paste SHALL be one undo step labelled "Paste" and SHALL mark the document dirty.
6. WHEN the clipboard holds both PressToShape data and SVG THEN the system SHALL use the PressToShape data.
7. WHEN the clipboard holds only SVG (from another app) THEN the system SHALL read it as when opening an SVG file:
   - shapes from all layers and groups SHALL be pasted into the active container in document order, with their visual appearance (transforms and inherited styles applied as on open);
   - elements PressToShape does not support SHALL be skipped, and the status message SHALL say so as on open.
8. WHEN the clipboard holds plain text that is a complete SVG document THEN Paste SHALL treat it as SVG (text editors and some apps only offer text).
9. IF the clipboard holds nothing pasteable (empty, an image, plain text that is not SVG, broken SVG) THEN Paste SHALL change nothing and show a status message ("Nothing to paste"); it SHALL NOT raise an error dialog or crash.
10. IF the active layer is hidden THEN Paste SHALL still paste there and the status message SHALL say that the layer is hidden.
11. Edit → Paste SHALL be enabled whenever the clipboard holds PressToShape data, SVG or text, and update as the clipboard changes while the app runs.

### Requirement 4: Paste in Place

**User Story:** As a designer, I want to paste shapes at exactly the position they were copied from, so that I can move shapes between layers or documents without changing their placement.

#### Acceptance Criteria

1. WHEN the user chooses Edit → Paste in Place (Ctrl+Shift+V) THEN the system SHALL paste as in Requirement 3, but keep the shapes' document coordinates instead of centering them on the view.
2. WHEN SVG from another app is pasted in place THEN the shapes SHALL keep the coordinates they have in that SVG document's user space.
3. Paste in Place SHALL be one undo step labelled "Paste in Place".

Note: Inkscape's Ctrl+Alt+V is Divide in PressToShape already, so Paste in Place uses Illustrator's Ctrl+Shift+V.

### Requirement 5: Duplicate

**User Story:** As a designer, I want to duplicate the selection in one step, so that I can make copies without touching the clipboard.

#### Acceptance Criteria

1. WHEN shapes are selected AND the user chooses Edit → Duplicate (Ctrl+D) THEN the system SHALL add a copy of each selected shape at the same position, directly above the topmost selected shape of its container, and select the copies.
2. The copies SHALL keep the original shapes' relative paint order among themselves.
3. Copies SHALL get new unique ids, including parts inside Composites.
4. Duplicate SHALL NOT change the system clipboard.
5. Duplicate SHALL be one undo step labelled "Duplicate". IF nothing is selected THEN it SHALL be disabled.
6. WHEN parts of an entered Composite are selected THEN Duplicate SHALL duplicate them as parts of that Composite with the same modes.

### Requirement 6: Alt+drag to duplicate

**User Story:** As an illustrator, I want to drag a copy off a shape with Alt held, so that I can duplicate and place in one gesture like in Illustrator and Affinity.

#### Acceptance Criteria

1. WHEN the Select tool is active AND the user presses on a selected or unselected shape with Alt held AND drags THEN the system SHALL move a copy of the selection (after the press updated it as without Alt) and leave the originals in place.
2. WHILE such a drag runs THEN the cursor SHALL show the duplicate action, and the moving copy SHALL preview like a normal move.
3. WHEN the drag is released THEN duplicate and move SHALL be one undo step labelled "Duplicate". The copies SHALL be selected.
4. IF Alt is held but the pointer is released without dragging (below the usual drag threshold) THEN nothing SHALL be duplicated.
5. Alt on the scale handles SHALL keep scaling from the center as today; Alt+drag only duplicates when moving.
6. Shift during an Alt+drag SHALL constrain the move as it does for a normal move.

### Requirement 7: Menus and shortcuts

**User Story:** As a user, I want the commands where I expect them, so that I find them without looking.

#### Acceptance Criteria

1. The Edit menu SHALL list, after Undo/Redo: Cut, Copy, Paste, Paste in Place, Duplicate, then Delete.
2. Shortcuts SHALL be: Cut `Ctrl+X` (and `Shift+Del`), Copy `Ctrl+C` (and `Ctrl+Ins`), Paste `Ctrl+V` (and `Shift+Ins`), Paste in Place `Ctrl+Shift+V`, Duplicate `Ctrl+D`.
3. WHEN keyboard focus is in a text field (layer rename, spin boxes, the zoom field) THEN the clipboard shortcuts SHALL act on that text field, not on shapes.
4. Cut, Copy and Paste SHALL have toolbar icons only if they fit the toolbar layout; menu and shortcuts are required.

## Non-Functional Requirements

### Code Architecture and Modularity
- The Qt clipboard is used only in `views/`. Operations take and return plain data (bytes/strings), so copy, cut, paste and duplicate are unit-tested without a display.
- The clipboard's PressToShape data reuses the `.p2s` shape encoders and decoders, so a shape type added to the native format is copyable without extra work.
- Pasting and duplicating go through `editing/containers.py` (active container, `change_container`), so they work the same on layers and inside Composites.
- Id renumbering lives in one helper used by paste and duplicate (and later groups and symbols).

### Performance
- Copy, paste and duplicate of 1,000 shapes SHOULD finish in well under a second.
- Checking whether Paste is enabled SHALL NOT parse the clipboard content; it only looks at the offered formats.

### Security
- Clipboard content from other apps is untrusted, like an opened file: parsed with the same SVG reader and validated `.p2s` decoders, with size limits; nothing from it is executed.

### Reliability
- Round-trip tests: copy → paste reproduces every shape type, nested Composites, rotated text and styles without fill or stroke, with new ids.
- SVG copied from PressToShape and pasted back SHALL look the same (same as an SVG save/open round trip).
- Broken or hostile clipboard data fails with a status message, never an exception or a partial paste.

### Usability
- Status bar messages for every clipboard action; no new dialogs.
- Out of scope: copying and pasting nodes inside a path, pasting raster images (no image objects yet), pasting plain text as a new text object, paste style / paste size, a clipboard history, repeat-duplicate with the last offset (Affinity's Ctrl+J), and duplicating layers.
