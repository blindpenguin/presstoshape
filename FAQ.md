# FAQ

## About the project

### What is PressToShape?

An experimental, open-source vector drawing application for artists, built with Python, Qt (PySide6) and Skia. It aims to grow into a full illustration tool; today it covers the basics: shapes, bezier pen, text, layers, boolean operations, SVG open/save and PNG export.

### Why another vector editor when Inkscape exists?

Inkscape is an incredible tool, but it can be complex to use. PressToShape aims to simplify making illustrations with a more approachable interface and workflow.

### Is PressToShape meant to replace Illustrator?

Not replace it. The goal is to become a viable alternative. Rather than recreating Illustrator feature by feature, PressToShape takes inspiration from many tools (Illustrator, Inkscape, Affinity and others) and combines their best ideas with its own, to build something new.

### Why is PressToShape "experimental"?

Two reasons. It's early in development, so expect bugs and things to change. And it's built with heavy AI assistance: part of the point of the project is to see how far AI-assisted coding can be pushed on a real, non-trivial application.

### Who's behind PressToShape?

It's currently a one-person project.

### What can PressToShape do today?

Draw rectangles (with rounded corners), ellipses, bezier paths, freehand lines and text; set fill, stroke, stroke width, opacity, dashes, line ends and corners; organize layers and groups; align and distribute objects, with rulers, guides, a grid and snapping; copy, paste and duplicate shapes (also to and from Inkscape via the clipboard); combine shapes with union, difference, intersection, exclude and divide, or keep them editable as a Composite; undo/redo edits; open and save SVG (with Inkscape-style layers); export PNG; scale and rotate shapes with handles; edit path nodes. The interface is available in English and German. Not there yet: gradients, brushes and stable releases.

## Using PressToShape

### Where can I download it?

