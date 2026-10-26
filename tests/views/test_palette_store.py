import json
import time

from presstoshape.formats.palette_files import encode_index, encode_palette
from presstoshape.formats.swatch_library import write_library
from presstoshape.models.colours import Palette, Swatch
from presstoshape.views.palette_store import PaletteStore

RED = (Swatch(1, "", "#ff0000"),)


def write(folder, name, palette):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(encode_palette(palette), encoding="utf-8")


def test_load_follows_the_index_and_appends_unknown_files(tmp_path):
    folder = tmp_path / "palettes"
    for name in ("a", "b", "c"):
        write(folder, f"{name}.json", Palette(0, name.upper(), RED))
    (folder / "index.json").write_text(encode_index(["c.json", "gone.json", "a.json"]), encoding="utf-8")
    result = PaletteStore(folder).load()
    assert [p.name for p in result.palettes] == ["C", "A", "B"]
    assert [p.id for p in result.palettes] == [1, 2, 3]
    assert result.problems == []


def test_damaged_files_are_reported_and_left_alone(tmp_path):
    folder = tmp_path / "palettes"
    write(folder, "good.json", Palette(0, "Good", RED))
    (folder / "bad.json").write_text("{nope", encoding="utf-8")
    store = PaletteStore(folder)
    result = store.load()
    assert [p.name for p in result.palettes] == ["Good"]
    assert result.problems == ["bad.json"]
    store.save((*result.palettes, Palette(9, "Bad", RED)))
    assert (folder / "bad.json").read_text(encoding="utf-8") == "{nope"
    assert (folder / "bad-2.json").is_file()


def test_save_writes_only_changed_palettes_and_deletes_removed(tmp_path):
    folder = tmp_path / "palettes"
    store = PaletteStore(folder)
    store.load()
    first, second = Palette(1, "First", RED), Palette(2, "Second", RED)
    store.save((first, second))
    assert json.loads((folder / "index.json").read_text())["order"] == ["first.json", "second.json"]
    stamp = (folder / "first.json").stat().st_mtime_ns
    time.sleep(0.01)
    renamed = Palette(2, "Renamed", (Swatch(1, "", "#00ff00"),))
    store.save((renamed, first))
    assert (folder / "first.json").stat().st_mtime_ns == stamp
    assert json.loads((folder / "second.json").read_text())["name"] == "Renamed"
    assert json.loads((folder / "index.json").read_text())["order"] == ["second.json", "first.json"]
    store.save((renamed,))
    assert not (folder / "first.json").exists()
    reloaded = PaletteStore(folder).load().palettes
    assert [(p.name, p.swatches[0].color) for p in reloaded] == [("Renamed", "#00ff00")]


def test_duplicate_names_on_disk_are_made_unique(tmp_path):
    folder = tmp_path / "palettes"
    write(folder, "a.json", Palette(0, "Same", RED))
    write(folder, "b.json", Palette(0, "same", RED))
    store = PaletteStore(folder)
    palettes = store.load().palettes
    assert [p.name for p in palettes] == ["Same", "same (2)"]
    store.save(palettes)
    assert json.loads((folder / "b.json").read_text())["name"] == "same (2)"


def test_migration_from_the_single_library(tmp_path):
    (tmp_path / "swatches.json").write_text(write_library(RED), encoding="utf-8")
    result = PaletteStore(tmp_path / "palettes").load()
    assert [(p.name, p.swatches) for p in result.palettes] == [("My swatches", RED)]
    assert not (tmp_path / "swatches.json").exists()
    assert (tmp_path / "swatches.migrated.json").is_file()
    assert [p.name for p in PaletteStore(tmp_path / "palettes").load().palettes] == ["My swatches"]


def test_unreadable_old_library_is_not_migrated(tmp_path):
    (tmp_path / "swatches.json").write_text("{broken", encoding="utf-8")
    result = PaletteStore(tmp_path / "palettes").load()
    assert result.palettes == () and result.problems == ["swatches.json"]
    assert (tmp_path / "swatches.json").read_text(encoding="utf-8") == "{broken"


def test_no_folder_no_library(tmp_path):
    assert PaletteStore(tmp_path / "palettes").load().palettes == ()


def test_loading_500_palettes_is_quick(tmp_path):
    folder = tmp_path / "palettes"
    store = PaletteStore(folder)
    store.load()
    swatches = tuple(Swatch(i, "", f"#{i:06x}") for i in range(1, 33))
    store.save(tuple(Palette(i, f"Palette {i}", swatches) for i in range(1, 501)))
    start = time.perf_counter()
    loaded = PaletteStore(folder).load().palettes
    assert len(loaded) == 500
    assert time.perf_counter() - start < 0.5
