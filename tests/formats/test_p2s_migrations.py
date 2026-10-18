"""Every format version's sample file must keep opening, to the same document, in every later version."""

from pathlib import Path

from presstoshape.formats.p2s import SavedState, read_p2s
from presstoshape.formats.p2s_migrations import CURRENT_VERSION, MIGRATIONS, upgrade
from presstoshape.models.app_state import Document, Layer, Tool
from presstoshape.models.shapes import CompositeShape, EllipseShape, LineTo, MoveTo, PathShape, RectShape, Style

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
