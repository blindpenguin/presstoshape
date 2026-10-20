# Tasks Document

- [x] 1. Flags on shapes and layers, geometry and rendering
  - Files: presstoshape/models/shapes.py, presstoshape/models/app_state.py, presstoshape/editing/session.py, presstoshape/geometry/transforms.py, presstoshape/render/scene.py, presstoshape/render/paths.py, presstoshape/render/hit_test.py, tests/models/*, tests/geometry/test_transforms.py, tests/render/*
  - `hidden` / `locked` appended to every shape dataclass, `Layer.locked`; `_copy_document` copies layers with `replace`; Composite outline skips hidden parts; `draw_shape` returns on hidden; `draw_composite_parts` skips hidden parts; group bounds over non-hidden children (all when every child is hidden); hit-test skips hidden children
  - Purpose: hidden shapes vanish from drawing, export, picking and bounds (Req 1.2, 1.4, 1.5)
  - _Leverage: existing CompositeShape/GroupShape branches in transforms, scene, paths, hit_test_
  - _Requirements: 1.2, 1.4, 1.5, 5.5_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced with Skia | Task: Implement design.md Components 1–3; tests: defaults False and positional constructors unchanged, undo snapshot keeps Layer.locked, Composite outline without hidden part (base moves up) and empty when all hidden, CPU pixel test hidden shape and hidden group child not drawn, hidden child not hit, group bounds exclude hidden children and fall back to all | Restrictions: no Qt; shapes frozen (replace); no per-frame cost (check only while recording); speaking names | Success: suite green; scripts/bench_canvas.py numbers unchanged. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Shown/pickable rules, edit chain and map_shapes
  - Files: presstoshape/editing/containers.py, presstoshape/editing/queries.py, presstoshape/tools/snapper.py, tests/editing/test_containers.py, tests/tools/test_select.py, tests/tools/test_snapper.py (or existing snapping tests), tests/tools/test_node.py
  - `shown_shapes`, `pickable_shapes` (skips hidden, locked, locked/hidden layers, also in edit mode), `edit_chain` candidates pickable only; `map_shapes` keeping identity and part modes; Snapper uses `shown_shapes`; `queries.any_hidden` / `any_locked` memoized on layer shape tuples
  - Purpose: one place decides what is drawn, snapped to and pickable (Req 1.2, 2.2, 2.4, 3.2)
  - _Leverage: containers.with_children, valid_edit_path, Session trimming after undo_
  - _Requirements: 1.2, 1.7, 2.2, 2.4, 2.6, 3.2, 3.4_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md Component 4 and the any_hidden/any_locked queries; tests: shown vs pickable for hidden, locked, locked layer, inside entered group; edit_chain trims hidden/locked container and container in locked layer; map_shapes changes nested shapes, keeps untouched identities and part modes; click and rubber band (ToolDriver) skip locked/hidden and act on what's below; Select All skips them; snapping still hits a locked shape but not a hidden one; Node tool can't pick a locked path; memo answers change after an edit | Restrictions: no Qt; callers other than Snapper keep pickable_shapes; never layer.shapes directly in operations | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Visibility operations and layer lock
  - Files: presstoshape/editing/operations/visibility.py (new), presstoshape/editing/operations/layers.py, presstoshape/editing/operations/shapes.py, presstoshape/editing/operations/clipboard.py, presstoshape/editing/operations/__init__.py (registration import if needed), tests/editing/test_visibility.py (new), tests/editing/test_layers.py, tests/editing/test_clipboard.py
  - `hide_selection`, `show_all`, `lock_selection`, `unlock_all` registered with can_run; `set_hidden`, `set_locked`; `set_layer_locked`; each change trims edit_path and prunes selection; locked layer refuses drawing, notes paste; paste clears top-level flags; status messages with ngettext
  - Purpose: the commands users run (Req 1, 2, 3, 6.2, 6.3)
  - _Leverage: map_selected, map_shapes, prune_selection, set_layer_visible, hidden-layer checks in shapes._add and clipboard.paste_
  - _Requirements: 1.1, 1.3, 1.6–1.8, 2.1, 2.3, 2.5–2.7, 3.1, 3.3, 3.4, 5.4, 5.5, 6.2, 6.3_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md Component 5 except select_object; tests: each command's undo label and one undo step, selection afterwards (cleared / shown-and-pickable ones), can_run, Show All doesn't touch layer visibility, nested toggles, hiding/locking the entered container or locking its layer leaves edit mode, moving/deleting a group moves/deletes its hidden and locked children, commands inside an entered group, locked layer refusal message, paste on locked layer with note, pasted shapes arrive unflagged, nested flags survive copy/paste | Restrictions: no Qt; operations take plain values; UI text through i18n (literals only) | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Object tree logic and select_object
  - Files: presstoshape/editing/object_tree.py (new), presstoshape/editing/operations/visibility.py, presstoshape/editing/operations/edit_mode.py (if a helper is needed), tests/editing/test_object_tree.py (new), tests/editing/test_visibility.py
  - `object_type`, `object_label`, `Location`, `locate`, `inherited_flags`; `select_object(session, shape_id, extend)` activates layer, enters containers, selects; refuses effectively hidden/locked objects; tolerates vanished ids
  - Purpose: Qt-free logic behind the tree (Req 4.2, 4.4, 4.5)
  - _Leverage: edit_mode.enter, layers.select_layer, set_selection_
  - _Requirements: 4.2, 4.4, 4.5_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement design.md Component 6 and select_object from Component 5; tests: labels per type and shortened text, locate for top-level, group child, Composite part in a group, inherited flags from layer and containers, select_object enters the right chain from another entered container, extend within same container, refused for hidden/locked/inherited, no-op for unknown id, not an undo step | Restrictions: no Qt; labels translated with _() literals | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. .p2s version 7
  - Files: presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, tests/formats/test_p2s.py, tests/formats/samples/v7.p2s (new), docs/file-format.md
  - Optional `hidden`/`locked` on shapes and `locked` on layers, validated booleans; `MIGRATIONS[6] = _unchanged`; sample with hidden shape, locked group with hidden child, hidden Composite part, locked layer
  - Purpose: flags survive save, reopen, clipboard and recovery (Req 5.1)
  - _Leverage: existing optional-field encoding, sample tests_
  - _Requirements: 5.1, 5.4_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement the .p2s part of design.md Component 9; tests: round trip of every flag position, stable bytes, v6 sample opens unflagged, v7 sample opens with its flags, non-boolean flag → P2sError with JSON path | Restrictions: explicit encoders/decoders, never generic over dataclass fields; flags written only when set | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. SVG read and write
  - Files: presstoshape/formats/svg.py, presstoshape/formats/svg_reader.py, presstoshape/formats/svg_names.py (attribute name if needed), tests/formats/test_svg.py, tests/formats/test_svg_reader.py (or existing reader tests)
  - Writer: `style="display:none"` for hidden, `sodipodi:insensitive="true"` for locked shapes, groups, Composite parts and layers; reader: `display:none` elements imported hidden (text lines, groups), `sodipodi:insensitive="true"` → locked, other values ignored; defs/symbol and hidden `<use>` targets unchanged; Composite stored-parts check with hidden parts
  - Purpose: Inkscape interop for both states (Req 5.2, 5.3)
  - _Leverage: layer display:none handling, svg_names namespaces, Composite metadata reader_
  - _Requirements: 5.2, 5.3_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with SVG knowledge | Task: Implement the SVG part of design.md Component 9; tests: write → read round trip of all flag positions, Inkscape-style snippets (hidden rect, hidden group, locked path, locked layer, display:none multi-line text), odd insensitive values ignored, `<symbol>` content with display:none still skipped, Composite with hidden part reads back as Composite, clipboard SVG keeps nested flags | Restrictions: never copy code from Inkscape; interop from format facts only; svgelements only for values, not SVG.parse | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Commands in the menu, shortcuts and icons
  - Files: presstoshape/views/keymap.py, scripts/generate_icons.py, presstoshape/assets/icons/*.svg (generated), presstoshape/icons.py, presstoshape/assets/translations/presstoshape.pot, presstoshape/assets/translations/de.po
  - Object menu section with Hide Selection (Ctrl+3), Show All (Ctrl+Alt+3), Lock Selection (Ctrl+2), Unlock All (Ctrl+Alt+2); Tabler icons eye, eye-off, lock, lock-open, square, circle, vector-bezier, typography, box-multiple; translations updated
  - Purpose: commands reachable by menu and keys (Req 6.1)
  - _Leverage: keymap Binding, MENUS layout, generate_icons mapping, update_translations.py_
  - _Requirements: 6.1_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement design.md Component 8; regenerate icons with `uv run --group dev python scripts/generate_icons.py`; run `uv run python scripts/update_translations.py` and translate new entries in de.po (all task 3–7 texts) | Restrictions: no new shortcuts beyond the four; no QIcon(path); mnemonic clash test must pass | Success: suite green incl. translation and mnemonic tests; screenshot shows the Object menu entries. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. Object tree model
  - Files: presstoshape/views/object_tree_model.py (new)
  - `ObjectTreeModel(QAbstractItemModel)`: name / eye / lock columns, lazy children, topmost first, type and state icons (disabled mode for inherited), editable layer names, `set_content(state)` resetting only when content changed, key ↔ index lookup for expansion restore and selection sync
  - Purpose: the data behind the Layers panel tree (Req 4.1–4.4)
  - _Leverage: editing/object_tree.py, icon_engine.icon, theme colours_
  - _Requirements: 4.1–4.4, Performance_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer experienced with Qt item models | Task: Implement the model part of design.md Component 7; check with a scratch script (QAbstractItemModelTester under offscreen) and a 10k-shape document: set_content unchanged-content cost and reset cost | Restrictions: views only consume state; no Qt below views/; no defensive try/except around Qt calls; delete scratch scripts after | Success: model tester passes; unchanged refresh is a few comparisons; reset with 10k shapes well under one frame. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Layers panel tree
  - Files: presstoshape/views/layers_view.py, presstoshape/views/main_window.py (if wiring changes)
  - `QTreeView` replacing `QListWidget`; eye/lock clicks → layer or object toggles (deferred with QTimer.singleShot); name clicks → select_layer / select_object (Ctrl/Shift extend); layer rename on double-click; refresh mirrors selection, restores expansion and scroll, expands and scrolls to the first selected row; add/delete buttons kept
  - Purpose: users see, toggle and pick any object (Req 3.1, 4)
  - _Leverage: ObjectTreeModel, existing LayersPanel buttons and deferred-apply pattern_
  - _Requirements: 3.1, 4.1–4.7_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement the panel part of design.md Component 7; check with screenshot_app.py and a scratch QTest script, offscreen and on desktop GL: toggle eye/lock on layer and object rows, click a group child row (group entered, child selected), canvas selection highlights its row, Ctrl+3 / Ctrl+Alt+3 / Ctrl+2 / Ctrl+Alt+2, rename a layer; time refresh after a move with 10k shapes | Restrictions: don't rebuild the tree from inside its own signals; blockSignals while mirroring selection; refresh idempotent and cheap; give widgets parents; delete scratch scripts and crops after | Success: interactions work in both renderers; refresh with 10k shapes stays around a few ms when only the selection changes. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 10. Docs and final checks
  - Files: README.md, FAQ.md (if SVG import text changes), .spec-workflow/steering/product.md, FEATURE_GAPS.md (local, not committed)
  - Product feature list (layers and groups: hide/lock objects, lock layers, object tree); README SVG note that hidden objects are kept; tick the gap item, update the Layers panel upgrade item to what remains; full test suite, bench_canvas, `main.py --self-test`
  - Purpose: docs match the app (all requirements)
  - _Leverage: memory rule on hedged public claims_
  - _Requirements: all_
  - _Prompt: Implement the task for spec object-visibility, first run spec-workflow-guide to get the workflow guide then implement the task: Role: developer and technical writer | Task: Update docs as listed with soft wording on what works; run `uv run pytest`, `uv run python scripts/bench_canvas.py` (CPU and GL) and `uv run python main.py --self-test` | Restrictions: hedge public claims; FEATURE_GAPS.md stays uncommitted | Success: suite green, benchmark unchanged, self-test passes, docs updated. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
