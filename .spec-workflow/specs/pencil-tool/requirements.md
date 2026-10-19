# Requirements Document

## Introduction

PressToShape gets a **Pencil tool**: drag to draw freehand, and the stroke becomes a smooth path of bezier curves as soon as the mouse (or tablet pen) is released. A **Smoothing** setting decides how closely the path follows the hand: low values keep every wobble, high values give calm, flowing lines with few nodes. The result is an ordinary path, so it can be styled, node-edited, combined in booleans and Composites like anything else.

This is the first step of the "Freehand & brushes" pillar. Pressure-sensitive, variable-width strokes and brushes build on it in later specs, so the input recording is designed to carry more than positions later.

## Alignment with Product Vision

- **Product pillar 1, Freehand & brushes**: "pressure-sensitive tablet input, pencil with smoothing, vector brushes…": this spec delivers the pencil with smoothing.
- **Principle 1, Artists first**: drawing must feel immediate. The stroke appears under the pointer while drawing, with no visible lag, and the final curve looks like what was drawn.
- **Target users**: illustrators with tablets and mice. Tablet pens work as pointing devices from day one.
- **Feature gap list, P1 "Shapes and tools"**: "Pencil / freehand tool with smoothing (also the base for tablet work)".

## Requirements

### Requirement 1: Drawing freehand

**User Story:** As an illustrator, I want to draw lines by hand, so that I can sketch and draw organic shapes directly.

#### Acceptance Criteria

1. The Pencil tool SHALL be in the tool strip (after the Pen), in the Tools menu and have the shortcut `F` (freehand). Selecting it shows a crosshair cursor, as the other drawing tools do.
2. WHEN the user presses and drags on the canvas THEN the stroke SHALL be drawn live under the pointer while dragging, in the Pencil's stroke style, without visible lag even for long strokes.
3. WHEN the user releases THEN the stroke SHALL be replaced by a smooth path (cubic beziers fitted to the drawn points) and selected, as one undo step ("Add path").
4. WHEN the stroke ends close to where it started (within a few screen pixels, independent of zoom) THEN the path SHALL be closed.
5. IF the pointer barely moved (a click, or a stroke shorter than a few screen pixels) THEN nothing SHALL be created.
6. Esc while drawing SHALL cancel the stroke without creating anything.
7. The path SHALL be added like other new shapes:
   - to the active layer;
   - inside an entered Composite, as a part in the new-part mode;
   - IF the active layer is hidden, with the existing "Layer is hidden" message.
8. Pen tablets SHALL work as with any pointing device (press, drag, release).

### Requirement 2: Smoothing

**User Story:** As an artist, I want to choose between faithful and calm lines, so that both sketchy and clean drawing styles work.

#### Acceptance Criteria

1. The Pencil's tool options SHALL have a **Smoothing** slider from 0 to 100 (default 50), next to its stroke and fill style.
2. Smoothing SHALL control how closely the fitted path follows the drawn points:
   - at 0 the path stays within about one screen pixel of the stroke;
   - higher values allow more deviation and produce fewer nodes and gentler curves.
3. The fitted path SHALL have smooth joins between curves wherever the stroke didn't turn sharply; sharp turns (corners drawn on purpose) SHALL stay corners.
4. Tolerances SHALL be measured in screen pixels at the zoom used while drawing, so the same hand movement gives the same character of line at any zoom.
5. The smoothing value SHALL be remembered like other tool settings (for the session and in `.p2s` files with the other tool settings).

### Requirement 3: Quality of the result

**User Story:** As an artist, I want pencil paths that are easy to edit afterwards, so that I can fine-tune them with the Node tool.

#### Acceptance Criteria

1. At default smoothing, a typical stroke SHALL produce far fewer nodes than drawn points: roughly one node per noticeable change of direction, not one per mouse event.
2. The fitted path SHALL NOT have loops, spikes or overshoots that weren't drawn.
3. Fitting SHALL be fast: a 5-second stroke (several hundred to a few thousand points) SHALL be fitted in well under 100 ms.
4. The result SHALL be a normal path, fully supported by node editing, booleans, Composites, SVG and `.p2s`.

### Requirement 4: Style

**User Story:** As a user, I want the pencil to draw with its own style, so that switching tools doesn't change how my lines look.

#### Acceptance Criteria

1. The Pencil SHALL have its own default style, like the other drawing tools: stroke on (dark, width 2 px or equivalent in the document unit), no fill. It is editable in its tool options (fill, stroke, width, in the document's unit).
2. The live stroke while drawing SHALL use that style's stroke colour and width, so what is drawn is what is created.

## Non-Functional Requirements

### Code Architecture and Modularity
- **Curve fitting** is pure geometry in `geometry/`, Qt-free and unit-tested: a tested algorithm (e.g. Philip Schneider's "An Algorithm for Automatically Fitting Digitized Curves", Graphics Gems 1990, with corner detection and a light pre-smoothing of the raw points).
- **The tool** is a `BaseTool` subclass in `tools/` that records points and commits through one operation.
- **Point records** keep room for more input data per point (pressure, tilt, time) so the next spec (pressure and variable width) can extend them without rewriting the tool.

### Performance
- While drawing, the per-move cost SHALL stay small enough to keep the canvas fluid (no full re-fit per mouse move; the live preview is the raw stroke).
- Fitting SHALL take less than 100 ms for strokes up to 5,000 points.

### Usability
- Shortcut `F`, a tool icon, a tool options hint ("Drag to draw. Smoothing: how calm the line is."), German translation complete.
- **Out of scope** (later specs):
  - pressure and variable width;
  - brushes;
  - redrawing part of an existing path with the pencil (Illustrator's pencil edit);
  - an eraser;
  - Shift for straight segments;
  - stabilizer or lazy-mouse modes.
