"""Every format version's sample file must keep opening, to the same document, in every later version."""

from pathlib import Path

from presstoshape.formats.p2s import SavedState, read_p2s
from presstoshape.formats.p2s_migrations import CURRENT_VERSION, MIGRATIONS, upgrade
from presstoshape.models.app_state import Document, Layer, Tool
from presstoshape.models.layout import GridSettings, Guide
from presstoshape.models.shapes import (
    CompositeShape,
    EllipseShape,
    GroupShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)

SAMPLES = Path(__file__).resolve().parent / "samples"


def expected_v1() -> tuple[Document, SavedState]:
    """What tests/formats/samples/v1.p2s holds (written by write_p2s at format version 1)."""
    red = Style(fill="#ff0000", stroke=None, stroke_width=0.0)
    parts = (RectShape(4, 0.0, 0.0, 100.0, 60.0, red), EllipseShape(5, 80.0, 30.0, 25.0, 25.0, red))
    composite = CompositeShape(3, parts, ("add", "subtract"), red)
    document = Document(
        width=320.0,
        height=200.0,
        layers=[
            Layer("Layer 1", True, [RectShape(1, 10.0, 10.0, 50.0, 40.0, Style(), (0.0, 1.0, -1.0, 0.0, 70.0, 0.0))]),
            Layer("Top", False, [PathShape(2, (MoveTo(0.0, 0.0), LineTo(30.5, 12.25)), Style(fill=None)), composite]),
        ],
        next_id=6,
    )
    state = SavedState(
        zoom_percent=150,
        view_center=(160.0, 100.0),
        tool_styles={Tool.RECTANGLE: red},
        font_size=20.0,
        new_part_mode="exclude",
        selection=frozenset({4}),
        selected_layer=1,
        edit_path=(3,),
    )
    return document, state


def test_every_old_version_has_a_migration_and_a_sample():
    assert set(MIGRATIONS) == set(range(1, CURRENT_VERSION))
    for version in range(1, CURRENT_VERSION + 1):
        assert (SAMPLES / f"v{version}.p2s").is_file()


def test_current_version_payload_passes_unchanged():
    payload = {"format_version": CURRENT_VERSION, "document": {}}
    assert upgrade(payload, CURRENT_VERSION) == payload


def test_v1_sample_opens_to_the_expected_document():
    assert read_p2s((SAMPLES / "v1.p2s").read_bytes()) == expected_v1()


def expected_v2() -> tuple[Document, SavedState]:
    """What tests/formats/samples/v2.p2s holds: an A4 document in mm at 300 DPI."""
    red = Style(fill="#ff0000", stroke=None, stroke_width=0.0)
    document = Document(
        width=2480.3149606299212,
        height=3507.8740157480315,
        layers=[Layer("Layer 1", True, [RectShape(1, 118.0, 118.0, 1181.0, 590.5, red)])],
        next_id=2,
        unit="mm",
        dpi=300.0,
    )
    return document, SavedState(zoom_percent=25, view_center=(1240.0, 1754.0), selection=frozenset({1}))


def test_v1_documents_become_pixels_at_96_dpi():
    document, _state = read_p2s((SAMPLES / "v1.p2s").read_bytes())
    assert (document.unit, document.dpi) == ("px", 96.0)


def test_v2_sample_opens_to_the_expected_document():
    assert read_p2s((SAMPLES / "v2.p2s").read_bytes()) == expected_v2()


def expected_v3() -> tuple[Document, SavedState]:
    """What tests/formats/samples/v3.p2s holds: a pencil path, the Pencil's style and its smoothing."""
    pencil = Style(fill=None, stroke="#18181b", stroke_width=2.0)
    path = PathShape(1, (MoveTo(10.0, 10.0), LineTo(110.0, 60.0)), pencil)
    document = Document(width=400.0, height=300.0, layers=[Layer("Layer 1", True, [path])], next_id=2)
    state = SavedState(zoom_percent=100, tool_styles={Tool.PENCIL: pencil}, pencil_smoothing=80)
    return document, state


def test_v2_files_keep_the_default_smoothing():
    _document, state = read_p2s((SAMPLES / "v2.p2s").read_bytes())
    assert state.pencil_smoothing is None


def test_v3_sample_opens_to_the_expected_document():
    assert read_p2s((SAMPLES / "v3.p2s").read_bytes()) == expected_v3()


def expected_v4() -> tuple[Document, SavedState]:
    """What tests/formats/samples/v4.p2s holds: opacities, fill rule, stroke options, rect radii, text anchor."""
    card = Style(
        fill="#3b82f6",
        stroke="#18181b",
        stroke_width=2.0,
        opacity=0.75,
        fill_opacity=0.5,
        fill_rule="evenodd",
        join="bevel",
        miter_limit=8.0,
    )
    dashed = Style(
        fill=None,
        stroke="#18181b",
        stroke_width=4.0,
        stroke_opacity=0.5,
        cap="round",
        join="round",
        dashes=(8.0, 4.0),
        dash_offset=2.0,
    )
    shapes = [
        RectShape(1, 20.0, 20.0, 160.0, 100.0, card, rx=12.0, ry=8.0),
        PathShape(2, (MoveTo(20.0, 200.0), LineTo(380.0, 200.0)), dashed),
        TextShape(3, 200.0, 260.0, "Centred", 24.0, Style(fill="#000000", stroke=None), anchor="middle"),
    ]
    document = Document(width=400.0, height=300.0, layers=[Layer("Layer 1", True, shapes)], next_id=4)
    return document, SavedState(zoom_percent=100, tool_styles={Tool.RECTANGLE: card})


