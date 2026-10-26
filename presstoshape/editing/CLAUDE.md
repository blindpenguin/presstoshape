# editing/ — session and operations

```
editing/
├── session.py            # Session: the AppState, labelled undo history, subscribe/notify, edit()
├── registry.py           # registered operations: id, menu label, can_run
├── queries.py            # read-only questions about state
├── containers.py         # active container (layer, entered group or Composite): pickable shapes, change_container
└── operations/           # the only code that changes state, one module per feature
```

## Rules

- Commands without extra input (menus, shortcuts) are registered with `@operation("edit.delete", "&Delete", can_run=...)`; shortcuts and icons go in `views/keymap.py`, not next to the operation. Commands with a check mark register a `checked` callback.
- Groups and Composites are containers (`children_of`): `AppState.edit_path` holds the ids of the entered ones (outer to inner). Operations reach "the shapes being edited" only through `editing/containers.py` (`pickable_shapes`, `change_container`), never `layer.shapes` directly, so they work the same on layer shapes, group children and parts; rules that only hold for Composite parts (outlines, part modes, no text) check `edited_composite`. Part modes stay keyed by part id when lists are rebuilt; an entered container left empty is removed. Enter/leave (`operations/edit_mode.py`) are not undo steps; `Session` trims a stale `edit_path` after undo.
- Crash recovery (`editing/operations/recovery.py`, `views/recovery_keeper.py`): one rule, while the document is dirty its snapshot is at most one interval old, otherwise there is none. Snapshots live only in the app's recovery folder, never in user folders. Anything that replaces or saves the document just has to clear `dirty` (and bump `Session.revision` through `edit()`/`replace_document`); the keeper does the rest.
- Colours (`editing/operations/colours.py`, `swatches.py`): every colour source (Colour panel, swatches, eyedropper, menu) goes through `apply_colour`, which writes the active paint of `queries.colour_target` (selection, else the active drawing tool's style, else `AppState.colours.current`). Document swatches are undoable and saved; recent colours and the stored palettes (`ColourState.palettes`, changed through `operations/palettes.py`; the swatch operations' "library" is the current palette) are app-level state that `MainWindow` persists (settings; `views/palette_store.py`, one JSON file per palette in the data folder's `palettes/`). Picker drags with a selection preview through `CanvasView.set_style_preview` (Overlay `live`) and commit once on release: a document edit per mouse move re-records the whole picture.
- Guides and the grid belong to the `Document` (undoable, saved); show/lock/snap toggles are view state on `AppState` (rulers and snapping remembered in app settings, grid/guides visibility in `.p2s` working state).
