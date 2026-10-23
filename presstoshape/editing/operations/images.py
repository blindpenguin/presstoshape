"""Pictures: place, replace, resize and turn into reference images."""

from collections.abc import Sequence
from dataclasses import dataclass, replace

from presstoshape.editing import containers, queries
from presstoshape.editing.operations._document import add_on_top, new_id, prune_selection
from presstoshape.editing.registry import operation
from presstoshape.editing.session import Session
from presstoshape.formats.image_info import ImageError, probe
from presstoshape.geometry.boxes import Point
from presstoshape.i18n import N_, _, ngettext, pgettext
from presstoshape.models.app_state import AppState, Layer
from presstoshape.models.shapes import ImageData, ImageShape, Shape
from presstoshape.render.images import trial_decode

# A placed picture shows at its pixel size, but never wider or taller than this share of the page.
PAGE_SHARE = 0.8
# Each further picture of one placement sits this far right and down, so they don't hide each other.
STAGGER = 16.0


@dataclass(frozen=True)
class PlaceResult:
    """The shapes a placement made and the files it refused, each with the message naming file and reason."""

    placed: tuple[int, ...] = ()
    refused: tuple[tuple[str, str], ...] = ()


def _reference_layer_name() -> str:
    return pgettext("layer name", "Reference")


def prepare(files: Sequence[tuple[str, bytes]]) -> tuple[list[ImageData], list[tuple[str, str]]]:
    """Pictures from `(name, file bytes)`, one blob per distinct content, and the refused files with a message.
    A file whose header is fine but whose pixels don't decode is refused too."""
    accepted: list[ImageData] = []
    refused: list[tuple[str, str]] = []
    known: dict[str, ImageData] = {}
    for name, raw in files:
        try:
            data = probe(raw)
            if data.digest not in known and not trial_decode(data):
                raise ImageError("corrupt")
        except ImageError as error:
            refused.append((name, error.message(name)))
            continue
        accepted.append(known.setdefault(data.digest, data))
    return accepted, refused


def _picture_size(data: ImageData, state: AppState) -> tuple[float, float]:
    document = state.document
    scale = min(1.0, PAGE_SHARE * document.width / data.width, PAGE_SHARE * document.height / data.height)
    return data.width * scale, data.height * scale


def _reference_layer(state: AppState) -> Layer:
    """The layer for reference images, made (locked, below everything) when the document has none."""
    name = _reference_layer_name()
    for layer in state.document.layers:
        if layer.name == name:
            return layer
    layer = Layer(name, locked=True)
    state.document.layers.insert(0, layer)
    state.selected_layer_index += 1
    return layer


def place_images(
    session: Session, files: Sequence[tuple[str, bytes]], center: Point, reference: bool = False
) -> PlaceResult:
    """Puts the pictures of `files` (name, bytes) around `center` on top of the active container, selected; as
    reference images in the Reference layer when `reference`. One undo step; files that can't be used are
    refused with a message and the others are placed anyway."""
    state = session.state
    pictures, refused = prepare(files)
    if pictures and containers.edited_composite(state) is not None:
        message = _("Images can't be placed inside a Composite")
        refused = [*refused, *((name, message) for name, _raw in files)]
        pictures = []
    if not pictures:
        state.status_message = refused[0][1] if refused else _("Nothing to place")
        session.notify()
        return PlaceResult(refused=tuple(refused))
    count = len(pictures)
    if reference:
        label = ngettext("Place reference image", "Place {count} reference images", count).format(count=count)
    else:
        label = ngettext("Place image", "Place {count} images", count).format(count=count)
    with session.edit(label):
        shapes: list[Shape] = []
        for index, data in enumerate(pictures):
            width, height = _picture_size(data, state)
            x = center[0] - width / 2 + index * STAGGER
            y = center[1] - height / 2 + index * STAGGER
            shapes.append(ImageShape(new_id(state), x, y, width, height, data, reference=reference, locked=reference))
        if reference:
            _reference_layer(state).shapes.extend(shapes)
            state.selection = set()
        else:
            add_on_top(state, shapes)
            state.selection = {shape.id for shape in shapes}
        state.node_selection = frozenset()
        state.status_message = (
            ngettext("Placed {count} reference image", "Placed {count} reference images", count)
            if reference
            else ngettext("Placed {count} image", "Placed {count} images", count)
        ).format(count=count)
        if refused:
            state.status_message = "; ".join([state.status_message, *(message for _name, message in refused)])
    return PlaceResult(tuple(shape.id for shape in shapes), tuple(refused))


