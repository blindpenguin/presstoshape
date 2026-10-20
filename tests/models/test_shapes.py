import math

from presstoshape.models.shapes import Style, sanitized


def test_default_style_is_already_sanitized():
    assert sanitized(Style()) == Style()


def test_opacities_are_clamped():
    style = sanitized(Style(opacity=2, fill_opacity=-1, stroke_opacity=math.nan))
    assert (style.opacity, style.fill_opacity, style.stroke_opacity) == (1, 0, 1)


def test_unknown_enum_values_fall_back_to_defaults():
    style = sanitized(Style(fill_rule="odd", cap="pointy", join="glued"))
    assert (style.fill_rule, style.cap, style.join) == ("nonzero", "butt", "miter")


def test_odd_dash_lists_are_repeated():
    assert sanitized(Style(dashes=(4, 2, 1))).dashes == (4, 2, 1, 4, 2, 1)


def test_invalid_dash_lists_become_solid():
    assert sanitized(Style(dashes=(4, -2))).dashes == ()
    assert sanitized(Style(dashes=(0, 0))).dashes == ()
    assert sanitized(Style(dashes=(math.inf, 1))).dashes == ()


def test_numbers_are_kept_in_range():
    style = sanitized(Style(stroke_width=-3, miter_limit=0.2, dash_offset=math.nan))
    assert (style.stroke_width, style.miter_limit, style.dash_offset) == (0, 1, 0)
