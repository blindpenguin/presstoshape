# tools/ — Qt-free input state machines

```
tools/
├── base.py               # Mods, CursorType, ToolContext, BaseTool
├── registry.py           # TOOLS (display order) + Toolbox
└── select.py / node.py / pen.py / pencil.py / shapes.py / text.py / eyedropper.py
```

## Rules

- Tools subclass `BaseTool` and are listed in `tools/registry.py`; they keep gesture state (drag start, pen points, previews) until they commit through one operation call. `CanvasView` never checks tool types.
- While a gesture runs, the tool reports the moving ids plus a doc-space `matrix` (move/rotate) or exact `live` replacement shapes (scale, node drags) in its `Overlay`, so the recorded picture is reused.
- Tools decide cursors as `CursorType` (Qt-free, tested); only `views/cursors.py` maps them to Qt.
- Snapping: tools build a `Snapper` once per gesture (`ToolContext.snapper(...)`, targets from the visible area) and ask it for corrected points/offsets while dragging; Ctrl ignores it; its hits go into `Overlay.snap` for feedback. The math lives in `geometry/snapping.py`, never per frame over all shapes.
