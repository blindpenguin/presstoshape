"""Replays shapes from recorded Skia pictures, so a frame isn't thousands of draw calls from Python."""

from collections.abc import Callable, Iterable, Iterator, Sequence

import skia

from presstoshape.models.app_state import Document
from presstoshape.models.shapes import (
    IDENTITY_TRANSFORM,
    CompositeShape,
    ContainerShape,
    ImageShape,
    Shape,
    Transform,
    children_of,
)
from presstoshape.render.images import device_scale, image_sampling
from presstoshape.render.overlay import CanvasColors, Overlay
from presstoshape.render.paths import PathCache, to_skia_matrix
from presstoshape.render.scene import (
    draw_composite_parts,
    draw_dim,
    draw_mask_outlines,
    draw_shape,
    edit_mode_outer,
    live_container,
    visible_shapes,
)

# Shapes may sit anywhere on the pasteboard; the cull rect only has to contain them.
_CULL = skia.Rect.MakeLTRB(-1e7, -1e7, 1e7, 1e7)


def record(shapes: Iterable[Shape], cache: PathCache) -> skia.Picture:
    recorder = skia.PictureRecorder()
    recording = recorder.beginRecording(_CULL, skia.RTreeFactory()())
    for shape in shapes:
        draw_shape(recording, shape, cache)
    return recorder.finishRecordingAsPicture()


def _images_in(shape: Shape) -> Iterator[ImageShape]:
    if isinstance(shape, ImageShape):
        yield shape
    for child in children_of(shape):
        yield from _images_in(child)


class ShapesPicture:
    """Paint order split into runs of static and moving shapes, each recorded once.

    While dragging only the matrix (or the live replacement shapes) changes, so the runs are reused and the
    moving ones replayed transformed, or skipped in favor of the live shapes. A content change (by `key`) or a
    different moving set re-records.
    """

    def __init__(self, cache: PathCache) -> None:
        self._cache = cache
        self._key: tuple | None = None
        self._runs: list[tuple[bool, skia.Picture, tuple[int, ...]]] = []
        self._images: tuple[ImageShape, ...] = ()

    def draw_shapes(
        self,
        canvas: skia.Canvas,
        shapes: Sequence[Shape],
        moving: frozenset[int] = frozenset(),
        matrix: Transform = IDENTITY_TRANSFORM,
        live: tuple[Shape, ...] = (),
        hidden: frozenset[int] = frozenset(),
        references: bool = True,
    ) -> None:
        """`shapes` bottom to top; `hidden` ones are left out (drawn elsewhere)."""
        shapes = tuple(shapes)
        self._draw(canvas, shapes, lambda: shapes, moving, matrix, live, hidden, references)

    def _draw(
        self,
        canvas: skia.Canvas,
        content_key: object,
        shapes: Callable[[], Iterable[Shape]],
        moving: frozenset[int],
        matrix: Transform,
        live: tuple[Shape, ...],
        hidden: frozenset[int],
        references: bool = True,
    ) -> None:
        separate = moving | hidden
        zoom = device_scale(canvas)
        # Tuple comparison checks identity first, so unchanged content compares in a fast C loop. Images are
        # recorded for the sampling their zoom calls for, so the picture is also valid only while that holds.
        key = (content_key, separate, references, self._sampling(zoom))
        if key != self._key:
            with self._cache.drawing(zoom, references):
                self._runs, self._images = self._record(shapes(), separate)
            self._key = (content_key, separate, references, self._sampling(zoom))
        replacements = {s.id: s for s in live}
        for is_moving, picture, ids in self._runs:
            if not is_moving:
                canvas.drawPicture(picture)
            elif all(shape_id in hidden for shape_id in ids):
                continue
            elif replacements:
                for shape_id in ids:
                    if shape_id in replacements:
                        draw_shape(canvas, replacements[shape_id], self._cache)
            else:
                canvas.save()
                canvas.concat(to_skia_matrix(matrix))
                canvas.drawPicture(picture)
                canvas.restore()

    def _sampling(self, zoom: float) -> tuple[tuple[bool, int], ...]:
        return tuple(image_sampling(shape, zoom) for shape in self._images)

    def _record(
        self, shapes: Iterable[Shape], moving: frozenset[int]
    ) -> tuple[list[tuple[bool, skia.Picture, tuple[int, ...]]], tuple[ImageShape, ...]]:
        runs: list[tuple[bool, skia.Picture, tuple[int, ...]]] = []
        images: list[ImageShape] = []
        recorder: skia.PictureRecorder | None = None
        run_moving = False
        ids: list[int] = []
        for shape in shapes:
            is_moving = shape.id in moving
            if recorder is None or is_moving != run_moving:
                if recorder is not None:
                    runs.append((run_moving, recorder.finishRecordingAsPicture(), tuple(ids)))
                recorder = skia.PictureRecorder()
                recorder.beginRecording(_CULL, skia.RTreeFactory()())
                run_moving = is_moving
                ids = []
            draw_shape(recorder.getRecordingCanvas(), shape, self._cache)
            images.extend(_images_in(shape))
            ids.append(shape.id)
        if recorder is not None:
            runs.append((run_moving, recorder.finishRecordingAsPicture(), tuple(ids)))
        return runs, tuple(images)


