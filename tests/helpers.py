"""Plain helpers shared by test modules (fixtures live in conftest.py)."""

from presstoshape.models.shapes import CubicTo, LineTo, MoveTo


def points(segments):
    for segment in segments:
        match segment:
            case MoveTo(x, y) | LineTo(x, y) | CubicTo(x=x, y=y):
                yield x, y


def bbox(segments):
    pts = list(points(segments))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def all_shapes(session):
    return [shape for layer in session.state.document.layers for shape in layer.shapes]


class ToolDriver:
    """Drives a Toolbox the way CanvasView does, without Qt: switch tools, then talk to the active one."""

    def __init__(self, session, ask_text=lambda: None):
        from presstoshape.render.paths import PathCache
        from presstoshape.tools.base import ToolContext
        from presstoshape.tools.registry import Toolbox

        self.toolbox = Toolbox(ToolContext(session, PathCache(), repaint=lambda: None, ask_text=ask_text))

    def set_tool(self, tool) -> None:
        self.toolbox.switch(tool)

    @property
    def pixel_size(self) -> float:
        return self.toolbox.context.pixel_size

    @pixel_size.setter
    def pixel_size(self, value: float) -> None:
        self.toolbox.context.pixel_size = value

    def __getattr__(self, name):
        return getattr(self.toolbox.active, name)


def setup_tools(text: str | None = "hi"):
    """A fresh session and a ToolDriver whose text prompt answers `text`."""
    from presstoshape.editing.session import Session

    session = Session()
    return session, ToolDriver(session, ask_text=lambda: text)


def drag(driver, start, end, shift=False, ctrl=False, alt=False) -> None:
    from presstoshape.tools.base import Mods

    mods = Mods(shift, ctrl, alt)
    driver.press(start, mods)
    driver.move(end, mods)
    driver.release(end, mods)


def leaves(shapes):
    """`shapes` with every group replaced by the shapes inside it (recursively), in order."""
    from presstoshape.models.shapes import GroupShape

    result = []
    for shape in shapes:
        result.extend(leaves(shape.children) if isinstance(shape, GroupShape) else [shape])
    return result


TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73000000104944415478da63f8cf0004ff19"
    "2014001bf203fd3e975da40000000049454e44ae426082"
)


def tiny_image():
    """A 2×2 PNG (red | blue) as the ImageData the reader and the editor would make from the file."""
    from presstoshape.formats.image_info import probe

    return probe(TINY_PNG)


def quadrant_picture(width=60, height=30):
    """An ImageData of a PNG with four differently coloured quadrants, so alignment and mirroring show."""
    import skia

    from presstoshape.formats.image_info import probe

    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    colors = (skia.ColorRED, skia.ColorGREEN, skia.ColorBLUE, skia.ColorYELLOW)
    for index, color in enumerate(colors):
        left, top = (index % 2) * width / 2, (index // 2) * height / 2
        canvas.drawRect(skia.Rect.MakeXYWH(left, top, width / 2, height / 2), skia.Paint(Color=color))
    return probe(surface.makeImageSnapshot().encodeToData(skia.EncodedImageFormat.kPNG, 100).bytes())
