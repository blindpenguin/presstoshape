"""What an SVG import couldn't keep or only approximated, counted per kind and worded for the user."""

from collections import Counter
from enum import Enum, auto

from presstoshape.i18n import ngettext


class Note(Enum):
    PATTERN = auto()
    COLOR_INTERPOLATION = auto()
    CLIP = auto()
    MASK = auto()
    MASK_COLOR_SPACE = auto()
    IMAGE_MISSING = auto()
    IMAGE_UNSUPPORTED = auto()
    IMAGE_REMOTE = auto()
    IMAGE_TOO_LARGE = auto()
    IMAGE_SVG = auto()
    FILTER = auto()
    MARKER = auto()
    GROUP_OPACITY = auto()
    CSS_SKIPPED = auto()
    MISSING_REFERENCE = auto()
    CYCLIC_REFERENCE = auto()
    MIXED_TEXT = auto()
    VIEWPORT_OVERFLOW = auto()
    UNKNOWN_ELEMENT = auto()
    COMPOSITE_UNREADABLE = auto()
    COMPOSITE_EDITED = auto()
    ANGLED_GUIDE = auto()
    BROKEN_GRID = auto()
    PATH_ERROR = auto()
    INVALID_VALUE = auto()
    CONDITIONAL = auto()
    UNEVEN_STROKE = auto()
    TEXT_SKEW = auto()


def _message(note: Note, count: int) -> str:
    match note:
        case Note.PATTERN:
            text = ngettext("{count} pattern was painted grey", "{count} patterns were painted grey", count)
        case Note.COLOR_INTERPOLATION:
            text = ngettext(
                "{count} gradient asks for linearRGB colour mixing, sRGB is used",
                "{count} gradients ask for linearRGB colour mixing, sRGB is used",
                count,
            )
        case Note.CLIP:
            text = ngettext(
                "{count} clip path was ignored, its content is shown unclipped",
                "{count} clip paths were ignored, their content is shown unclipped",
                count,
            )
        case Note.MASK:
            text = ngettext(
                "{count} mask was ignored, its content is shown unmasked",
                "{count} masks were ignored, their content is shown unmasked",
                count,
            )
        case Note.MASK_COLOR_SPACE:
            text = ngettext(
                "{count} mask asks for linearRGB colour mixing, sRGB is used",
                "{count} masks ask for linearRGB colour mixing, sRGB is used",
                count,
            )
        case Note.IMAGE_MISSING:
            text = ngettext(
                "{count} image was left out: its file was not found",
                "{count} images were left out: their files were not found",
                count,
            )
        case Note.IMAGE_UNSUPPORTED:
            text = ngettext(
                "{count} image was left out: it is not a readable PNG, JPEG, WebP or GIF",
                "{count} images were left out: they are not readable PNG, JPEG, WebP or GIF files",
                count,
            )
        case Note.IMAGE_REMOTE:
            text = ngettext(
                "{count} image was left out: it is on the internet, which PressToShape does not fetch",
                "{count} images were left out: they are on the internet, which PressToShape does not fetch",
                count,
            )
        case Note.IMAGE_TOO_LARGE:
            text = ngettext(
                "{count} image was left out: it is too large",
                "{count} images were left out: they are too large",
                count,
            )
        case Note.IMAGE_SVG:
            text = ngettext(
                "{count} image was left out: it is an SVG drawing, which cannot be placed as a picture",
                "{count} images were left out: they are SVG drawings, which cannot be placed as pictures",
                count,
            )
        case Note.FILTER:
            text = ngettext(
                "{count} filter effect (blur, shadow, …) was left out",
                "{count} filter effects (blur, shadow, …) were left out",
                count,
            )
        case Note.MARKER:
            text = ngettext(
                "{count} line with markers (arrowheads) lost them",
                "{count} lines with markers (arrowheads) lost them",
                count,
            )
        case Note.GROUP_OPACITY:
            text = ngettext(
                "{count} transparent group was approximated by making each object in it transparent",
                "{count} transparent groups were approximated by making each object in them transparent",
                count,
            )
        case Note.CSS_SKIPPED:
            text = ngettext("{count} CSS rule was not applied", "{count} CSS rules were not applied", count)
        case Note.MISSING_REFERENCE:
            text = ngettext(
                "{count} reference to a missing element was left out",
                "{count} references to missing elements were left out",
                count,
            )
        case Note.CYCLIC_REFERENCE:
            text = ngettext(
                "{count} reference that refers to itself was left out",
                "{count} references that refer to themselves were left out",
                count,
            )
        case Note.MIXED_TEXT:
            text = ngettext(
                "{count} text line with mixed styles now uses one style",
                "{count} text lines with mixed styles now use one style each",
                count,
            )
        case Note.VIEWPORT_OVERFLOW:
            text = ngettext(
                "{count} viewport would clip its content; it is shown unclipped",
                "{count} viewports would clip their content; it is shown unclipped",
                count,
            )
        case Note.UNKNOWN_ELEMENT:
            text = ngettext("{count} other element was left out", "{count} other elements were left out", count)
        case Note.COMPOSITE_UNREADABLE:
            text = ngettext(
                "{count} composite couldn't be read and was opened as a path",
                "{count} composites couldn't be read and were opened as paths",
                count,
            )
        case Note.COMPOSITE_EDITED:
            text = ngettext(
                "{count} composite was edited in another program and was opened as a path",
                "{count} composites were edited in another program and were opened as paths",
                count,
            )
        case Note.ANGLED_GUIDE:
            text = ngettext("{count} angled guide was left out", "{count} angled guides were left out", count)
        case Note.BROKEN_GRID:
            text = ngettext(
                "{count} grid setting couldn't be read, the default grid is used",
                "{count} grid settings couldn't be read, the default grid is used",
                count,
            )
        case Note.PATH_ERROR:
            text = ngettext(
                "{count} path had errors and was cut short", "{count} paths had errors and were cut short", count
            )
        case Note.INVALID_VALUE:
            text = ngettext("{count} invalid value was ignored", "{count} invalid values were ignored", count)
        case Note.CONDITIONAL:
            text = ngettext(
                "{count} element meant for another language or viewer was left out",
                "{count} elements meant for another language or viewer were left out",
                count,
            )
        case Note.UNEVEN_STROKE:
            text = ngettext(
                "{count} stroke under uneven scaling was approximated",
                "{count} strokes under uneven scaling were approximated",
                count,
            )
        case Note.TEXT_SKEW:
            text = ngettext("{count} skewed text lost its skew", "{count} skewed texts lost their skew", count)
    return text.format(count=count)


class NoteCollector:
    def __init__(self) -> None:
        self._counts: Counter[Note] = Counter()

    def add(self, note: Note, count: int = 1) -> None:
        if count > 0:
            self._counts[note] += count

    def count(self, note: Note) -> int:
        return self._counts[note]

    def messages(self) -> list[str]:
        """One message per kind of note, in a fixed order."""
        return [_message(note, self._counts[note]) for note in Note if self._counts[note]]
