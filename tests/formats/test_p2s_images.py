import io
import json
import zipfile

import pytest

from presstoshape.formats import p2s
from presstoshape.formats.p2s import MISSING_MIME, P2sError, SavedState, media_of, read_p2s_with_notes, write_p2s
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import Aspect, GroupShape, ImageShape, Masking, RectShape, Style
from tests.helpers import TINY_PNG, tiny_image

PICTURE = tiny_image()


def document_with(*shapes):
    return Document(200, 100, [Layer("L", True, list(shapes))], next_id=100)


def image(shape_id=1, **fields):
    return ImageShape(shape_id, 0.0, 0.0, 20.0, 10.0, fields.pop("data", PICTURE), **fields)


def archive(document, state=SavedState()):
    return write_p2s(document, state, None, "test")


def entries(data):
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {info.filename: (zf.read(info.filename), info.compress_type) for info in zf.infolist()}


def repacked(data, **changes):
    found = {name: content for name, (content, _method) in entries(data).items()}
    for name, content in changes.items():
        found[name.replace("__", "/")] = content
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, content in found.items():
            if content is not None:
                zf.writestr(name, content)
    return buffer.getvalue()


def rename_media(data, new_name):
    found = entries(data)
    old = next(name for name in found if name.startswith("media/"))
    return repacked(data, **{old.replace("/", "__"): None, new_name.replace("/", "__"): found[old][0]})


def test_round_trip_keeps_every_field():
    shapes = [
        image(1),
        image(2, aspect=Aspect("xMaxYMin", True), opacity=0.25, reference=True, locked=True),
        image(3, aspect=Aspect("none"), transform=(0.0, 1.0, -1.0, 0.0, 5.0, 6.0), hidden=True),
    ]
    document = document_with(*shapes)
    restored, _state, notes = read_p2s_with_notes(archive(document))
    assert restored == document
    assert notes == []
    assert restored.layers[0].shapes[1].data.data == TINY_PNG


def test_one_blob_is_stored_once_and_shared_after_reading():
    document = document_with(image(1), image(2), GroupShape(4, (image(3),)))
    data = archive(document)
    assert [name for name in entries(data) if name.startswith("media/")] == [f"media/{PICTURE.digest}.png"]
    restored, _state, _notes = read_p2s_with_notes(data)
    first, second, group = restored.layers[0].shapes
    assert first.data is second.data is group.children[0].data


def test_media_entries_are_stored_after_the_document_and_named_by_digest():
    found = entries(archive(document_with(image())))
    assert list(found)[:2] == ["mimetype", "document.json"]
    content, method = found[f"media/{PICTURE.digest}.png"]
    assert content == TINY_PNG and method == zipfile.ZIP_STORED


def test_unreferenced_pictures_are_never_written():
    assert not [name for name in entries(archive(document_with())) if name.startswith("media/")]


def test_pictures_nested_in_groups_and_masks_are_found_and_round_trip():
    clip = RectShape(7, 0, 0, 5, 5, Style())
    masked = GroupShape(5, (image(6), clip), masking=Masking("clip", (7,)))
    document = document_with(GroupShape(8, (masked,)))
    assert list(media_of(document.layers[0].shapes)) == [PICTURE.digest]
    assert read_p2s_with_notes(archive(document))[0] == document


def test_file_without_pictures_has_no_media_and_the_same_bytes_as_before():
    document = document_with(RectShape(1, 0, 0, 5, 5, Style()))
    data = archive(document)
    assert [name for name in entries(data) if name != "mimetype"] == ["document.json"]
    assert write_p2s(*(read_p2s_with_notes(data)[:2]), None, "test") == data


def test_missing_media_gives_a_placeholder_and_a_note():
    data = repacked(archive(document_with(image(1), image(2))), **{f"media__{PICTURE.digest}.png": None})
    document, _state, notes = read_p2s_with_notes(data)
    shapes = document.layers[0].shapes
    assert all(shape.data.mime == MISSING_MIME and shape.data.data == b"" for shape in shapes)
    assert (shapes[0].data.width, shapes[0].data.height) == (20, 10)
    assert len(notes) == 1


