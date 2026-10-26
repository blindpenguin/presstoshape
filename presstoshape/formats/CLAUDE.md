# formats/ — SVG and .p2s

- `svg.py` (SVG write + public read API), `svg_reader.py` (cascade, `<use>`, text lines), `css.py` (`<style>` subset)
- `svg_values.py` / `svg_names.py` / `svg_page.py` / `svg_notes.py` (import notes for the report dialog), `svg_nodetypes.py` (corner nodes as `sodipodi:nodetypes`), `svg_corners.py` (live corners in path metadata)
- `image_info.py` (picture header probe: type, size, limits, digest) + `svg_images.py` (`<image>` sources, never the network)
- `p2s.py` + `p2s_migrations.py` (native .p2s, `docs/file-format.md`)
- `clipboard.py` (shape payload for copy/paste, not migrated: falls back to SVG)

## Rules

- **svgelements** — only for parsing path `d` data, colors, lengths and transform strings (`formats/svg_values.py`, colours in `formats/svg_reader.py`). Don't use its `SVG.parse` document reader: it silently drops `display:none` groups (hidden layers) and `<text>`.
- Native format `.p2s` (ZIP + JSON, `formats/p2s.py`): encoders/decoders are explicit per type, never generic over dataclass fields. Any change to what files store bumps `CURRENT_VERSION` in `formats/p2s_migrations.py`, adds a migration from the previous version, a `tests/formats/samples/v<N>.p2s` sample, and a row in `docs/file-format.md`. Everything the app can save must open again (tested round trips). Saves are atomic (`documents.write_atomically`) and can keep one backup of the previous file (`name.backup.ext`).
- `.p2s` keeps image bytes as `media/<digest>.<ext>`, written once per distinct blob. Reference images are left out of saved SVG.
- SVG conformance (`docs/svg-conformance.md`): `uv run python scripts/svg_conformance.py fetch` once, then `report` (HTML with side-by-side images in `build/svg-conformance/`). `tests/scripts/svg_conformance_pass.txt` is checked by pytest while the suite is fetched; add a test only after comparing it by eye, keep reviewed-but-wrong ones as `!name # reason`, never drop an entry to make a change pass without saying so. Saved SVG is also rendered by resvg (dev dep) and must match our canvas (`tests/formats/test_svg_generator.py`).
