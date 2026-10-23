import xml.etree.ElementTree as ET

from presstoshape.formats.svg import write_shapes_svg, write_svg
from presstoshape.geometry.segments import rect_segments
from presstoshape.models.app_state import Document, Layer
from presstoshape.models.shapes import (
    EllipseShape,
    GradientStop,
    GroupShape,
    LinearGradient,
    Masking,
    PathShape,
    RectShape,
    Style,
    TextShape,
)

NS = "{http://www.w3.org/2000/svg}"
RED = Style(fill="#ff0000", stroke=None)


def _doc(*shapes) -> Document:
    return Document(200, 100, [Layer("L", True, list(shapes))])


def _root(doc: Document) -> ET.Element:
    return ET.fromstring(write_svg(doc).split("\n", 1)[1])


def _group(mask, mask_type="clip", content=None, **fields) -> GroupShape:
    content = content or [RectShape(1, 0, 0, 100, 100, RED)]
    return GroupShape(50, (*content, *mask), masking=Masking(mask_type, tuple(s.id for s in mask), **fields))


def _defs(root):
    return root.find(f"{NS}defs")


def test_clip_group_is_a_g_with_clip_path_and_a_clippath_in_defs():
    root = _root(_doc(_group([EllipseShape(2, 50, 50, 30, 30, RED)])))
    group = root.find(f"{NS}g/{NS}g")
    assert group.get("clip-path") == "url(#clip1)"
    assert [child.tag for child in group] == [f"{NS}rect"]
    clip = _defs(root).find(f"{NS}clipPath")
    assert clip.get("id") == "clip1"
    assert [child.tag for child in clip] == [f"{NS}ellipse"]


def test_clip_children_carry_geometry_only():
    mask = RectShape(2, 0, 0, 10, 10, Style(fill="#00ff00", stroke="#000000", stroke_width=5, opacity=0.5))
    child = _defs(_root(_doc(_group([mask]))))[0][0]
    assert set(child.attrib) == {"x", "y", "width", "height"}


def test_clip_rule_follows_the_fill_rule():
    path = PathShape(2, rect_segments(0, 0, 50, 50) + rect_segments(10, 10, 20, 20), Style(fill_rule="evenodd"))
    child = _defs(_root(_doc(_group([path]))))[0][0]
    assert child.get("clip-rule") == "evenodd" and "fill-rule" not in child.attrib
    plain = _defs(_root(_doc(_group([PathShape(2, path.segments, Style())]))))[0][0]
    assert "clip-rule" not in plain.attrib


def test_hidden_mask_object_is_left_out_of_the_clip():
    mask = [RectShape(2, 0, 0, 10, 10, RED, hidden=True), RectShape(3, 0, 0, 5, 5, RED)]
    assert len(_defs(_root(_doc(_group(mask))))[0]) == 1


def test_plain_group_in_a_clip_is_flattened():
    inner = GroupShape(7, (RectShape(2, 0, 0, 10, 10, RED), EllipseShape(3, 5, 5, 2, 2, RED)))
    clip = _defs(_root(_doc(_group([inner]))))[0]
    assert [child.tag for child in clip] == [f"{NS}rect", f"{NS}ellipse"]


def test_masked_group_in_a_clip_becomes_its_visible_area():
    inner = GroupShape(
        7,
        (RectShape(2, 0, 0, 100, 100, RED), RectShape(3, 0, 0, 50, 50, RED)),
        masking=Masking("clip", (3,)),
    )
    clip = _defs(_root(_doc(_group([inner]))))[0]
    assert [child.tag for child in clip] == [f"{NS}path"]


def test_inverted_clip_is_a_path_with_a_hole():
    clip = _defs(_root(_doc(_group([RectShape(2, 20, 20, 40, 40, RED)], inverted=True))))[0]
    assert [child.tag for child in clip] == [f"{NS}path"]
    assert clip[0].get("d").count("M") == 2


