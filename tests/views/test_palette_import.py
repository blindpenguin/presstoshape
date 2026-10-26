from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from presstoshape.editing.operations import palettes
from presstoshape.editing.session import Session
from presstoshape.models.colours import Palette, Swatch
from presstoshape.views import palette_import
from presstoshape.views.palette_import import ClashDialog, import_palettes, read_file, read_items

GPL = "GIMP Palette\r\n#Palette Name: {name}\r\n#Colors: 2\r\n0\t0\t0\t000000\r\n29\t43\t83\t1D2B53\r\n"


@pytest.fixture(autouse=True)
def app():
    QApplication.instance() or QApplication([])


def lospec_files(tmp_path, names):
    """Lospec-style GIMP palettes, as a user would select them together in the file dialog."""
    folder = tmp_path / "downloads"
    folder.mkdir(exist_ok=True)
    files = []
    for name in names:
        target = folder / f"{name.lower()}.gpl"
        target.write_text(GPL.format(name=name), encoding="utf-8")
        files.append(target)
    return files


def test_read_file_formats_and_images(tmp_path):
    image = QImage(16, 8, QImage.Format.Format_RGBA8888)
    image.fill(QColor("#1d2b53"))
    for x in range(8, 16):
        for y in range(8):
            image.setPixelColor(x, y, QColor("#ffccaa"))
    image.save(str(tmp_path / "palette-8x.png"))
    name, colors = read_file(tmp_path / "palette-8x.png")
    assert name is None and [color for _n, color, _o in colors] == ["#1d2b53", "#ffccaa"]
    (tmp_path / "p.gpl").write_text(GPL.format(name="PICO"), encoding="utf-8")
    assert read_file(tmp_path / "p.gpl")[0] == "PICO"
    (tmp_path / "notes.doc").write_bytes(b"nothing")
    with pytest.raises(ValueError):
        read_file(tmp_path / "notes.doc")


def test_read_items_names_and_failures(tmp_path):
    (tmp_path / "named.gpl").write_text(GPL.format(name="Named"), encoding="utf-8")
    (tmp_path / "plain.hex").write_text("000000\n", encoding="utf-8")
    (tmp_path / "broken.pal").write_text("JASC-PAL\n0100\n0\n", encoding="utf-8")
    (tmp_path / "junk.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "big.hex").write_text("".join(f"{i:06x}\n" for i in range(1100)), encoding="utf-8")
    files = sorted(tmp_path.iterdir())
    result = read_items(files)
    assert [item.name for item in result.items] == ["Named", "plain"]
    assert dict(result.failures) == {
        "big.hex": "has more than 1024 colours",
        "broken.pal": "has no colours",
        "junk.txt": "isn't a palette PressToShape can read",
    }


def test_clash_dialog_choices():
    items = [palettes.ImportItem("A", ()), palettes.ImportItem("B", ())]
    dialog = ClashDialog(items, [Path("a.gpl"), Path("b.gpl")], [0, 1])
    assert dialog.choices() == {0: "keep", 1: "keep"}
    dialog.set_all("replace")
    dialog.set_choice(1, "skip")
    assert dialog.choices() == {0: "replace", 1: "skip"}


def test_import_flow_with_clashes(tmp_path):
    session = Session()
    palettes.set_palettes(session, (Palette(1, "B", (Swatch(1, "", "#ffffff"),)),))
    files = lospec_files(tmp_path, ["A", "B", "C"])
    asked, reports = [], []

    def ask(parent, items, sources, clashing):
        asked.append([items[index].name for index in clashing])
        return {clashing[0]: "replace"}

    counts = import_palettes(None, session, files, ask, lambda parent, text: reports.append(text))
    assert asked == [["B"]]
    assert counts == palettes.ImportCounts(imported=2, replaced=1)
    assert [p.name for p in session.state.colours.palettes] == ["B", "A", "C"]
    assert [s.color for s in session.state.colours.palettes[0].swatches] == ["#000000", "#1d2b53"]
    assert "2 palettes imported." in reports[0] and "1 replaced." in reports[0]


def test_cancelling_the_clash_dialog_imports_nothing(tmp_path):
    session = Session()
    palettes.set_palettes(session, (Palette(1, "A"),))
    counts = import_palettes(None, session, lospec_files(tmp_path, ["A", "B"]), lambda *args: None, print)
    assert counts is None
    assert [p.name for p in session.state.colours.palettes] == ["A"]


def test_too_many_files_are_refused_with_a_message(tmp_path, monkeypatch):
    monkeypatch.setattr(palette_import, "MAX_FILES", 1)
    session, reports = Session(), []
    files = lospec_files(tmp_path, ["A", "B"])
    assert import_palettes(None, session, files, report=lambda parent, text: reports.append(text)) is None
    assert "at most 1" in reports[0]
    assert session.state.colours.palettes == ()


def test_one_clean_file_needs_no_summary(tmp_path):
    session, reports = Session(), []
    path = tmp_path / "solo.gpl"
    path.write_text(GPL.format(name="Solo"), encoding="utf-8")
    import_palettes(None, session, [path], report=lambda parent, text: reports.append(text))
    assert reports == []
    assert palettes.current_palette(session.state).name == "Solo"