def selected_images(state: AppState, reference: bool | None = None, locked_too: bool = False) -> list[ImageShape]:
    """Selected pictures; `reference` True or False keeps only those. Locked ones count with `locked_too`."""
    found = (
        (queries.find_shape(state, shape_id) for shape_id in sorted(state.selection))
        if locked_too
        else containers.active_shapes(state)
    )
    return [
        shape
        for shape in found
        if isinstance(shape, ImageShape)
        and shape.id in state.selection
        and not shape.hidden
        and (locked_too or not shape.locked)
        and (reference is None or shape.reference == reference)
    ]


def _has_images(session: Session) -> bool:
    return bool(selected_images(session.state))


def _has_artwork(session: Session) -> bool:
    return bool(selected_images(session.state, reference=False))


def _has_references(session: Session) -> bool:
    return bool(selected_images(session.state, reference=True, locked_too=True))


def _change_images(session: Session, images: Sequence[ImageShape], label: str, change, message: str, then=None) -> None:
    wanted = {shape.id for shape in images}
    state = session.state
    with session.edit(label):
        containers.change_container(
            state, lambda shapes: [change(shape) if shape.id in wanted else shape for shape in shapes]
        )
        if then is not None:
            then(state)
        state.status_message = message


def _about_center(shape: ImageShape, width: float, height: float) -> ImageShape:
    center_x, center_y = shape.x + shape.width / 2, shape.y + shape.height / 2
    return replace(shape, x=center_x - width / 2, y=center_y - height / 2, width=width, height=height)


@operation("image.reset_size", N_("&Reset Image Size"), can_run=_has_images)
def reset_size(session: Session) -> None:
    """The selected pictures back to their pixel size, about their centres."""
    images = selected_images(session.state)
    if images:
        _change_images(
            session,
            images,
            _("Reset image size"),
            lambda shape: _about_center(shape, float(shape.data.width), float(shape.data.height)),
            _("Reset the image size"),
        )


def _fitted_to_page(shape: ImageShape, state: AppState) -> ImageShape:
    document = state.document
    scale = min(document.width / shape.data.width, document.height / shape.data.height)
    width, height = shape.data.width * scale, shape.data.height * scale
    return replace(
        shape,
        x=(document.width - width) / 2,
        y=(document.height - height) / 2,
        width=width,
        height=height,
        transform=(1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
    )


@operation("image.fit_page", N_("&Fit Image to Page"), can_run=_has_images)
def fit_page(session: Session) -> None:
    """The selected pictures as large as the page allows, centred on it."""
    state = session.state
    images = selected_images(state)
    if images:
        _change_images(
            session,
            images,
            _("Fit image to page"),
            lambda shape: _fitted_to_page(shape, state),
            _("Fitted to the page"),
        )


@operation("image.make_reference", N_("Make Ref&erence"), can_run=_has_artwork)
def make_reference(session: Session) -> None:
    """The selected pictures become reference images: dimmed, locked and left out of exports."""
    images = selected_images(session.state, reference=False)
    if not images:
        return
    _change_images(
        session,
        images,
        _("Make reference image"),
        lambda shape: replace(shape, reference=True, locked=True),
        _("Made a reference image"),
    )
    prune_selection(session.state)


@operation("image.make_artwork", N_("Make &Artwork"), can_run=_has_references)
def make_artwork(session: Session) -> None:
    """The selected reference images become ordinary pictures again."""
    images = selected_images(session.state, reference=True, locked_too=True)
    if images:
        _change_images(
            session,
            images,
            _("Make image artwork"),
            lambda shape: replace(shape, reference=False, locked=False),
            _("Made the image artwork"),
            _unlock_emptied_reference_layers,
        )


def _unlock_emptied_reference_layers(state: AppState) -> None:
    """The Reference layer is locked for its reference images; once it holds none, it is an ordinary layer."""
    name = _reference_layer_name()
    for layer in state.document.layers:
        has_reference = any(isinstance(shape, ImageShape) and shape.reference for shape in layer.shapes)
        if layer.name == name and layer.locked and not has_reference:
            layer.locked = False


def replace_image(session: Session, shape_id: int, name: str, raw: bytes) -> PlaceResult:
    """Swaps the picture of an image, keeping its position, width and transform; the height follows the new
    picture's ratio about the same centre. One undo step; a file that can't be used changes nothing."""
    state = session.state
    pictures, refused = prepare([(name, raw)])
    target = queries.find_shape(state, shape_id)
    if not isinstance(target, ImageShape) or not pictures:
        state.status_message = refused[0][1] if refused else _("Select an image to replace")
        session.notify()
        return PlaceResult(refused=tuple(refused))
    data = pictures[0]

    def refit(shape: ImageShape) -> ImageShape:
        return _about_center(replace(shape, data=data), shape.width, shape.width * data.height / data.width)

    with session.edit(_("Replace image")):
        containers.change_container(
            state, lambda shapes: [refit(shape) if shape.id == shape_id else shape for shape in shapes]
        )
        state.status_message = _("Replaced the image")
    return PlaceResult((shape_id,))
