# Tasks Document

- [x] 1. Curve fitting
  - Files: presstoshape/geometry/fitting.py, tests/geometry/test_fitting.py
  - `StrokeSample`; `fit_stroke(samples, smoothing, pixel_size, close_distance_px)` with decimation, closing, corner detection, corner-preserving pre-smoothing, Schneider fit per run with shared tangents at smooth joins, safeguards (degenerate runs, overshoot fallback, recursion cap)
  - Purpose: the pure geometry behind the pencil (Req 2, 3)
  - _Leverage: geometry/segments (Segment types), Schneider 1990_
  - _Requirements: 1.4, 1.5, 2.2–2.4, 3.1–3.3_
  - _Prompt: Implement the task for spec pencil-tool, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer experienced in computational geometry | Task: Implement fit_stroke per design.md with the tests listed there (line, noisy/clean circle closed with few segments, L corner kept, sine wave smooth joins, deviation ≤ tolerance, more smoothing → fewer segments, tiny/identical → None, zoom independence, no overshoot, 5000 points < 100 ms) | Restrictions: pure Python, no new dependencies, no Qt; speaking names | Success: tests green, architecture test green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 2. Model, operations and file format version 3
  - Files: presstoshape/models/app_state.py, presstoshape/editing/operations/shapes.py, presstoshape/editing/operations/view.py, presstoshape/formats/p2s.py, presstoshape/formats/p2s_migrations.py, tests/formats/samples/v3.p2s, docs/file-format.md, related tests
  - `Tool.PENCIL`, default Pencil style, `AppState.pencil_smoothing`; `shapes.add_drawn_path`; `view.set_pencil_smoothing`, `tool_name` for the Pencil; `.p2s` `tools.pencil_smoothing`, version 3 with identity migration, v3 sample, doc row
  - Purpose: state and persistence (Req 1.3, 1.7, 2.5, 4.1)
  - _Leverage: shapes._add, p2s state codec, migration rule_
  - _Requirements: 1.3, 1.7, 2.5, 4.1_
  - _Prompt: Implement the task for spec pencil-tool, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python developer | Task: Implement per design.md; tests: add_drawn_path in layer/Composite/hidden layer, smoothing clamped and not a document edit, v3 round trip, v2 sample opens with default 50, bad value refused | Restrictions: follow the native format rules in CLAUDE.md | Success: tests green. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 3. Pencil tool, registry, keymap, icon and tool options
  - Files: presstoshape/tools/pencil.py, presstoshape/tools/registry.py, presstoshape/views/keymap.py, presstoshape/views/tool_options_view.py, presstoshape/icons.py, scripts/generate_icons.py, presstoshape/assets/icons/tool_pencil.svg, tests/tools/test_pencil.py, tests/views (tool options)
  - `PencilTool` (samples, live preview in the Pencil style, release → fit → add_drawn_path, Esc, click → nothing); registry entry "Penc&il" after the Pen; `F` shortcut with icon; Pencil tool options page (style + Smoothing slider + hint)
  - Purpose: the tool users draw with (Req 1, 2.1, 4.2)
  - _Leverage: PenTool, ToolOptionsPanel, StyleEditor, generate_icons_
  - _Requirements: 1.1–1.8, 2.1, 4.2_
  - _Prompt: Implement the task for spec pencil-tool, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Python/PySide6 developer | Task: Implement per design.md; tool tests with ToolDriver (drag, preview style, Esc, click, closing, Composite part, hidden layer, smoothing affects node count); slider ↔ state test; QTest scratch run offscreen and with GL with many mouse moves (wavy stroke and closed loop), screenshot with the Node tool showing the nodes; bench_canvas unchanged | Restrictions: tools stay Qt-free; no per-move refit; delete scratch files one command each | Success: tests green, drawing verified on both renderers. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._

- [x] 4. Translations, docs and final check
  - Files: presstoshape/assets/translations/*, README.md, FAQ.md, .spec-workflow/steering/*.md, FEATURE_GAPS.md (local)
  - German complete; README tool list and Pencil description (hedged); FAQ "what can it do"; product.md current features; structure.md tree; full suite, self-test, screenshots en/de
  - Purpose: complete, documented feature
  - _Requirements: all_
  - _Prompt: Implement the task for spec pencil-tool, first run spec-workflow-guide to get the workflow guide then implement the task: Role: Developer focused on docs | Task: Translate, update docs, run checks; tell the user what to try by hand (mouse and tablet) | Restrictions: British English, hedged wording, no em dashes in user-facing prose; FEATURE_GAPS.md stays uncommitted | Success: suite green, docs match behaviour. Before starting set this task to [-] in tasks.md; after finishing log it with log-implementation (with artifacts) and set it to [x]._
