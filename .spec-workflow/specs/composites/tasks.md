# Tasks Document

- [x] 1. CompositeShape model and geometry
  - Files: presstoshape/models/shapes.py, presstoshape/models/app_state.py, presstoshape/geometry/booleans.py, presstoshape/geometry/transforms.py, tests/geometry/test_transforms.py, tests/geometry/test_booleans.py
  - `PartMode` in models (booleans.Mode aliases it), frozen `CompositeShape(id, parts, modes, style, transform)`, `Shape` union; `AppState.edit_path`, `new_part_mode`; `outline` (combine_parts, PathOpsError → empty), `translate`, `transform_shape`, `rotation_of` for Composites
  - Purpose: a Composite is a shape with an outline; everything outline-based works
  - _Leverage: geometry.booleans.combine_parts_
  - _Requirements: 1.1, 2.3, 2.5, 5.1, 5.3_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer with computational geometry experience | Task: Add the model and geometry per design.md (Model, geometry sections); tests: outline per mode, nested, empty, pathops error → empty, translate/transform_shape map over parts recursively with identity composite transform | Restrictions: models stay plain data with no veccy imports beyond models; speaking names; "type" not "kind" | Success: tests pass, architecture test green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Rendering and picking of Composites
  - Files: presstoshape/render/paths.py, presstoshape/render/hit_test.py, presstoshape/render/handles.py, presstoshape/render/scene.py, tests/render/*
  - PathCache result path + empty-result fallback bounds; hit_test takes pickable shapes (bottom to top) instead of the document; empty Composite hit inside fallback bounds; selection_frame treats Composites like paths; draw_overlays takes the pickable shapes for selection boxes
  - Purpose: Composites draw, export and pick as one shape
  - _Leverage: PathCache, draw_shape default branch_
  - _Requirements: 2.1, 2.2, 2.5_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python graphics developer experienced with Skia | Task: Implement the render changes per design.md (render/ section, except draw_edit_mode); update every caller of hit_test/draw_overlays (tools pass the pickable shapes for now as the visible layer shapes); tests: composite renders its result (pixel probe), export matches, empty composite fallback bounds + hit, frame | Restrictions: render must not import editing; no slowdown for documents without composites | Success: full suite green; bench within noise. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Active container helpers and container-aware queries
  - Files: presstoshape/editing/containers.py, presstoshape/editing/queries.py, presstoshape/editing/operations/_document.py, presstoshape/editing/operations/booleans.py, presstoshape/editing/operations/shapes.py, presstoshape/editing/operations/selection.py, presstoshape/editing/session.py, presstoshape/tools/base.py, presstoshape/tools/select.py, tests/editing/test_containers.py
  - editing/edit_chain/edited_composite/container_lists/change_container/valid_edit_path; pickable_shapes, recursive find_shape; _document helpers and _replace_with on change_container; shapes._add via container with new_part_mode; session after-restore validates edit_path then prunes against pickable_shapes; ToolContext.shape_at and band select use pickable_shapes
  - Purpose: every existing operation and tool works on parts in edit mode
  - _Requirements: 3.3, 3.4, 3.8, 5.3, NFR Architecture_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer working in the session/operations architecture | Task: Implement containers.py and switch callers per design.md (editing/containers.py, queries, session sections); tests at depth 0/1/2: container lists, change_container rebuilds the chain and the layer, modes kept by id, new parts get new_part_mode, undo trims edit_path and keeps part selection | Restrictions: behavior outside edit mode unchanged (existing tests untouched and green); no Qt | Success: full suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Composite operations
  - Files: presstoshape/editing/operations/composites.py, presstoshape/editing/operations/__init__.py, presstoshape/editing/operations/paths.py, presstoshape/editing/operations/layers.py, presstoshape/editing/operations/documents.py, presstoshape/editing/operations/selection.py, tests/editing/test_composites.py
  - make_composite (+ mode variants, nested inside edit mode), release, flatten (and Object to Path for Composites), enter/leave, set_part_mode (base skipped), set_new_part_mode; deleting the last part deletes the Composite and leaves; layer ops and new/open leave edit mode; registrations
  - Purpose: create, edit and undo Composites
  - _Requirements: 1.1–1.4, 3.1, 3.5, 3.6, 3.8, 4.1, 4.2, 5.2, 5.4, 6.1–6.3_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer working in the session/operations architecture | Task: Implement operations/composites.py per design.md table and the edit-mode exits in layers/documents/selection; tests for every row incl. undo labels, nested make taking the bottom part's mode, text excluded, enter/leave not undoable | Restrictions: geometry first, then session.edit; one undo step per command | Success: tests pass. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Arrange operations
  - Files: presstoshape/editing/operations/arrange.py, presstoshape/editing/operations/__init__.py, tests/editing/test_arrange.py
  - raise/lower/raise_to_top/lower_to_bottom within each container list; registered object.* commands
  - Purpose: z-order for shapes, evaluation order for parts
  - _Requirements: 4.3_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement arrange.py per design.md; tests with several selected shapes in a layer and in a Composite (result changes), no-op at the ends without undo step | Restrictions: keep relative order of selected shapes | Success: tests pass. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. Edit-mode rendering and tool behavior
  - Files: presstoshape/render/scene.py, presstoshape/views/canvas_view.py, presstoshape/tools/base.py, presstoshape/tools/select.py, tests/render/test_scene.py, tests/tools/test_select.py
  - draw_edit_mode (dim, live result with moving/live parts, mode-styled part outlines, thicker base); CanvasView calls it; SelectTool double-click enter/leave, key("enter"); BaseTool.escape leaves when nothing selected
  - Purpose: visible, usable edit mode
  - _Requirements: 3.1, 3.2, 3.3, 3.6, 5.2_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python graphics/interaction developer | Task: Implement per design.md (scene.draw_edit_mode, tools section); tests: pixel probes for dimming and live result with a moved part, double-click enters/leaves, nested enter, Esc order, drawn rect becomes part in new_part_mode, node tool edits a path part | Restrictions: tools stay unaware of drawing; Qt-free tools | Success: tests pass. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Edit bar, panels, keymap and menus
  - Files: presstoshape/views/edit_bar_view.py, presstoshape/views/main_window.py, presstoshape/views/selection_view.py, presstoshape/views/tool_options_view.py, presstoshape/views/keymap.py, presstoshape/views/menu_bar_view.py, tests/views/test_keymap.py
  - EditBar (breadcrumb buttons, Done); central widget with bar + canvas; part-mode combobox (Base/Mixed) and "Composite" name in SelectionOptions; new-part-mode row in tool options; submenu support in MENUS; Path menu composite entries, Object menu with arrange; bindings Ctrl+Alt+C, Page Up/Down, Home/End
  - Purpose: reach and control everything from the UI
  - _Requirements: 1.1, 1.2, 3.6, 3.7, 4.1, 4.2, 4.3, 6.1, 6.2_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: PySide6 developer | Task: Implement the views per design.md; QTest scratch flow of the whole feature offscreen and on desktop GL (incl. Page Up/Down/Home/End not swallowed by the canvas scroll area); screenshot of edit mode | Restrictions: refresh idempotent, blockSignals when writing back; icons via icon_engine; keymap test green | Success: flow works on both renderers; screenshot shows dimming, outlines and bar. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. SVG read/write of Composites
  - Files: presstoshape/formats/svg.py, tests/formats/test_svg.py
  - Write result path + metadata definition (namespace, nested); read back; geometric XOR check; mismatch or broken metadata → plain path + status message
  - Purpose: exchange with other tools without losing editability
  - _Requirements: 7.1–7.5_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer familiar with SVG | Task: Implement per design.md (formats/svg.py section); tests: nested round trip with all modes, Inkscape-style rewritten d still recognized, edited d → plain path + message, broken metadata → path, documents without composites unchanged | Restrictions: don't use svgelements SVG.parse; guard only parsing boundaries | Success: tests pass; a file opens in a browser showing the result. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 9. Benchmarks, docs and final check
  - Files: scripts/bench_canvas.py, README.md, FAQ.md, CLAUDE.md, .spec-workflow/steering/{product,tech,structure}.md
  - Bench case: drag a part of a 20-part Composite in edit mode; benchmark unchanged for documents without Composites; docs describe Composites (hedged wording), containers/edit_path in CLAUDE.md architecture rules
  - Purpose: verified performance and truthful docs
  - _Requirements: All, NFR Performance_
  - _Prompt: Implement the task for spec composites, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on quality and docs | Task: Extend bench, run it (GL and CPU), update docs, final suite and screenshot | Restrictions: delete scratch files one command per deletion; no long-running servers | Success: bench within noise without composites, fluid edit-mode drag; docs updated. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
