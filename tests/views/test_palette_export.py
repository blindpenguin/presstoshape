from presstoshape.formats.palettes import read_named_palette
from presstoshape.models.colours import Palette, Swatch
from presstoshape.views.palette_export import export_names, write_palettes

PALETTES = (
    Palette(1, "PICO-8", (Swatch(1, "Black", "#000000"),)),
    Palette(2, "pico-8 (2)", (Swatch(1, "", "#ff004d", 0.5),)),
    Palette(3, "Grün", (Swatch(1, "", "#00ff00"),)),
)


def test_export_names_are_unique_and_safe():
    assert export_names(PALETTES, ".gpl") == ["pico-8.gpl", "pico-8-2.gpl", "gr-n.gpl"]


def test_write_palettes_keeps_names_and_opacity(tmp_path):
    assert write_palettes(tmp_path, PALETTES, ".txt") == []
    name, colors = read_named_palette(".txt", (tmp_path / "pico-8-2.txt").read_text(encoding="utf-8"))
    assert name == "pico-8 (2)"
    assert colors == [("", "#ff004d", 0.502)]
    assert sorted(path.name for path in tmp_path.iterdir()) == ["gr-n.txt", "pico-8-2.txt", "pico-8.txt"]


def test_write_failures_are_reported(tmp_path):
    missing = tmp_path / "missing"
    failures = write_palettes(missing, PALETTES[:1], ".hex")
    assert [name for name, _error in failures] == ["pico-8.hex"]
