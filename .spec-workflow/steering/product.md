# Product Overview

## Product Purpose
PressToShape is an open-source, cross-platform, professional vector drawing application for artists. It aims to combine the best ideas of existing tools — Illustrator's breadth, Affinity Designer's speed and polish, Inkscape's openness, and the approachable, illustration-first feel of Linearity/Vectornator — into one powerful tool that can take on Adobe Illustrator.

The problem it solves: professional vector work is dominated by a proprietary subscription product. Open alternatives exist, but are often not fast, approachable or artist-focused enough for illustration work. PressToShape is meant to be a tool artists choose because it is good, not only because it is free.

Today PressToShape is at an early stage (shapes, bezier pen, text, styling, layers, booleans, non-destructive Composites, undo, SVG I/O). This document describes where it is going.

## Target Users
- **Illustrators and digital artists** drawing with tablets and mice. Need: expressive freehand and brush tools, pressure sensitivity, rich color and paint, a fast canvas that doesn't get in the way.
- **Graphic and UI designers** making logos, icons, layouts and marketing assets. Need: precise path editing, typography, alignment, snapping, export to common formats.
- **People leaving Illustrator** (cost, subscription, platform). Need: familiar concepts and workflows, professional feature depth, reliable import/export.
- **Inkscape users** who want a more modern, artist-focused workflow. Need: their SVG files and layers carry over and back.

## Key Features
Current:
1. **Drawing tools**: select, node, bezier pen (click for corners, drag for curves, closing paths), pencil (freehand with smoothing), rectangle, ellipse, text, eyedropper (picks up a shape's style or the colour under the pointer); Shift constraints, keyboard shortcuts.
2. **Direct manipulation**: scale/rotate handles on the selection, arrow-key nudge, flip, align and distribute, rulers, guides, grid and snapping, path node and bezier handle editing (node types, break, join, delete segment, close/open, reverse, combine/split, continuing paths with the pen), live corners (round, inverted, chamfer), object to path, cursors that show the action.
3. **Styling**: fill and stroke with their own opacity, stroke width, object opacity, fill rule, line ends, corners and dashes per shape or multi-selection; rounded rectangle corners, text alignment; per-tool default styles in a context-sensitive tool options panel; a docked Colour panel (fill/stroke pair, HSV picker, hex, alpha, recent colours, document swatches saved as Inkscape swatches, a personal swatch library with GIMP palette import/export).
4. **Layers and groups**: layers can be added, deleted, renamed, hidden and locked (Inkscape-compatible); single objects can be hidden and locked too, and the Layers panel shows every object in a tree with eye and lock toggles; groups bundle shapes, can be entered to edit inside them and have their own opacity; SVG groups stay groups.
5. **Boolean operations**: union, difference, intersection, exclude, divide.
6. **Canvas navigation**: zoom under cursor, pan (middle-drag, touchpad).
7. **Undo/redo** for every document edit.
8. **Clipboard**: copy, cut, paste, paste in place, duplicate and Alt+drag duplicate; SVG on the clipboard for other apps.
9. **Files**: native `.p2s` format (lossless, with working state) and SVG open/save. SVG import reads CSS class styles, `<use>`/`<symbol>` and multi-line text, and reports what it couldn't import.
10. **New documents**: New Document dialog with presets and custom sizes in px, mm, cm, in or pt with DPI; recent files; documents keep their unit.
11. **Crash recovery and backups**: recovery snapshots while there are unsaved changes, offered after a crash; one backup of the previous version on save.
12. **Languages and settings**: English and German interface, user-provided `.po` translations; a Settings window (language, renderer).

Core feature pillars (target):
1. **Freehand & brushes**: pressure-sensitive tablet input, pencil with smoothing, vector brushes, variable-width strokes, width profiles.
2. **Rich paint**: linear/radial/mesh gradients, patterns, opacity and blend modes, multiple fills and strokes per object.
3. **Non-destructive effects**: live effects such as blur, shadows and filters, rendered on canvas and on export.
4. **Typography**: rich text, text on path, OpenType font features, converting text to outlines.
5. **Path editing & construction**: node/handle editing, full boolean set, shape builder, stroke-to-path, offset, simplify.
6. **Precision & layout**: transforms with handles, snapping, grids, guides, align/distribute, artboards.
7. **File formats**: native PressToShape format that stores everything PressToShape can do; SVG import/export with Inkscape interop; raster export (PNG etc.).

## Business Objectives
- Become a serious open-source alternative to Adobe Illustrator for illustration and design work.
- Win artists through quality: speed, feel and workflow, not just price.
- Run on Linux and Windows with packaged, installable builds. macOS is not a target for now.
- Fit into existing pipelines through solid SVG and Inkscape interop.
- Keep the architecture clean and the codebase approachable so the project can grow and accept contributors.

## Success Metrics
- **Feature coverage**: each core pillar above reaches a usable first version.
- **Performance**: canvas stays fluid (no visible lag in pan/zoom/drag/brush strokes) with complex documents of tens of thousands of shapes; startup to usable window in a couple of seconds.
- **Interop**: PressToShape-made SVG round-trips through Inkscape with shapes, styles and layers intact; common Inkscape and Illustrator-exported SVG files open correctly.
- **Reliability**: no data loss — every edit undoable, native format reloads exactly what was saved.
- **Adoption**: artists use it for real projects (tracked via releases, downloads, community feedback).

## Product Principles
1. **Artists first**: optimize for drawing feel and creative flow. Tools respond instantly, gestures feel natural, the UI stays out of the way of the canvas.
2. **Professional depth, approachable surface**: deep capability is available, but common tasks stay simple and discoverable; panels follow the current tool and selection instead of showing everything at once. Keyboard shortcuts are reserved for frequent drawing and editing actions; rarely used commands and windows (settings, about) are reached through menus.
3. **Non-destructive by default**: effects, booleans and styles should stay editable wherever practical; every edit is undoable.
4. **Own format for fidelity, SVG for exchange**: the native format stores everything PressToShape supports without compromise. SVG import/export stays a first-class citizen, and features SVG can't express degrade predictably (e.g. flatten or rasterize) instead of silently disappearing.
5. **Inkscape interop is a requirement**: layers and supported content survive a round trip with Inkscape.
6. **What you see is what you export**: canvas rendering matches exported output.

## Monitoring & Visibility (if applicable)
Not applicable — PressToShape is a local desktop app with no telemetry. User feedback is through the status bar (tool, zoom, messages) and window title (file name, unsaved state).

## Future Vision
PressToShape grows from its current shape-editor core into a full professional illustration application, pillar by pillar, while its session / operations / tools architecture keeps it maintainable.

### Potential Enhancements
- **Pro workflows**: artboards, symbols/components, global (linked) colors, styles libraries.
- **Import**: PDF / AI-compatible import, more SVG features (patterns, filters, markers). Raster pictures (PNG, JPEG, WebP, GIF) can be placed and are embedded in `.p2s` and SVG; SVG files as pictures are not read.
- **Export**: PNG/JPEG/PDF export with size/DPI and per-artboard/slice export.
- **Customization**: preferences, customizable shortcuts and workspaces.
- **Extensibility**: plugin or scripting API in the longer term.
