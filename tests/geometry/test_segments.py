from veccy.geometry.boxes import box_from_drag
from veccy.geometry.segments import smooth_segments
from veccy.models.shapes import MoveTo


def test_box_from_drag_normalizes_any_direction():
    assert box_from_drag((10, 10), (0, 4)) == (0, 4, 10, 6)



def test_box_from_drag_square_keeps_drag_direction():
    assert box_from_drag((10, 10), (0, 4), square=True) == (0, 0, 10, 10)



def test_smooth_segments_passes_through_points():
    pts = [(0, 0), (10, 5), (20, 0)]
    segments = smooth_segments(pts)
    assert segments[0] == MoveTo(0, 0)
    assert [(s.x, s.y) for s in segments[1:]] == pts[1:]