def test_a_placeholder_survives_saving_and_opening_again():
    data = repacked(archive(document_with(image())), **{f"media__{PICTURE.digest}.png": None})
    document, state, _notes = read_p2s_with_notes(data)
    again = read_p2s_with_notes(write_p2s(document, state, None, "test"))
    assert again[0].layers[0].shapes[0].data.digest == PICTURE.digest
    assert again[2]


def test_corrupt_media_is_a_placeholder():
    data = repacked(archive(document_with(image())), **{f"media__{PICTURE.digest}.png": b"not a picture"})
    document, _state, notes = read_p2s_with_notes(data)
    assert document.layers[0].shapes[0].data.mime == MISSING_MIME
    assert notes


def test_media_that_does_not_match_its_digest_is_refused():
    other = TINY_PNG[:-12] + b"\x00" * 12
    data = repacked(archive(document_with(image())), **{f"media__{PICTURE.digest}.png": other})
    document, _state, notes = read_p2s_with_notes(data)
    assert document.layers[0].shapes[0].data.mime == MISSING_MIME
    assert notes


def test_oversize_media_is_a_placeholder_without_being_read(monkeypatch):
    monkeypatch.setattr(p2s, "_MAX_MEDIA_BYTES", 10)
    document, _state, notes = read_p2s_with_notes(archive(document_with(image())))
    assert document.layers[0].shapes[0].data.mime == MISSING_MIME
    assert notes


def test_entry_names_are_never_used_as_paths():
    hostile = f"media/../../{PICTURE.digest}.png"
    data = rename_media(archive(document_with(image())), hostile)
    document, _state, notes = read_p2s_with_notes(data)
    assert document.layers[0].shapes[0].data.mime == MISSING_MIME and notes
    odd = rename_media(archive(document_with(image())), f"media/{PICTURE.digest}.png.exe")
    assert read_p2s_with_notes(odd)[0].layers[0].shapes[0].data.mime == MISSING_MIME


def test_unreferenced_media_in_the_archive_is_ignored():
    data = repacked(archive(document_with()), **{f"media__{'a' * 64}.png": b"x" * 1000})
    assert read_p2s_with_notes(data)[0] == document_with()


def test_too_many_entries_are_refused(monkeypatch):
    monkeypatch.setattr(p2s, "_MAX_ENTRIES", 3)
    data = repacked(archive(document_with()), **{f"media__{index:064x}.png": b"x" for index in range(5)})
    with pytest.raises(P2sError):
        read_p2s_with_notes(data)


def test_total_media_over_the_limit_is_refused(monkeypatch):
    monkeypatch.setattr(p2s, "_MAX_MEDIA_TOTAL", 100)
    with pytest.raises(P2sError):
        read_p2s_with_notes(repacked(archive(document_with()), **{f"media__{'c' * 64}.png": b"z" * 200}))


@pytest.mark.parametrize("media", ["", "short", "G" * 64, "../" + "a" * 61, 5, None])
def test_a_malformed_media_reference_is_damage(media):
    payload = json.loads(entries(archive(document_with(image())))["document.json"][0])
    payload["document"]["layers"][0]["shapes"][0]["media"] = media
    data = repacked(archive(document_with(image())), **{"document.json": json.dumps(payload).encode()})
    with pytest.raises(P2sError):
        read_p2s_with_notes(data)


def test_an_unknown_alignment_is_damage():
    payload = json.loads(entries(archive(document_with(image())))["document.json"][0])
    payload["document"]["layers"][0]["shapes"][0]["aspect"] = "middle"
    data = repacked(archive(document_with(image())), **{"document.json": json.dumps(payload).encode()})
    with pytest.raises(P2sError):
        read_p2s_with_notes(data)


def test_current_version_is_eleven():
    assert json.loads(entries(archive(document_with()))["document.json"][0])["format_version"] == 11
