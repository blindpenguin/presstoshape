import copy
import io
import json
import math
import re
import zipfile

import pytest

from presstoshape.formats import p2s
from presstoshape.formats.p2s import (
    P2sError,
    SavedState,
    decode_document,
    encode_document,
    read_p2s,
    read_preview,
    write_p2s,
)
from presstoshape.formats.p2s_migrations import CURRENT_VERSION
from presstoshape.formats.svg import read_svg
from presstoshape.models.app_state import Document, Layer, Tool
from presstoshape.models.layout import GridSettings, Guide
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    GradientStop,
    GroupShape,
    LinearGradient,
    LineTo,
    MoveTo,
    PathShape,
    RadialGradient,
    RectShape,
    Style,
    TextShape,
)

RED = Style(fill="#ff0000", stroke=None, stroke_width=0.0)
OUTLINE = Style(fill=None, stroke="#18181b", stroke_width=1.25)
ROTATED = (math.cos(0.3), math.sin(0.3), -math.sin(0.3), math.cos(0.3), 12.5, -3.0)
SKEWED = (1.0, 0.0, 0.4, 1.0, 0.0, 0.0)
FULL = Style(
    fill="#123456",
    stroke="#654321",
    stroke_width=3.5,
    opacity=0.5,
    fill_opacity=0.25,
    stroke_opacity=0.75,
    fill_rule="evenodd",
    cap="round",
    join="bevel",
    miter_limit=7.0,
    dashes=(4.0, 2.0, 1.0, 2.0),
    dash_offset=1.5,
)


def _sample_document() -> Document:
    inner = CompositeShape(
        20, (RectShape(21, 0, 0, 40, 40, RED), EllipseShape(22, 40, 40, 15, 15, RED)), ("add", "exclude"), RED
    )
    composite = CompositeShape(
        10, (RectShape(11, 0.1, 0.2, 100, 60, Style()), inner), ("add", "subtract"), Style(fill="#00aa00")
    )
    path = PathShape(
        3, (MoveTo(0, 0), LineTo(10.000000001, 0), CubicTo(1, 2, 3, 4, 5, 6), Close(), MoveTo(7, 7)), OUTLINE
    )
    return Document(
        width=1920.0,
        height=1080.5,
        layers=[
            Layer("Background", True, [RectShape(1, -5, 1e-9, 1e6, 0.0, Style(), ROTATED)]),
            Layer("Empty", True, []),
            Layer("Hidden ünïcode", False, [path, TextShape(4, 10, 20, 'Hi\n"there" ☺', 18.5, RED, SKEWED), composite]),
            Layer(
                "Styled",
                True,
                [
                    RectShape(30, 0, 0, 50, 40, FULL, rx=5, ry=8),
                    TextShape(31, 10, 20, "Centred", 12, FULL, anchor="middle"),
                    CompositeShape(32, (RectShape(33, 0, 0, 9, 9, FULL),), ("add",), FULL),
                ],
            ),
        ],
        next_id=34,
    )


def _round_trip(document: Document) -> Document:
    return decode_document(json.loads(json.dumps(encode_document(document))))


def test_document_round_trips_exactly():
    original = _sample_document()
    assert _round_trip(original) == original


def test_encoding_is_stable_across_round_trips():
    first = json.dumps(encode_document(_sample_document()))
    second = json.dumps(encode_document(_round_trip(_sample_document())))
    assert first == second


