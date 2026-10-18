"""Replays the document from recorded Skia pictures, so a frame isn't thousands of draw calls from Python."""

import skia

from veccy.models.app_state import Document
from veccy.render.paths import PathCache
from veccy.render.scene import draw_shape, visible_shapes

# Shapes may sit anywhere on the pasteboard; the cull rect only has to contain them.
_CULL = skia.Rect.MakeLTRB(-1e7, -1e7, 1e7, 1e7)


class DocumentPicture:
    """Paint order split into runs of static and moving shapes, each recorded once.

    While dragging only the offset changes, so the runs are reused and the moving ones replayed translated.
    Any document change or a different moving set re-records.
    """

    def __init__(self, cache: PathCache) -> None:
        self._cache = cache
        self._key: tuple | None = None
        self._runs: list[tuple[bool, skia.Picture]] = []

    def draw(
        self,
        canvas: skia.Canvas,
        doc: Document,
        moving: frozenset[int] = frozenset(),
        offset: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        # Tuple comparison checks identity first, so an unchanged document compares in a fast C loop.
        key = (tuple((layer.visible, tuple(layer.shapes)) for layer in doc.layers), moving)
        if key != self._key:
            self._runs = self._record(doc, moving)
            self._key = key
        for is_moving, picture in self._runs:
            if is_moving:
                canvas.save()
                canvas.translate(*offset)
                canvas.drawPicture(picture)
                canvas.restore()
            else:
                canvas.drawPicture(picture)

    def _record(self, doc: Document, moving: frozenset[int]) -> list[tuple[bool, skia.Picture]]:
        runs: list[tuple[bool, skia.Picture]] = []
        recorder: skia.PictureRecorder | None = None
        run_moving = False
        for shape in visible_shapes(doc):
            is_moving = shape.id in moving
            if recorder is None or is_moving != run_moving:
                if recorder is not None:
                    runs.append((run_moving, recorder.finishRecordingAsPicture()))
                recorder = skia.PictureRecorder()
                recorder.beginRecording(_CULL, skia.RTreeFactory()())
                run_moving = is_moving
            draw_shape(recorder.getRecordingCanvas(), shape, self._cache)
        if recorder is not None:
            runs.append((run_moving, recorder.finishRecordingAsPicture()))
        return runs
