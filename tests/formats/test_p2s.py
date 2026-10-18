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
from presstoshape.models.app_state import Document, Layer, Tool
from presstoshape.models.shapes import (
    Close,
    CompositeShape,
    CubicTo,
    EllipseShape,
    LineTo,
    MoveTo,
    PathShape,
    RectShape,
    Style,
    TextShape,
)

RED = Style(fill="#ff0000", stroke=None, stroke_width=0.0)
OUTLINE = Style(fill=None, stroke="#18181b", stroke_width=1.25)
ROTATED = (math.cos(0.3), math.sin(0.3), -math.sin(0.3), math.cos(0.3), 12.5, -3.0)
SKEWED = (1.0, 0.0, 0.4, 1.0, 0.0, 0.0)


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
        ],
        next_id=23,
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
    assert decode_document(encoded).next_id == 23


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
    assert (payload["format"], payload["format_version"], payload["app_version"]) == ("presstoshape", 1, "0.1.0 (test)")
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
