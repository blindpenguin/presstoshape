from pathlib import Path

from veccy import icons


def test_every_icon_constant_points_to_a_file():
    paths = [v for v in vars(icons).values() if isinstance(v, Path) and v.suffix == ".svg"]
    assert paths
    missing = [p.name for p in paths if not p.is_file()]
    assert missing == []
