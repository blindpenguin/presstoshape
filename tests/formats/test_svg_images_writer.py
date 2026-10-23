import base64
import xml.etree.ElementTree as ET

from presstoshape.editing.operations import documents
from presstoshape.editing.session import Session
from presstoshape.formats.svg import count_references, write_shapes_svg, write_svg
from presstoshape.formats.svg_names import INSENSITIVE, XLINK_HREF, q
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import Aspect, GroupShape, ImageData, ImageShape, Masking, RectShape, Style
from tests.helpers import TINY_PNG, tiny_image

PICTURE = tiny_image()


def image(shape_id=1, **fields):
    return ImageShape(shape_id, 10.0, 20.0, 40.0, 30.0, fields.pop("data", PICTURE), **fields)


def document(*shapes):
    return Document(200, 100, [Layer("L", True, list(shapes))])


def images_in(text):
    return list(ET.fromstring(text).iter(q("image")))


def test_image_is_written_with_a_data_uri_of_the_original_bytes():
    (element,) = images_in(write_svg(document(image())))
    assert dict(element.attrib) == {
        "x": "10",
        "y": "20",
        "width": "40",
        "height": "30",
        XLINK_HREF: "data:image/png;base64," + base64.b64encode(TINY_PNG).decode(),
    }


def test_defaults_are_left_out_and_changes_are_written():
    (element,) = images_in(write_svg(document(image(aspect=Aspect("xMinYMax", True), opacity=0.5))))
    assert element.get("preserveAspectRatio") == "xMinYMax slice"
    assert element.get("opacity") == "0.5"
    (plain,) = images_in(write_svg(document(image(aspect=Aspect("none")))))
    assert plain.get("preserveAspectRatio") == "none"
    (default,) = images_in(write_svg(document(image())))
    assert "preserveAspectRatio" not in default.attrib and "opacity" not in default.attrib


def test_href_uses_the_xlink_prefix_and_only_that():
    text = write_svg(document(image()))
    assert 'xmlns:xlink="http://www.w3.org/1999/xlink"' in text
    assert "xlink:href=" in text and " href=" not in text


def test_transform_hidden_and_locked_are_written():
    (element,) = images_in(
        write_svg(document(image(transform=(0.0, 1.0, -1.0, 0.0, 5.0, 6.0), hidden=True, locked=True)))
    )
    assert element.get("transform").startswith("rotate(")
    assert element.get("style") == "display:none"
    assert element.get(INSENSITIVE) == "true"


def test_a_picture_used_by_many_shapes_is_written_for_each_but_valid_xml():
    assert len(images_in(write_svg(document(image(1), image(2), GroupShape(4, (image(3),)))))) == 3


def test_reference_images_are_skipped_and_counted():
    shapes = [image(1), image(2, reference=True), GroupShape(4, (image(3, reference=True), image(5)))]
    assert count_references(shapes) == 2
    text = write_svg(document(*shapes))
    assert len(images_in(text)) == 2


def test_a_group_of_only_references_disappears():
    text = write_svg(document(GroupShape(3, (image(1, reference=True),)), RectShape(2, 0, 0, 5, 5, Style())))
    assert not images_in(text) and "<g>" not in text.replace('<g id="layer1"', "")


def test_masked_group_keeps_its_masking_when_a_reference_inside_goes():
    clip = RectShape(4, 0, 0, 20, 20, Style())
    group = GroupShape(5, (image(1), image(2, reference=True), clip), masking=Masking("clip", (4,)))
    root = ET.fromstring(write_svg(document(group)))
    assert len(list(root.iter(q("image")))) == 1
    assert len(list(root.iter(q("clipPath")))) == 1


def test_a_picture_without_bytes_is_not_written():
    missing = ImageData(b"", 4, 4, "application/x-missing", "0" * 64)
    assert not images_in(write_svg(document(image(data=missing))))


def test_clipboard_svg_skips_references_too():
    text = write_shapes_svg([image(1), image(2, reference=True)], (0.0, 0.0, 100.0, 100.0))
    assert len(images_in(text)) == 1


def test_an_image_as_clip_object_becomes_its_outline():
    group = GroupShape(5, (RectShape(1, 0, 0, 100, 100, Style()), image(2)), masking=Masking("clip", (2,)))
    root = ET.fromstring(write_svg(document(group)))
    (clip,) = root.iter(q("clipPath"))
    assert [child.tag for child in clip] == [q("path")]


def test_files_without_images_keep_their_exact_output():
    text = write_svg(document(RectShape(1, 0, 0, 5, 5, Style())))
    assert "image" not in text and "xlink" not in text


def test_saving_svg_reports_references_that_were_left_out():
    session = Session()
    session.state.document = document(image(1, reference=True), image(2, reference=True))
    session.state.file_path = None
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as folder:
        assert documents.save_file(session, str(Path(folder) / "out.svg"))
    assert "2 reference images were not saved to SVG" in session.state.status_message
    assert "(" in session.state.status_message