def test_v3_files_get_default_styles():
    document, _state = read_p2s((SAMPLES / "v3.p2s").read_bytes())
    style = document.layers[0].shapes[0].style
    assert (style.opacity, style.fill_rule, style.cap, style.dashes) == (1.0, "nonzero", "butt", ())


def test_v4_sample_opens_to_the_expected_document():
    assert read_p2s((SAMPLES / "v4.p2s").read_bytes()) == expected_v4()


def expected_v5() -> tuple[Document, SavedState]:
    """What tests/formats/samples/v5.p2s holds: nested groups with opacity, a Composite inside a group, and the
    outer group entered."""
    red = Style(fill="#ff0000", stroke=None, stroke_width=0.0)
    blue = Style(fill="#0000ff", stroke=None, stroke_width=0.0)
    composite = CompositeShape(
        4,
        (RectShape(5, 20.0, 20.0, 60.0, 40.0, red), EllipseShape(6, 80.0, 40.0, 20.0, 20.0, red)),
        ("add", "subtract"),
        blue,
    )
    inner = GroupShape(7, (TextShape(8, 20.0, 100.0, "Grouped", 18.0, red),), opacity=0.5)
    outer = GroupShape(1, (RectShape(2, 0.0, 0.0, 120.0, 120.0, blue), composite, inner), opacity=0.75)
    shapes = [outer, RectShape(3, 200.0, 50.0, 40.0, 40.0, red)]
    document = Document(width=300.0, height=200.0, layers=[Layer("Layer 1", True, shapes)], next_id=9)
    return document, SavedState(zoom_percent=100, selection=frozenset({7}), edit_path=(1,))


def test_v5_sample_opens_to_the_expected_document():
    assert read_p2s((SAMPLES / "v5.p2s").read_bytes()) == expected_v5()


def expected_v6() -> tuple[Document, SavedState]:
    """What tests/formats/samples/v6.p2s holds: guides, an own grid and their view state."""
    document = Document(
        width=400.0,
        height=300.0,
        layers=[Layer("Layer 1", True, [RectShape(1, 40.0, 40.0, 100.0, 60.0, Style())])],
        next_id=4,
        unit="mm",
        dpi=96.0,
        guides=(Guide(2, "vertical", 40.0), Guide(3, "horizontal", 100.0)),
        grid=GridSettings(18.897637795275593, 2),
    )
    return document, SavedState(zoom_percent=100, show_grid=True, show_guides=True, lock_guides=True)


def test_v5_files_have_no_guides_or_grid():
    document, state = read_p2s((SAMPLES / "v5.p2s").read_bytes())
    assert document.guides == () and document.grid is None and state.show_grid is None


def test_v6_sample_opens_to_the_expected_document():
    assert read_p2s((SAMPLES / "v6.p2s").read_bytes()) == expected_v6()


def expected_v7() -> tuple[Document, SavedState]:
    """What tests/formats/samples/v7.p2s holds: a hidden shape, a locked group with a hidden child, a hidden
    Composite part and a locked layer."""
    red = Style(fill="#ff0000", stroke=None)
    parts = (RectShape(7, 0.0, 50.0, 40.0, 40.0, red), EllipseShape(8, 40.0, 70.0, 15.0, 15.0, red, hidden=True))
    children = (RectShape(4, 0.0, 0.0, 20.0, 20.0, red, hidden=True), RectShape(5, 30.0, 0.0, 20.0, 20.0, red))
    group = GroupShape(3, children, locked=True)
    composite = CompositeShape(6, parts, ("add", "subtract"), red)
    document = Document(
        width=200.0,
        height=150.0,
        layers=[
            Layer("Sketch", True, [RectShape(1, 0.0, 0.0, 200.0, 150.0, Style(), locked=True)], locked=True),
            Layer("Layer 2", True, [RectShape(2, 10.0, 10.0, 30.0, 30.0, red, hidden=True), group, composite]),
        ],
        next_id=9,
    )
    return document, SavedState(zoom_percent=100, selected_layer=1)


def test_v6_files_open_with_everything_shown_and_unlocked():
    document, _state = read_p2s((SAMPLES / "v6.p2s").read_bytes())
    assert all(not layer.locked for layer in document.layers)
    assert all(not shape.hidden and not shape.locked for layer in document.layers for shape in layer.shapes)


def test_v7_sample_opens_to_the_expected_document():
    assert read_p2s((SAMPLES / "v7.p2s").read_bytes()) == expected_v7()