class DocumentPicture(ShapesPicture):
    """The document's visible layers, plus the copies an Alt+drag shows."""

    def __init__(self, cache: PathCache) -> None:
        super().__init__(cache)
        self._copies_key: tuple[Shape, ...] = ()
        self._copies: skia.Picture | None = None

    def draw(
        self,
        canvas: skia.Canvas,
        doc: Document,
        moving: frozenset[int] = frozenset(),
        matrix: Transform = IDENTITY_TRANSFORM,
        live: tuple[Shape, ...] = (),
        hidden: frozenset[int] = frozenset(),
        references: bool = True,
    ) -> None:
        """`hidden` shapes are left out (the shape being edited inside, drawn by edit mode)."""
        content = tuple((layer.visible, tuple(layer.shapes)) for layer in doc.layers)
        self._draw(canvas, content, lambda: visible_shapes(doc), moving, matrix, live, hidden, references)

    def draw_copies(self, canvas: skia.Canvas, copies: tuple[Shape, ...], matrix: Transform) -> None:
        """`copies` through `matrix`, recorded once per set of shapes so each frame is one replay."""
        if not copies:
            self._copies_key, self._copies = (), None
            return
        if self._copies is None or copies != self._copies_key:
            self._copies_key, self._copies = copies, record(copies, self._cache)
        canvas.save()
        canvas.concat(to_skia_matrix(matrix))
        canvas.drawPicture(self._copies)
        canvas.restore()


class EditModeDrawing:
    """scene.draw_edit_mode with recorded pictures: the dimmed surroundings are recorded once per value of the
    outer shape, an entered group's shapes like the document (runs of static and moving shapes). Entering a
    large imported group therefore costs about as much per frame as the document view."""

    def __init__(self, cache: PathCache) -> None:
        self._cache = cache
        self._outer: Shape | None = None
        self._outer_picture: skia.Picture | None = None
        self._inside = ShapesPicture(cache)

    def draw(
        self,
        canvas: skia.Canvas,
        chain: Sequence[ContainerShape],
        overlay: Overlay,
        zoom: float,
        colors: CanvasColors,
    ) -> None:
        outer = edit_mode_outer(chain, overlay)
        # Identity first: inside a group the outer value is rebuilt per frame but equal while dragging.
        if self._outer_picture is None or (outer is not self._outer and outer != self._outer):
            self._outer, self._outer_picture = outer, record([outer], self._cache)
        canvas.drawPicture(self._outer_picture)
        draw_dim(canvas, colors)
        innermost = chain[-1]
        if isinstance(innermost, CompositeShape):
            draw_composite_parts(canvas, live_container(innermost, overlay), zoom, colors)
        else:
            self._inside.draw_shapes(canvas, innermost.children, overlay.moving, overlay.matrix, overlay.live)
            if innermost.masking is not None:
                draw_mask_outlines(canvas, live_container(innermost, overlay), zoom, colors, self._cache)
