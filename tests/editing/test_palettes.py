from presstoshape.editing.operations import palettes
from presstoshape.models.colours import Palette, Swatch


def names(session):
    return [palette.name for palette in session.state.colours.palettes]


def current(session):
    return palettes.current_palette(session.state)


def test_unique_names():
    existing = [Palette(1, "PICO-8"), Palette(2, "pico-8 (2)"), Palette(3, "Mine")]
    assert palettes.unique_name(existing, "  New   one ") == "New one"
    assert palettes.unique_name(existing, "pico-8") == "pico-8 (3)"
    assert palettes.unique_name(existing, "PICO-8 (2)") == "PICO-8 (3)"
    assert palettes.unique_name(existing, "") == "Palette"
    assert palettes.unique_name(existing, "Mine", ignore_id=3) == "Mine"


def test_new_palette_is_current_and_named_uniquely(session):
    first = palettes.new_palette(session, "Warm")
    second = palettes.new_palette(session, "warm")
    assert names(session) == ["Warm", "warm (2)"]
    assert session.state.colours.current_palette == second != first
    assert not session.can_undo


def test_rename_refuses_empty_and_taken_names(session):
    first = palettes.new_palette(session, "A")
    palettes.new_palette(session, "B")
    assert not palettes.rename_palette(session, first, "  ")
    assert not palettes.rename_palette(session, first, "b")
    assert palettes.rename_palette(session, first, " C  d ")
    assert names(session) == ["C d", "B"]


def test_duplicate_goes_after_the_original(session):
    first = palettes.new_palette(session, "A", (Swatch(1, "", "#000000"),))
    palettes.new_palette(session, "B")
    copy = palettes.duplicate_palette(session, first)
    assert names(session) == ["A", "A copy", "B"]
    assert current(session).id == copy
    assert current(session).swatches == palettes.find_palette(session.state, first).swatches
    assert palettes.duplicate_palette(session, 99) is None


def test_delete_moves_current_to_a_neighbour(session):
    a, b, c = (palettes.new_palette(session, name) for name in "ABC")
    palettes.set_current_palette(session, b)
    palettes.delete_palettes(session, [b])
    assert current(session).id == c
    palettes.delete_palettes(session, [c])
    assert current(session).id == a
    palettes.delete_palettes(session, [a])
    assert session.state.colours.palettes == () and session.state.colours.current_palette is None


def test_order(session):
    a, b, c = (palettes.new_palette(session, name) for name in "ABC")
    palettes.set_palette_order(session, [c, 99, a])
    assert names(session) == ["C", "A", "B"]


def test_set_palettes_picks_current_by_name(session):
    loaded = (Palette(1, "One"), Palette(2, "Two"))
    palettes.set_palettes(session, loaded, "Two")
    assert current(session).name == "Two"
    palettes.set_palettes(session, loaded, "Gone")
    assert current(session).name == "One"
    palettes.set_current_palette(session, 42)
    assert current(session).name == "One"


def item(name, *colors):
    return palettes.ImportItem(name, tuple(("", color, 1.0) for color in colors))


def test_clashes_with_existing_and_within_the_batch():
    existing = [Palette(1, "PICO-8")]
    items = [item("pico-8"), item("Endesga"), item("ENDESGA"), item("Other")]
    assert palettes.clashes(existing, items) == [0, 2]


def test_apply_import_keep_replace_skip(session):
    original = palettes.new_palette(session, "PICO-8", (Swatch(1, "", "#000000"),))
    palettes.new_palette(session, "Keep me")
    palettes.set_current_palette(session, original)
    items = [item("PICO-8", "#111111", "#222222"), item("Keep me", "#333333"), item("New", "#444444")]
    counts = palettes.apply_import(session, items, {0: "replace", 1: "skip"})
    assert counts == palettes.ImportCounts(imported=1, replaced=1, skipped=1)
    assert names(session) == ["PICO-8", "Keep me", "New"]
    replaced = palettes.find_palette(session.state, original)
    assert [s.color for s in replaced.swatches] == ["#111111", "#222222"]
    assert [s.id for s in replaced.swatches] == [1, 2]
    assert current(session).id == original


def test_apply_import_keep_numbers_and_replace_reaches_earlier_batch_items(session):
    items = [item("A", "#000001"), item("a", "#000002"), item("A", "#000003")]
    counts = palettes.apply_import(session, items, {1: "keep", 2: "replace"})
    assert counts == palettes.ImportCounts(imported=2, replaced=1)
    assert names(session) == ["A", "a (2)"]
    assert [s.color for s in session.state.colours.palettes[0].swatches] == ["#000003"]
    assert current(session).name == "A"


def test_apply_import_defaults_to_keep(session):
    palettes.new_palette(session, "A")
    palettes.apply_import(session, [item("A", "#000001")], {})
    assert names(session) == ["A", "A (2)"]