def test_identity_transform_is_left_out_and_segments_are_compact():
    encoded = encode_document(_sample_document())
    hidden_layer = encoded["layers"][2]["shapes"]
    assert "transform" not in hidden_layer[0]
    assert hidden_layer[0]["segments"][2] == ["C", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert hidden_layer[0]["segments"][3] == ["Z"]
    assert encoded["layers"][0]["shapes"][0]["transform"] == list(ROTATED)


def test_next_id_is_raised_above_existing_ids():
    encoded = encode_document(_sample_document())
    encoded["next_id"] = 2
    assert decode_document(encoded).next_id == 34


def _broken(change) -> str:
    encoded = copy.deepcopy(encode_document(_sample_document()))
    change(encoded)
    with pytest.raises(P2sError) as error:
        decode_document(encoded)
    return str(error.value)


@pytest.mark.parametrize(
    "change, where",
    [
        (lambda doc: doc["layers"][0]["shapes"][0].update(width="wide"), "document.layers[0].shapes[0].width"),
        (lambda doc: doc["layers"][0]["shapes"][0].update(width=-1), "document.layers[0].shapes[0].width"),
        (lambda doc: doc["layers"][0]["shapes"][0].update(x=float("nan")), "document.layers[0].shapes[0].x"),
        (lambda doc: doc["layers"][0]["shapes"][0].update(x=True), "document.layers[0].shapes[0].x"),
        (lambda doc: doc["layers"][0]["shapes"][0].update(type="star"), "document.layers[0].shapes[0].type"),
        (lambda doc: doc["layers"][0]["shapes"][0].pop("style"), "document.layers[0].shapes[0]"),
        (lambda doc: doc["layers"][0]["shapes"][0].update(transform=[1, 0, 0]), "transform"),
        (lambda doc: doc["layers"][2]["shapes"][0]["segments"].append(["Q", 1, 2]), "segments[5]"),
        (lambda doc: doc["layers"][2]["shapes"][2]["modes"].__setitem__(1, "melt"), "modes[1]"),
        (lambda doc: doc["layers"][2]["shapes"][2]["parts"].pop(), "shapes[2]"),
        (lambda doc: doc["layers"][1]["shapes"].append({"type": "rect"}), "document.layers[1].shapes[0]"),
        (lambda doc: doc["layers"][2]["shapes"][1].update(id=1), "id twice"),
        (lambda doc: doc["layers"][2].update(visible="yes"), "document.layers[2].visible"),
        (lambda doc: doc.update(layers=[]), "document.layers"),
        (lambda doc: doc.update(width=0), "document.width"),
        (lambda doc: doc["layers"][3]["shapes"][0]["style"].update(opacity=1.5), "style.opacity"),
        (lambda doc: doc["layers"][3]["shapes"][0]["style"].update(fill_opacity=-0.1), "style.fill_opacity"),
        (lambda doc: doc["layers"][3]["shapes"][0]["style"].update(fill_rule="odd"), "style.fill_rule"),
        (lambda doc: doc["layers"][3]["shapes"][0]["style"].update(cap="pointy"), "style.cap"),
        (lambda doc: doc["layers"][3]["shapes"][0]["style"].update(join=3), "style.join"),
        (lambda doc: doc["layers"][3]["shapes"][0]["style"].update(miter_limit=0.5), "style.miter_limit"),
        (lambda doc: doc["layers"][3]["shapes"][0]["style"].update(dashes=[1, -2]), "style.dashes[1]"),
        (lambda doc: doc["layers"][3]["shapes"][0]["style"].update(dashes="4 2"), "style.dashes"),
        (lambda doc: doc["layers"][3]["shapes"][0].update(rx=-1), "shapes[0].rx"),
        (lambda doc: doc["layers"][3]["shapes"][1].update(anchor="left"), "shapes[1].anchor"),
        (lambda doc: doc["layers"][3]["shapes"][0].update(hidden="yes"), "shapes[0].hidden"),
        (lambda doc: doc["layers"][3]["shapes"][2]["parts"][0].update(locked=1), "parts[0].locked"),
        (lambda doc: doc["layers"][3].update(locked="no"), "document.layers[3].locked"),
    ],
)
def test_damaged_documents_name_the_broken_place(change, where):
    message = _broken(change)
    assert message.startswith("damaged file:")
    assert where in message


# --- archive and working state --------------------------------------------------------------------

STATE = SavedState(
    zoom_percent=250,
    view_center=(300.5, -12.25),
    tool_styles={Tool.PEN: Style(fill=None), Tool.TEXT: RED},
    font_size=31.5,
    new_part_mode="intersect",
    selection=frozenset({21, 22}),
    selected_layer=2,
    edit_path=(10, 20),
)


def _archive(document=None, state=STATE, preview=b"\x89PNG fake") -> bytes:
    return write_p2s(document or _sample_document(), state, preview, "0.1.0 (test)")


def _payload(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return json.loads(archive.read("document.json"))


def _repack(data: bytes, change=None, names=None, first=None) -> bytes:
    """Rewrites an archive: `change` edits the payload, `names` replaces whole entries."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = {name: archive.read(name) for name in archive.namelist()}
    if change is not None:
        payload = json.loads(entries["document.json"])
        change(payload)
        entries["document.json"] = json.dumps(payload).encode()
    entries.update(names or {})
    order = [first] if first else []
    order += [name for name in entries if name not in order]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in order:
            if entries[name] is not None:
                archive.writestr(name, entries[name])
    return buffer.getvalue()


def test_archive_round_trips_document_and_state():
    document, state = read_p2s(_archive())
    assert document == _sample_document()
    assert state == STATE


def test_archive_layout_mimetype_first_and_uncompressed():
    data = _archive()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        assert [info.filename for info in infos] == ["mimetype", "document.json", "preview.png"]
        assert infos[0].compress_type == zipfile.ZIP_STORED
        assert infos[1].compress_type == zipfile.ZIP_DEFLATED
    assert data[30:38] == b"mimetype" and data[38:64] == b"application/x-presstoshape"
    payload = _payload(data)
    expected = ("presstoshape", CURRENT_VERSION, "0.1.0 (test)")
    assert (payload["format"], payload["format_version"], payload["app_version"]) == expected
    assert read_preview(data) == b"\x89PNG fake"


def test_saving_twice_gives_identical_bytes():
    document, state = read_p2s(_archive())
    assert write_p2s(document, state, b"\x89PNG fake", "0.1.0 (test)") == _archive()


def test_missing_state_and_preview_are_fine():
    data = _repack(_archive(preview=None), change=lambda payload: payload.pop("state"))
    document, state = read_p2s(data)
    assert state == SavedState() and read_preview(data) is None


def test_unknown_entries_and_tools_are_ignored():
    def add_tool(payload):
        payload["state"]["tools"]["styles"]["spray"] = {"fill": None, "stroke": None, "stroke_width": 1.0}

    data = _repack(_archive(), change=add_tool, names={"resources/brush.bin": b"\x00" * 10, "future.txt": b"x"})
    assert read_p2s(data)[1] == STATE


EMPTY = write_p2s(Document(), SavedState(), None, "x")


@pytest.mark.parametrize(
    "data, message",
    [
        (b"not a zip at all", "not a PressToShape file"),
        (_repack(EMPTY, names={"mimetype": b"text/plain"}), "not a PressToShape"),
        (_repack(EMPTY, first="document.json"), "not a PressToShape file"),
        (_repack(EMPTY, names={"document.json": None}), "document.json is missing"),
        (_repack(EMPTY, names={"document.json": b"{oops"}), "isn't valid JSON"),
        (_repack(EMPTY, names={"document.json": b'{"x": NaN}'}), "NaN"),
        (
            _repack(EMPTY, change=lambda p: p.update(format="other")),
            "not a PressToShape file",
        ),
        (
            _repack(EMPTY, change=lambda p: p["state"].update(selection=["a"])),
            "state.selection[0]",
        ),
    ],
)
def test_unreadable_archives_say_why(data, message):
    with pytest.raises(P2sError, match=re.escape(message)):
        read_p2s(data)


def test_newer_format_version_is_refused_with_both_versions():
    data = _repack(_archive(), change=lambda payload: payload.update(format_version=CURRENT_VERSION + 2))
    with pytest.raises(P2sError) as error:
        read_p2s(data)
    assert f"file format {CURRENT_VERSION + 2}" in str(error.value)
    assert f"reads up to {CURRENT_VERSION}" in str(error.value)
    assert "newer PressToShape" in str(error.value)


def test_oversized_entry_is_refused_before_reading_it_all(monkeypatch):
    monkeypatch.setattr(p2s, "_MAX_DOCUMENT_BYTES", 1000)
    padded = _repack(_archive(), change=lambda payload: payload.update(padding=" " * 5000))
    with pytest.raises(P2sError, match="too large"):
        read_p2s(padded)


def test_entry_lying_about_its_size_fails_cleanly():
    # zipfile reads only the declared size and then fails the checksum, so a lie can't inflate memory use.
    data = bytearray(_archive())
    header = data.index(b"PK\x01\x02", 0)
    while data.find(b"document.json", header) != header + 46:
        header = data.index(b"PK\x01\x02", header + 1)
    data[header + 24 : header + 28] = (10).to_bytes(4, "little")
    with pytest.raises(P2sError, match="damaged file"):
        read_p2s(bytes(data))


def test_everything_the_app_can_save_opens_again_including_id_zero():
    document = Document(layers=[Layer("L", True, [RectShape(0, 0, 0, 1, 1, Style())])], next_id=1)
    state = SavedState(selection=frozenset({0}))
    assert read_p2s(write_p2s(document, state, None, "x")) == (document, state)


def test_unit_and_dpi_round_trip_and_bad_values_are_refused():
    document = Document(width=2480.0, height=3508.0, unit="mm", dpi=300.0)
    assert _round_trip(document) == document
    for field, value in (("unit", "km"), ("unit", None), ("dpi", 0), ("dpi", 1e9)):
        encoded = encode_document(document)
        encoded[field] = value
        with pytest.raises(P2sError, match=field):
            decode_document(encoded)


def test_default_styles_stay_compact():
    encoded = p2s.encode_style(Style(fill="#ff0000", stroke=None, stroke_width=1.0))
    assert encoded == {"fill": "#ff0000", "stroke": None, "stroke_width": 1.0}
    rect_fields = set(p2s.encode_shape(RectShape(1, 0, 0, 1, 1, Style())))
    assert rect_fields == {"type", "id", "x", "y", "width", "height", "style"}


def test_odd_dash_lists_are_normalized_on_read():
    encoded = p2s.encode_style(Style())
    encoded["dashes"] = [3.0]
    assert p2s.decode_style(encoded, "style").dashes == (3.0, 3.0)


def test_tool_styles_keep_the_new_fields():
    state = SavedState(tool_styles={Tool.RECTANGLE: FULL})
    assert read_p2s(write_p2s(Document(), state, None, "x"))[1].tool_styles == {Tool.RECTANGLE: FULL}


GROUPED = Document(
    width=100.0,
    height=100.0,
    layers=[
        Layer(
            "L",
            True,
            [
                GroupShape(
                    1,
                    (
                        RectShape(2, 0, 0, 10, 10, RED),
                        GroupShape(3, (TextShape(4, 0, 20, "a", 12, FULL),), opacity=0.25),
                        CompositeShape(5, (RectShape(6, 0, 0, 5, 5, RED),), ("add",), RED),
                    ),
                    opacity=0.5,
                )
            ],
        )
    ],
    next_id=7,
)


def test_groups_round_trip_without_style_or_transform():
    encoded = encode_document(GROUPED)
    group = encoded["layers"][0]["shapes"][0]
    assert set(group) == {"type", "id", "children", "opacity"}
    assert "opacity" not in p2s.encode_shape(GroupShape(9, (RectShape(10, 0, 0, 1, 1, RED),)))
    assert _round_trip(GROUPED) == GROUPED


@pytest.mark.parametrize(
    "change, where",
    [
        (lambda group: group.update(children=[]), "shapes[0].children"),
        (lambda group: group.pop("children"), "shapes[0]"),
        (lambda group: group.update(opacity=2), "shapes[0].opacity"),
        (lambda group: group["children"][0].update(id=1), "id twice"),
    ],
)
def test_damaged_groups_name_the_broken_place(change, where):
    encoded = copy.deepcopy(encode_document(GROUPED))
    change(encoded["layers"][0]["shapes"][0])
    with pytest.raises(P2sError) as error:
        decode_document(encoded)
    assert where in str(error.value)


def test_guides_grid_and_their_view_state_round_trip():
    document = Document(
        guides=(Guide(5, "horizontal", 12.5), Guide(6, "vertical", -3.0)), grid=GridSettings(7.5, 3), next_id=7
    )
    assert _round_trip(document) == document
    state = SavedState(show_grid=True, show_guides=False, lock_guides=True)
    assert read_p2s(write_p2s(document, state, None, "x")) == (document, state)
    assert "guides" not in encode_document(Document()) and "grid" not in encode_document(Document())


@pytest.mark.parametrize(
    "change, where",
    [
        (lambda doc: doc["guides"][0].update(orientation="diagonal"), "guides[0].orientation"),
        (lambda doc: doc["guides"][0].update(position="left"), "guides[0].position"),
        (lambda doc: doc["guides"][0].update(id=5), "id twice"),
        (lambda doc: doc["grid"].update(spacing=0), "grid.spacing"),
        (lambda doc: doc["grid"].update(major_every=0), "grid.major_every"),
    ],
)
def test_damaged_guides_and_grids_name_the_broken_place(change, where):
    document = Document(
        layers=[Layer("L", True, [RectShape(5, 0, 0, 1, 1, RED)])],
        guides=(Guide(6, "horizontal", 1.0),),
        grid=GridSettings(5.0, 2),
        next_id=7,
    )
    encoded = copy.deepcopy(encode_document(document))
    change(encoded)
    with pytest.raises(P2sError) as error:
        decode_document(encoded)
    assert where in str(error.value)


def test_saved_view_state_is_applied_on_open(tmp_path):
    from presstoshape.editing.operations import documents
    from presstoshape.editing.session import Session

    target = tmp_path / "view.p2s"
    target.write_bytes(write_p2s(Document(), SavedState(show_grid=True, lock_guides=True), None, "x"))
    session = Session()
    documents.open_file(session, str(target))
    assert session.state.view.show_grid and session.state.view.lock_guides and session.state.view.show_guides


def _flagged_document() -> Document:
    composite = CompositeShape(
        5, (RectShape(6, 0, 0, 9, 9, RED, hidden=True), RectShape(7, 0, 0, 5, 5, RED)), ("add", "subtract"), RED
    )
    group = GroupShape(2, (RectShape(3, 0, 0, 5, 5, RED, hidden=True), RectShape(4, 0, 0, 5, 5, RED)), locked=True)
    return Document(
        width=100.0,
        height=100.0,
        layers=[
            Layer("Sketch", True, [RectShape(1, 0, 0, 5, 5, RED, hidden=True, locked=True), group], locked=True),
            Layer("Top", True, [composite, EllipseShape(8, 5, 5, 2, 2, RED)]),
        ],
        next_id=9,
    )


def test_hidden_and_locked_flags_round_trip_everywhere():
    original = _flagged_document()
    assert _round_trip(original) == original


def test_flags_are_written_only_when_set():
    encoded = encode_document(_flagged_document())
    sketch, top = encoded["layers"]
    assert sketch["locked"] is True and "locked" not in top
    assert (sketch["shapes"][0]["hidden"], sketch["shapes"][0]["locked"]) == (True, True)
    assert "hidden" not in sketch["shapes"][1] and sketch["shapes"][1]["locked"] is True
    assert "hidden" not in top["shapes"][1] and "locked" not in top["shapes"][1]
    assert top["shapes"][0]["parts"][0]["hidden"] is True
    assert json.dumps(encode_document(_round_trip(_flagged_document()))) == json.dumps(encoded)


def test_document_read_from_nested_viewports_round_trips():
    document = read_svg(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<svg x="5" y="5" width="20" height="20" viewBox="0 0 10 10"><rect width="10" height="10"/></svg></svg>'
    )
    assert _round_trip(document) == document


_STOPS = (GradientStop(0.0, "#ff0000"), GradientStop(0.4, "#00ff00", 0.25), GradientStop(1.0, "#0000ff"))
_LINEAR = LinearGradient(0.0, 0.0, 1.0, 1.0, _STOPS)
_RADIAL = RadialGradient(0.5, 0.5, 0.5, 0.25, 0.5, _STOPS, "userSpaceOnUse", "repeat", ROTATED)


@pytest.mark.parametrize(
    "paint", [_LINEAR, _RADIAL, LinearGradient(1.0, 2.0, 3.0, 4.0, _STOPS, "userSpaceOnUse", "reflect")]
)
def test_gradient_paints_round_trip(paint):
    style = Style(fill=paint, stroke=paint, stroke_width=3.0)
    assert p2s.decode_style(p2s.encode_style(style), "style") == style


def test_gradient_defaults_are_left_out():
    encoded = p2s.encode_paint(_LINEAR)
    assert set(encoded) == {"type", "x1", "y1", "x2", "y2", "stops"}
    assert "opacity" not in encoded["stops"][0] and encoded["stops"][1]["opacity"] == 0.25


def test_flat_paints_encode_as_before():
    assert p2s.encode_paint("#abcdef") == "#abcdef"
    assert p2s.encode_paint(None) is None


def test_gradient_shapes_survive_an_archive():
    document = Document(
        layers=[Layer("L", True, [RectShape(1, 0, 0, 10, 10, Style(fill=_RADIAL, stroke=_LINEAR))])], next_id=2
    )
    assert read_p2s(write_p2s(document, SavedState(), None, "x"))[0] == document


def test_tool_styles_carry_gradients():
    state = SavedState(tool_styles={Tool.RECTANGLE: Style(fill=_LINEAR)})
    assert read_p2s(write_p2s(Document(), state, None, "x"))[1].tool_styles == state.tool_styles


def _gradient_fields():
    return p2s.encode_paint(_RADIAL)


@pytest.mark.parametrize(
    "change, field",
    [
        (lambda f: f.update(type="conic"), "type"),
        (lambda f: f.update(units="em"), "units"),
        (lambda f: f.update(spread="wrap"), "spread"),
        (lambda f: f.update(stops="red"), "stops"),
        (lambda f: f.update(r="big"), "r"),
        (lambda f: f.update(transform=[1, 2]), "transform"),
        (lambda f: f.pop("stops"), "stops"),
        (lambda f: f.update(stops=[{"offset": 0}]), "color"),
        (lambda f: f.update(stops=[{"offset": 0, "color": 5}]), "color"),
    ],
)
def test_damaged_gradients_are_refused(change, field):
    fields = _gradient_fields()
    change(fields)
    with pytest.raises(P2sError, match=field):
        p2s.decode_paint(fields, "style.fill")


def test_out_of_range_gradient_values_are_brought_into_range_on_read():
    fields = _gradient_fields()
    fields["stops"] = [{"offset": 3, "color": "#fff", "opacity": 7}, {"offset": 0.1, "color": "#000"}]
    fields.update(fx=9.0, fy=0.5)
    style = p2s.decode_style({"fill": fields, "stroke": None, "stroke_width": 1.0}, "style")
    assert [(stop.offset, stop.opacity) for stop in style.fill.stops] == [(1.0, 1.0), (1.0, 1.0)]
    assert (style.fill.fx, style.fill.fy) == (1.0, 0.5)


def test_gradient_without_stops_reads_as_no_paint():
    fields = _gradient_fields()
    fields["stops"] = []
    assert p2s.decode_style({"fill": fields, "stroke": None, "stroke_width": 1.0}, "s").fill is None


def test_huge_stop_lists_are_cut_before_decoding():
    fields = _gradient_fields()
    fields["stops"] = [{"offset": 0.5, "color": "#000"}] * 100_000
    style = p2s.decode_style({"fill": fields, "stroke": None, "stroke_width": 1.0}, "s")
    assert len(style.fill.stops) == 1024
