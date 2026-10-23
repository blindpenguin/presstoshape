import math
from dataclasses import replace

from presstoshape.editing.containers import with_children
from presstoshape.models.shapes import (
    GroupShape,
    Masking,
    RectShape,
    Style,
    children_of,
    content_children,
    mask_children,
    sanitized_masking,
)


def rect(shape_id: int) -> RectShape:
    return RectShape(shape_id, 0, 0, 10, 10, Style())


def masked(mask_ids=(3,), mask_type="clip", **fields) -> GroupShape:
    children = (rect(1), rect(2), rect(3))
    return GroupShape(9, children, masking=Masking(mask_type, tuple(mask_ids), **fields))


def test_group_without_masking_is_all_content():
    group = GroupShape(9, (rect(1), rect(2)))
    assert group.masking is None
    assert mask_children(group) == ()
    assert content_children(group) == group.children


def test_helpers_split_children_in_order():
    group = masked(mask_ids=(3, 1))
    assert [c.id for c in mask_children(group)] == [1, 3]
    assert [c.id for c in content_children(group)] == [2]
    assert group.masking.is_mask(3) and not group.masking.is_mask(2)


def test_equality_and_hash():
    assert masked() == masked()
    assert hash(masked()) == hash(masked())
    assert masked() != masked(inverted=True)
    assert masked() != masked(mask_type="alpha")
    assert masked(region=(0, 0, 5, 5)) != masked()


def test_masking_does_not_change_children_of():
    assert [c.id for c in children_of(masked())] == [1, 2, 3]


def test_sanitized_prunes_unknown_and_duplicate_ids():
    clean = sanitized_masking(Masking("clip", (3, 7, 3, 1)), [1, 2, 3])
    assert clean.mask_ids == (3, 1)


def test_sanitized_resets_unknown_type():
    assert sanitized_masking(Masking("sepia", (1,)), [1]).type == "clip"


def test_sanitized_keeps_valid_masking_equal():
    masking = Masking("luminance", (1,), True, (0.0, 1.0, 2.0, 3.0))
    assert sanitized_masking(masking, [1, 2]) == masking


def test_sanitized_region():
    base = Masking("luminance", (1,))
    assert sanitized_masking(replace(base, region=(0, 0, math.nan, 1)), [1]).region is None
    assert sanitized_masking(replace(base, region=(0, 0, -1, 1)), [1]).region is None
    assert sanitized_masking(replace(base, region=(0, 0, math.inf, 1)), [1]).region is None
    assert sanitized_masking(replace(base, region=(0, 0, 1)), [1]).region is None
    assert sanitized_masking(replace(base, region=(0, 0, 0, 0)), [1]).region == (0.0, 0.0, 0.0, 0.0)


def test_empty_mask_ids_stay_a_masking():
    clean = sanitized_masking(Masking("luminance", ()), [1])
    assert clean == Masking("luminance", ())


def test_with_children_prunes_mask_ids():
    group = masked(mask_ids=(2, 3))
    rebuilt = with_children(group, [rect(1), rect(3)], "add")
    assert rebuilt.masking.mask_ids == (3,)
    assert rebuilt.masking.type == "clip"


def test_with_children_keeps_masking_when_only_content_goes():
    rebuilt = with_children(masked(), [rect(3)], "add")
    assert rebuilt.masking == Masking("clip", (3,))
    assert content_children(rebuilt) == ()


def test_with_children_on_plain_group_stays_plain():
    group = GroupShape(9, (rect(1),))
    assert with_children(group, [rect(1), rect(2)], "add").masking is None


def test_nested_masked_groups():
    inner = masked()
    outer = GroupShape(20, (inner, rect(30)), masking=Masking("luminance", (30,)))
    assert mask_children(outer) == (rect(30),)
    assert content_children(outer) == (inner,)
    assert inner.masking.type == "clip"
