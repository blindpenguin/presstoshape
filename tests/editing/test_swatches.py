import pytest

from presstoshape.editing.operations import guides, palettes, shapes, swatches
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import GradientStop, LinearGradient, RectShape, Style
from tests.helpers import all_shapes


def colors(session, palette):
    return [swatch.color for swatch in swatches.palette_swatches(session, palette)]


def test_document_swatches_are_undoable_and_use_document_ids(session):
    shapes.add_rectangle(session, (0, 0), (10, 10))
    guides.add_guide(session, "horizontal", 5)
    swatches.add_swatch(session, "document", "#FF0000", 0.5, "Red")
    (swatch,) = session.state.document.swatches
    used = {shape.id for shape in all_shapes(session)} | {guide.id for guide in session.state.document.guides}
    assert swatch.id not in used
    assert (swatch.name, swatch.color, swatch.opacity) == ("Red", "#ff0000", 0.5)
    assert session.undo_label == "Add swatch"
    session.undo()
    assert session.state.document.swatches == ()


def test_library_changes_are_not_undo_steps(session):
    swatches.add_swatch(session, "library", "#00ff00")
    swatches.add_swatch(session, "library", "#0000ff")
    library = swatches.palette_swatches(session, "library")
    assert [s.id for s in library] == [1, 2]
    assert not session.can_undo
    (palette,) = session.state.colours.palettes
    assert palette.name == "My swatches"
    assert session.state.colours.current_palette == palette.id


@pytest.mark.parametrize("palette", ["document", "library"])
def test_rename_replace_move_delete(session, palette):
    for color in ("#000001", "#000002", "#000003"):
        swatches.add_swatch(session, palette, color)
    first, second, third = swatches.palette_swatches(session, palette)
    swatches.rename_swatch(session, palette, second.id, "  Middle ")
    swatches.replace_swatch(session, palette, second.id, "#ABCDEF", 2.0)
    middle = swatches.palette_swatches(session, palette)[1]
    assert (middle.name, middle.color, middle.opacity) == ("Middle", "#abcdef", 1.0)
    swatches.move_swatch(session, palette, first.id, 5)
    assert colors(session, palette) == ["#abcdef", "#000003", "#000001"]
    swatches.move_swatch(session, palette, first.id, -1)
    assert colors(session, palette) == ["#abcdef", "#000001", "#000003"]
    swatches.delete_swatch(session, palette, third.id)
    assert colors(session, palette) == ["#abcdef", "#000001"]
    swatches.delete_all_swatches(session, palette)
    assert colors(session, palette) == []


def test_unchanged_document_palette_makes_no_undo_step(session):
    swatches.delete_all_swatches(session, "document")
    swatches.move_swatch(session, "document", 99, 1)
    assert not session.can_undo


def test_copy_between_palettes_skips_duplicates(session):
    swatches.add_swatch(session, "document", "#123456", name="Blue-ish")
    (swatch,) = session.state.document.swatches
    swatches.copy_swatch(session, "document", swatch.id)
    swatches.copy_swatch(session, "document", swatch.id)
    assert [(s.name, s.color) for s in swatches.palette_swatches(session, "library")] == [("Blue-ish", "#123456")]
    library_id = swatches.palette_swatches(session, "library")[0].id
    swatches.copy_swatch(session, "library", library_id)
    assert len(session.state.document.swatches) == 1


def test_import_counts_added_and_is_one_undo_step(session):
    swatches.add_swatch(session, "document", "#000001")
    count = session.undo_count
    added = swatches.import_swatches(session, "document", [("a", "#000001", 1.0), ("b", "#000002", 1.0)])
    assert added == 1
    assert session.undo_count == count + 1
    assert session.undo_label == "Import palette"


def test_add_document_colours(session):
    gradient = LinearGradient(0, 0, 1, 0, (GradientStop(0, "#ff0000"), GradientStop(1, "#00ff00")))
    session.state.document = Document(
        layers=[Layer("L", shapes=[RectShape(1, 0, 0, 1, 1, Style(fill=gradient, stroke="#0000ff"))])], next_id=2
    )
    swatches.add_swatch(session, "document", "#00ff00")
    assert swatches.add_document_colours(session) == 2
    assert colors(session, "document") == ["#00ff00", "#ff0000", "#0000ff"]
    assert session.undo_label == "Add document colours"


def test_library_operations_reach_a_given_palette(session):
    first = palettes.new_palette(session, "First")
    second = palettes.new_palette(session, "Second")
    swatches.add_swatch(session, "library", "#000001")
    assert swatches.palette_swatches(session, "library", second)[0].color == "#000001"
    palettes.set_current_palette(session, first)
    swatches.add_swatch(session, "library", "#000002")
    target = swatches.palette_swatches(session, "library", second)[0]
    swatches.rename_swatch(session, "library", target.id, "Named", palette_id=second)
    swatches.move_swatch(session, "library", target.id, 1, palette_id=second)
    swatches.delete_swatch(session, "library", target.id, palette_id=second)
    assert swatches.palette_swatches(session, "library", second) == ()
    assert [s.color for s in swatches.palette_swatches(session, "library")] == ["#000002"]