def test_luminance_mask_is_written_with_artwork_and_a_region():
    ramp = LinearGradient(0, 0, 1, 0, (GradientStop(0, "#000000"), GradientStop(1, "#ffffff")))
    mask = RectShape(2, 0, 0, 100, 100, Style(fill=ramp, stroke=None))
    root = _root(_doc(_group([mask], "luminance")))
    group = root.find(f"{NS}g/{NS}g")
    assert group.get("mask") == "url(#mask1)" and "clip-path" not in group.attrib
    mask_element = _defs(root).find(f"{NS}mask")
    assert mask_element.get("maskUnits") == "userSpaceOnUse"
    assert mask_element[0].get("fill") == "url(#grad1)"
    assert _defs(root).find(f"{NS}linearGradient").get("id") == "grad1"
    x, y, width, height = (float(mask_element.get(key)) for key in ("x", "y", "width", "height"))
    assert x < 0 and y < 0 and x + width > 100 and y + height > 100


def test_stored_region_is_the_mask_region():
    mask = _defs(_root(_doc(_group([RectShape(2, 0, 0, 9, 9, RED)], "luminance", region=(1.0, 2.0, 3.0, 4.0)))))[0]
    assert [mask.get(key) for key in ("x", "y", "width", "height")] == ["1", "2", "3", "4"]


def test_text_in_a_mask_falls_back_to_the_page_region():
    text = TextShape(2, 10, 50, "Hi", 20, Style(fill="#ffffff", stroke=None))
    mask = _defs(_root(_doc(_group([text], "luminance"))))[0]
    assert float(mask.get("x")) < 0 and float(mask.get("width")) >= 200


def test_alpha_mask_type_attribute():
    mask = _defs(_root(_doc(_group([RectShape(2, 0, 0, 9, 9, RED)], "alpha"))))[0]
    assert mask.get("mask-type") == "alpha"
    other = _defs(_root(_doc(_group([RectShape(2, 0, 0, 9, 9, RED)], "luminance"))))[0]
    assert "mask-type" not in other.attrib


def test_group_opacity_and_mask_share_one_g():
    group = _group([RectShape(2, 0, 0, 9, 9, RED)])
    from dataclasses import replace

    element = _root(_doc(replace(group, opacity=0.5))).find(f"{NS}g/{NS}g")
    assert element.get("opacity") == "0.5" and element.get("clip-path")


def test_ids_are_stable_between_saves_and_unique():
    doc = _doc(
        _group([RectShape(2, 0, 0, 9, 9, RED)]),
        GroupShape(
            60, (RectShape(3, 0, 0, 5, 5, RED), RectShape(4, 0, 0, 2, 2, RED)), masking=Masking("luminance", (4,))
        ),
    )
    assert write_svg(doc) == write_svg(doc)
    ids = [element.get("id") for element in _defs(_root(doc))]
    assert ids == ["clip1", "mask1"]


def test_nested_masked_group_in_content_writes_both():
    inner = GroupShape(7, (RectShape(2, 0, 0, 9, 9, RED), RectShape(3, 0, 0, 5, 5, RED)), masking=Masking("clip", (3,)))
    outer = GroupShape(8, (inner, RectShape(4, 0, 0, 20, 20, RED)), masking=Masking("clip", (4,)))
    root = _root(_doc(outer))
    assert len(_defs(root).findall(f"{NS}clipPath")) == 2
    assert root.find(f"{NS}g/{NS}g/{NS}g").get("clip-path") == "url(#clip2)"


def test_files_without_masks_have_no_extra_defs():
    assert "<defs" not in write_svg(_doc(RectShape(1, 0, 0, 10, 10, Style())))


def test_clipboard_svg_carries_masks():
    text = write_shapes_svg([_group([RectShape(2, 0, 0, 9, 9, RED)])], (0.0, 0.0, 10.0, 10.0))
    assert "<clipPath" in text and 'clip-path="url(#clip1)"' in text
