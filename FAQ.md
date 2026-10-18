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

Draw rectangles, ellipses, bezier paths and text; set fill, stroke and stroke width; organize layers; combine shapes with union, difference, intersection, exclude and divide; undo/redo edits; open and save SVG (with Inkscape-style layers); export PNG; scale and rotate shapes with handles; edit path nodes. Not there yet: gradients, brushes, a native file format and installers.

## Using PressToShape

### Which platforms does it run on?

PressToShape targets Linux and Windows. Testing currently happens on Linux only, as no Windows machine is available. macOS isn't a target yet. It may run, but expect limitations.

### Can I open my existing SVG and Inkscape files?

Mostly, with limits. PressToShape reads general SVG: rectangles, circles, ellipses, lines, polylines, polygons, paths and text, with nested groups, transforms and inherited styles. Inkscape layers should come through as PressToShape layers (hidden ones included), and files saved by PressToShape should open in Inkscape with their layers. PressToShape is in early development, though, so there may be issues.

Not supported yet: gradients, clip paths, masks, `<use>`, embedded images and CSS stylesheets. They're skipped or approximated (unsupported paint shows as grey). Rectangles, ellipses and text under rotate/scale/skew transforms should keep their type; skew on text is dropped, and paths get the transform applied to their points. Re-saving such a file from PressToShape can lose information, so keep a copy of the original.

### Will PressToShape have its own file format?

That's the plan. SVG can't hold everything PressToShape is meant to support later (live effects, brush definitions, …). A native format would store everything PressToShape can do, while SVG stays for exchange with other tools. The format isn't designed yet.

### Does it support drawing tablets and pressure?

Not yet. The pen tool currently places bezier points by clicking. Freehand drawing with pressure-sensitive tablets, vector brushes and variable-width strokes are planned.

### Can I export PNG or PDF?

PNG, yes: File → Export PNG… (Ctrl+Shift+E), with a scale factor and a transparent background. It uses the same renderer as the canvas, so it should match what you see. PDF export is planned.

### The canvas is slow, black or crashes. What can I do?

The canvas is drawn with Skia on the GPU via OpenGL. If your graphics driver has trouble with that, start PressToShape with CPU rendering:

```
PRESSTOSHAPE_RENDERER=cpu uv run python main.py
```

On Windows (PowerShell): `$env:PRESSTOSHAPE_RENDERER="cpu"; uv run python main.py`. CPU rendering is slower on large drawings but avoids the GPU entirely. If you can, please [open an issue](https://github.com/blindpenguin/presstoshape/issues) with your OS and GPU.

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