There are no stable releases yet, but [nightly builds](https://github.com/blindpenguin/presstoshape/releases/tag/nightly) are published automatically when the code changed: a Windows installer (MSI), a portable Windows ZIP, a Linux AppImage and the matching source code. They pass the automated tests and a start-up check on the build machines, but aren't tried by hand, so expect rough edges. The builds aren't code-signed yet, which is why Windows may show a SmartScreen warning.

### Which platforms does it run on?

PressToShape targets Linux and Windows. Testing currently happens on Linux only, as no Windows machine is available. macOS isn't a target yet. It may run, but expect limitations.

### Which languages does it speak? Can I translate it?

English and German for now; PressToShape follows your system language and Edit → Settings lets you choose. Other languages can be added without changing the program: translations are standard gettext `.po` files, which you can import in Settings. [docs/translating.md](docs/translating.md) explains how to start one. Contributions of new translations are welcome.

### Can I open my existing SVG and Inkscape files?

Mostly, with limits. PressToShape reads general SVG: rectangles (rounded too), circles, ellipses, lines, polylines, polygons, paths and text (multi-line text becomes one text object per line), with groups (they stay groups), `<use>` copies and symbols, transforms, and styles from attributes, `<style>` sheets with class and id rules (as Illustrator exports them) and inline styles. Opacity, even-odd fills, dashes, line ends and corners should come through. Inkscape layers should come through as PressToShape layers (hidden and locked ones included), hidden and locked objects should keep their state, and files saved by PressToShape should open in Inkscape with their layers. Page sizes in mm, cm, in or pt carry over in both directions. PressToShape is in early development, though, so there may be issues.

Pictures (`<image>` with PNG, JPEG, WebP or GIF, embedded or as a file next to the SVG) should come through; images that are SVG files, and anything on the internet (PressToShape never fetches it), are left out and listed. Not supported yet: gradients, clip paths, masks, filters, markers (arrowheads), fonts and mixed styles within one text line. They're skipped or approximated (gradients show as grey), and after opening such a file a dialog lists what couldn't be imported. Rectangles, ellipses and text under rotate/scale/skew transforms should keep their type; skew on text is dropped, and paths get the transform applied to their points. Re-saving such a file as SVG loses those parts, so keep a copy of the original or save as `.p2s`.

### What's a Composite?

A shape built from other shapes without destroying them. Each part adds to, subtracts from, intersects or excludes what's below it, and you can go back in (double-click) to move, reshape or re-mode any part while the result updates. Composites can contain Composites. In SVG files, other programs see the finished shape; the parts are kept in metadata that PressToShape reads back. If the shape was edited elsewhere in the meantime, PressToShape should open it as a plain path rather than guess.

### Will PressToShape have its own file format?

Yes: `.p2s`. It's a ZIP archive with the drawing as JSON and a small preview image, so it's easy to inspect and the format is [documented](docs/file-format.md). It stores everything PressToShape can do, plus where you were working (zoom, scroll position, tool settings, selection). SVG stays for exchange with other tools: Save As offers both, and a file opened as SVG keeps saving as SVG. Newer PressToShape versions should keep opening older `.p2s` files; a file from a newer version than yours is refused with a message instead of being opened half-way.

### Does it support drawing tablets and pressure?

Not yet. The pen tool currently places bezier points by clicking. Freehand drawing with pressure-sensitive tablets, vector brushes and variable-width strokes are planned.

### Can I export PNG or PDF?

PNG, yes: File → Export PNG… (Ctrl+Shift+E), at a resolution in DPI (or a scale factor) with a transparent background; the file records its DPI, so print programs know its physical size. It uses the same renderer as the canvas, so it should match what you see. PDF export is planned.

### The canvas is slow, black or crashes. What can I do?

The canvas is drawn with Skia on the GPU via OpenGL. If your graphics driver has trouble with that, start PressToShape with CPU rendering:

```
PRESSTOSHAPE_RENDERER=cpu uv run python main.py
```

On Windows (PowerShell): `$env:PRESSTOSHAPE_RENDERER="cpu"; uv run python main.py`. CPU rendering is slower on large drawings but avoids the GPU entirely. If you can, please [open an issue](https://github.com/blindpenguin/presstoshape/issues) with your OS and GPU.

### What happens to my work if PressToShape crashes?

While a document has unsaved changes, PressToShape writes a recovery copy every few minutes (5 by default; Edit → Settings → General changes it or turns it off). These copies stay in PressToShape's own data folder, never next to your files, and are deleted once you save or quit normally. After a crash or power loss, the next start lists them and you can recover the document; it opens as unsaved and the first save asks where to put it, so your original file isn't overwritten by accident. On top of that, saving over a file keeps its previous version as `name.backup.p2s` (or `.backup.svg`) next to it.

### Does PressToShape collect data or need the internet?

No. PressToShape runs offline: no telemetry, no accounts, no network access. Your files stay on your machine.

## Technology

### Why Python and not C++ or Rust?

Mainly because the maintainer understands Python well enough to review and adjust the AI-assisted code directly. The heavy lifting happens in native libraries anyway: Qt for the interface and Skia (the graphics engine behind Chrome) for rendering. Python mostly coordinates them. Whether that holds up for very large drawings is part of the experiment.

### Why Qt and Skia?

Qt (via PySide6) is a mature, cross-platform toolkit for desktop interfaces, with good tablet and HiDPI support. Skia is the 2D graphics engine used by Chrome and many design tools: it draws on the GPU and supports what PressToShape needs later, such as gradients, blend modes, effects and brushes. The same engine draws the canvas and exports, so they should look the same.

### What's the `.spec-workflow/` folder?

Planning documents. Larger features are written up as a spec first (requirements, then design, then tasks) and reviewed before code is written. The folder also holds "steering" docs describing the product vision, tech stack and project structure. It's part of how the AI-assisted development is kept on track.

## Contributing

### Can I contribute?

Not with code yet. It's too early and the architecture is still moving. Feedback, bug reports and feature ideas are very welcome, though: please [open an issue](https://github.com/blindpenguin/presstoshape/issues).
