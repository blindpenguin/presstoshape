"""Replays the document from recorded Skia pictures, so a frame isn't thousands of draw calls from Python."""

import skia

from presstoshape.models.app_state import Document
from presstoshape.models.shapes import IDENTITY_TRANSFORM, Shape, Transform
from presstoshape.render.paths import PathCache, to_skia_matrix
from presstoshape.render.scene import draw_shape, visible_shapes

# Shapes may sit anywhere on the pasteboard; the cull rect only has to contain them.
_CULL = skia.Rect.MakeLTRB(-1e7, -1e7, 1e7, 1e7)


class DocumentPicture:
    """Paint order split into runs of static and moving shapes, each recorded once.

    While dragging only the matrix (or the live replacement shapes) changes, so the runs are reused and the
    moving ones replayed transformed, or skipped in favor of the live shapes. Any document change or a different
    moving set re-records.
    """

    def __init__(self, cache: PathCache) -> None:
        self._cache = cache
        self._key: tuple | None = None
        self._runs: list[tuple[bool, skia.Picture, tuple[int, ...]]] = []

    def draw(
        self,
        canvas: skia.Canvas,
        doc: Document,
        moving: frozenset[int] = frozenset(),
        matrix: Transform = IDENTITY_TRANSFORM,
        live: tuple[Shape, ...] = (),
    ) -> None:
        # Tuple comparison checks identity first, so an unchanged document compares in a fast C loop.
        key = (tuple((layer.visible, tuple(layer.shapes)) for layer in doc.layers), moving)
        if key != self._key:
            self._runs = self._record(doc, moving)
            self._key = key
        replacements = {s.id: s for s in live}
        for is_moving, picture, ids in self._runs:
            if not is_moving:
                canvas.drawPicture(picture)
            elif replacements:
                for shape_id in ids:
                    if shape_id in replacements:
                        draw_shape(canvas, replacements[shape_id], self._cache)
            else:
                canvas.save()
                canvas.concat(to_skia_matrix(matrix))
                canvas.drawPicture(picture)
                canvas.restore()

    def _record(self, doc: Document, moving: frozenset[int]) -> list[tuple[bool, skia.Picture, tuple[int, ...]]]:
        runs: list[tuple[bool, skia.Picture, tuple[int, ...]]] = []
        recorder: skia.PictureRecorder | None = None
        run_moving = False
        ids: list[int] = []
        for shape in visible_shapes(doc):
            is_moving = shape.id in moving
            if recorder is None or is_moving != run_moving:
                if recorder is not None:
                    runs.append((run_moving, recorder.finishRecordingAsPicture(), tuple(ids)))
                recorder = skia.PictureRecorder()
                recorder.beginRecording(_CULL, skia.RTreeFactory()())
                run_moving = is_moving
                ids = []
            draw_shape(recorder.getRecordingCanvas(), shape, self._cache)
            ids.append(shape.id)
        if recorder is not None:
            runs.append((run_moving, recorder.finishRecordingAsPicture(), tuple(ids)))
        return runs
