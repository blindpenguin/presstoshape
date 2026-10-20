# Tasks Document

- [x] 1. GroupShape model and geometry
  - Files: presstoshape/models/shapes.py, presstoshape/geometry/transforms.py, presstoshape/editing/queries.py, presstoshape/editing/operations/_document.py, tests/geometry/test_transforms.py, tests/editing/*
  - `GroupShape`, `ContainerShape`, `children_of`; `outline`/`area_outline` → None; `translate`/`transform_shape` recurse; `find_shape` and `with_fresh_ids` recurse into children
  - Purpose: the data type and its math (Req 2.2, 2.6, 6.3)
  - _Leverage: CompositeShape handling in the same functions_
  - _Requirements: 2.2, 2.6, 6.3_
  - _Prompt: Implement the task for spec groups, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement Components 1 and 2 of design.md plus the recursion in find_shape / with_fresh_ids; tests: nested group translate/scale/rotate keeps relative positions, outline None, can_combine ignores groups, fresh ids for everything inside | Restrictions: no Qt; GroupShape has no style attribute; speaking names | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Containers and edit mode for groups
  - Files: presstoshape/editing/containers.py, presstoshape/editing/operations/edit_mode.py (new), presstoshape/editing/operations/composites.py, presstoshape/editing/operations/_document.py, presstoshape/editing/operations/shapes.py, presstoshape/editing/operations/clipboard.py, presstoshape/tools/select.py, presstoshape/tools/base.py, presstoshape/views/edit_bar_view.py, presstoshape/views/tool_options_view.py, presstoshape/views/selection_view.py, other callers, tests/editing/test_containers.py and related
  - Edit chain through Composites and groups; `edited_container` / `edited_composite` / `editing`; `with_children`; empty containers removed with `edit_path` trimmed; enter/leave/leave_all moved to `edit_mode.py` and accepting groups; Composite-only rules use `edited_composite`; paste into a Composite flattens groups; edit bar crumb names per type
  - Purpose: entering groups works like entering Composites (Req 3)
  - _Leverage: containers.change_container, composites.enter/leave, EditBar_
  - _Requirements: 3.1–3.7, 2.7_
  - _Prompt: Implement the task for spec groups, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement Component 3 of design.md and the container-related parts of Components 4 and 7; tests: mixed chains (group → Composite → group), pickable shapes inside, drawing/pasting into an entered group, delete last child removes the group and leaves, undo past group creation trims edit_path, text allowed in groups but not Composites, paste of a group into a Composite gives parts | Restrictions: Composite behaviour unchanged (existing tests stay green); enter/leave not undo steps | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Rendering, hit-testing and edit-mode drawing
  - Files: presstoshape/render/scene.py, presstoshape/render/paths.py, presstoshape/render/hit_test.py, presstoshape/render/handles.py, presstoshape/render/picture.py, presstoshape/views/canvas_view.py, scripts/bench_canvas.py, tests/render/*
  - `draw_shape` for groups with opacity layer only below 1; PathCache bounds/geometry bounds as children's union; hit tests recurse; axis-aligned selection frame; `ShapesPicture` generalizing `DocumentPicture`; edit-mode drawing for an innermost group (children above the dim, live/moving from the overlay, recorded pictures); benchmark scenario with an entered 10k group
  - Purpose: groups look right and stay fast (Req 2.5, 4)
  - _Leverage: DocumentPicture, draw_edit_mode, saveLayerAlpha path from the import spec_
  - _Requirements: 2.5, 4.1–4.4_
  - _Prompt: Implement the task for spec groups, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced with Skia | Task: Implement Component 5 of design.md; pixel tests (group opacity flattens overlap, full-opacity group equals loose shapes), hit and rubber-band tests, bounds and frame tests; bench_canvas before/after (CPU and GL) plus the entered-group scenario | Restrictions: no per-frame Python loops over group contents in the entered-group view; documents without groups render exactly as before | Success: tests green, benchmark unchanged for existing scenarios, entered-group scenario comparable. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Group/ungroup, styling and bounds operations
  - Files: presstoshape/editing/operations/groups.py (new), presstoshape/editing/operations/style.py, presstoshape/editing/operations/transform.py, presstoshape/editing/operations/__init__.py (registration import if needed), tests/editing/test_groups.py, tests/editing/test_style.py, tests/editing/test_transform.py
  - `object.group` / `object.ungroup` with can_run; z-position and layer rules; opacity pushed down on ungroup; `restyle_shape` and `display_style`; `set_bounds`
  - Purpose: users create, dissolve, style and size groups (Req 1, 2.4)
  - _Leverage: containers.change_container, style.restyled, transform_shape_
  - _Requirements: 1.1–1.5, 2.4_
  - _Prompt: Implement the task for spec groups, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement Component 4 of design.md; tests per design (order, top-most z-position, across layers, ungroup in place, opacity factor into leaves/nested groups/Composites, disabled cases, undo labels, style recursion vs group opacity, set_bounds on a group with text and rects) | Restrictions: operations take plain values; one undo step each | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 5. Native format v5
  - Files: presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, tests/formats/samples/v5.p2s, docs/file-format.md, tests/formats/test_p2s.py, tests/formats/test_p2s_migrations.py
  - `group` type (children, optional opacity, no style/transform), id checks recurse, version 5 with identity migration, sample with nested group + Composite inside + entered group, doc rows
  - Purpose: groups survive saving (Req 6)
  - _Leverage: Composite codec, migration rule_
  - _Requirements: 6.1–6.4_
  - _Prompt: Implement the task for spec groups, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement the .p2s part of Component 6; tests: round trip, damaged group cases with paths, v4 sample still opens, v5 sample opens to the expected document and state, clipboard payload keeps groups | Restrictions: follow the native format rules in CLAUDE.md | Success: suite green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 6. SVG groups
  - Files: presstoshape/formats/svg.py, presstoshape/formats/svg_reader.py, tests/formats/test_svg.py, tests/formats/test_svg_import.py
  - Writer `<g opacity>`; reader builds groups from `<g>`/`<a>` (pending opacity rules, empty dropped), nested layers as groups, `<use>` of group/symbol as group, shared depth limit; fixture tests updated to grouped structure; group-opacity note only for layers/root
  - Purpose: files keep their structure (Req 5)
  - _Leverage: svg_reader visit_group / _use, writer _shape_element_
  - _Requirements: 5.1–5.7_
  - _Prompt: Implement the task for spec groups, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced with SVG | Task: Implement the SVG part of Component 6; tests per design; time the 10k-shape import script before/after | Restrictions: layers stay layers; PressToShape's own files round-trip exactly | Success: suite green, import time comparable. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 7. Menus, shortcuts and selection panel
  - Files: presstoshape/views/keymap.py, presstoshape/views/selection_view.py, presstoshape/icons.py, scripts/generate_icons.py, presstoshape/assets/icons/*.svg, tests/views/*
  - Ctrl+G / Ctrl+Shift+G in the Object menu (icons if the Object toolbar has arrange icons); selection panel heading, X/Y/W/H for a group via set_bounds, `display_style`, fill rule visibility for groups
  - Purpose: the feature is reachable and visible (Req 1, 2.4)
  - _Leverage: keymap entries of arrange commands, SelectionOptions_
  - _Requirements: 1.1, 1.3, 2.4, NFR Usability_
  - _Prompt: Implement the task for spec groups, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python/PySide6 developer | Task: Implement Component 7 of design.md; keymap test (no clashes), panel tests for a selected group; QTest scratch run offscreen and with GL (group, drag, enter, move child, Esc, ungroup; open the Figma fixture and enter its group); screenshots en/de | Restrictions: views never assign AppState; no other new shortcuts | Success: tests green, flows verified on both renderers. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 8. Translations, docs and final check
  - Files: presstoshape/assets/translations/*, README.md, FAQ.md, CLAUDE.md, .spec-workflow/steering/product.md, .spec-workflow/steering/structure.md, FEATURE_GAPS.md (local)
  - German complete; README/FAQ groups and SVG structure (hedged); CLAUDE.md container wording (Composites and groups); steering docs; full suite, self-test, bench, screenshots en/de
  - Purpose: complete, documented feature
  - _Requirements: all_
  - _Prompt: Implement the task for spec groups, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on docs | Task: Translate, update docs, run all checks; tell the user what to try by hand | Restrictions: British English, hedged public wording, no em dashes in user-facing prose; FEATURE_GAPS.md stays uncommitted | Success: suite green, docs match behaviour. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
