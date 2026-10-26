from presstoshape.editing.operations import colours
from presstoshape.editing.operations.style import display_style
from presstoshape.geometry.boxes import Point
from presstoshape.models.shapes import ImageShape
from presstoshape.render import hit_test
from presstoshape.render.scene import visible_shapes
from presstoshape.tools.base import HIT_TOLERANCE_PX, BaseTool, CursorType, Mods


class EyedropperTool(BaseTool):
    """Click a shape: the selection takes its style (no selection: the colour panel takes its colours). Shift+click,
    or a click on a picture: the active paint takes the colour shown under the pointer."""

    cursor = CursorType.EYEDROPPER

    def press(self, point: Point, mods: Mods) -> None:
        context = self._context
        state = context.state
        leaf = hit_test.leaf_at(
            list(visible_shapes(state.document)), context.cache, point, HIT_TOLERANCE_PX * context.pixel_size
        )
        if mods.shift or isinstance(leaf, ImageShape):
            color = context.sample_color(point)
            if color is not None:
                colours.apply_sampled_colour(context.session, color)
        elif leaf is not None:
            colours.pick_up_style(context.session, display_style(leaf))
