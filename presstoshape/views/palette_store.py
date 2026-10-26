"""The palettes folder: one file per stored palette plus an index of their order. Loads at start, saves only what
changed, never touches files it couldn't read."""

from dataclasses import dataclass, field
from pathlib import Path

from presstoshape.editing.operations.documents import write_atomically
from presstoshape.editing.operations.palettes import unique_name
from presstoshape.formats.palette_files import INDEX_FILE, decode_index, decode_palette, encode_index, encode_palette
from presstoshape.formats.palette_files import file_name as palette_file_name
from presstoshape.formats.swatch_library import read_library
from presstoshape.i18n import _
from presstoshape.models.colours import Palette

# The single library file of earlier versions, next to the palettes folder.
OLD_LIBRARY = "swatches.json"
MIGRATED_LIBRARY = "swatches.migrated.json"


@dataclass
class LoadResult:
    palettes: tuple[Palette, ...] = ()
    # Files that couldn't be read (left as they are).
    problems: list[str] = field(default_factory=list)


class PaletteStore:
    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._files: dict[int, str] = {}
        # The palette object each file holds, to write only changed ones.
        self._saved: dict[int, Palette] = {}
        self._index: list[str] = []
        # Files in the folder that aren't loaded palettes (unreadable ones): never written over.
        self._foreign: set[str] = set()

    def load(self) -> LoadResult:
        result = LoadResult()
        if not self.folder.is_dir():
            self._migrate(result)
            return result
        try:
            index = decode_index((self.folder / INDEX_FILE).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            index = []
        present = sorted(
            path.name
            for path in self.folder.glob("*.json")
            if path.name != INDEX_FILE and not path.name.startswith(".") and path.is_file()
        )
        ordered = [name for name in dict.fromkeys(index) if name in present]
        ordered += [name for name in present if name not in ordered]
        palettes: list[Palette] = []
        for name in ordered:
            try:
                stored_name, swatches = decode_palette((self.folder / name).read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, ValueError):
                result.problems.append(name)
                self._foreign.add(name)
                continue
            palette = Palette(len(palettes) + 1, unique_name(palettes, stored_name), swatches)
            palettes.append(palette)
            self._files[palette.id] = name
            # A name made unique here differs from the file's: saved again on the next save.
            if palette.name == stored_name:
                self._saved[palette.id] = palette
        self._index = [self._files[palette.id] for palette in palettes] if index == ordered else index
        result.palettes = tuple(palettes)
        return result

    def _migrate(self, result: LoadResult) -> None:
        """The single library of earlier versions becomes the palette "My swatches"; its file is kept, renamed."""
        old = self.folder.parent / OLD_LIBRARY
        if not old.is_file():
            return
        try:
            swatches = read_library(old.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            result.problems.append(OLD_LIBRARY)
            return
        palette = Palette(1, _("My swatches"), swatches)
        self.save((palette,))
        old.replace(old.with_name(MIGRATED_LIBRARY))
        result.palettes = (palette,)

    def save(self, palettes: tuple[Palette, ...]) -> None:
        """Writes the palettes that changed since the last load or save, deletes the files of removed ones and
        rewrites the index when the order changed. Raises OSError; what was written stays written."""
        self.folder.mkdir(parents=True, exist_ok=True)
        current = {palette.id for palette in palettes}
        for palette_id in [palette_id for palette_id in self._files if palette_id not in current]:
            (self.folder / self._files.pop(palette_id)).unlink(missing_ok=True)
            self._saved.pop(palette_id, None)
        for palette in palettes:
            if palette.id not in self._files:
                taken = [*self._files.values(), *self._foreign, *(path.name for path in self.folder.iterdir())]
                self._files[palette.id] = palette_file_name(palette.name, taken)
            if self._saved.get(palette.id) is not palette:
                write_atomically(self.folder / self._files[palette.id], encode_palette(palette).encode("utf-8"))
                self._saved[palette.id] = palette
        order = [self._files[palette.id] for palette in palettes]
        if order != self._index:
            write_atomically(self.folder / INDEX_FILE, encode_index(order).encode("utf-8"))
            self._index = order
