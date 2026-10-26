"""Exporting stored palettes (or the document's swatches): one to a file, or several into a folder."""

from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from presstoshape.formats.palette_files import file_name
from presstoshape.formats.palettes import WRITE_SUFFIXES, write_palette
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.colours import Palette

FILTERS = {
    ".gpl": N_("GIMP palette (*.gpl)"),
    ".hex": N_("Hex palette (*.hex)"),
    ".pal": N_("JASC palette (*.pal)"),
    ".txt": N_("Paint.NET palette (*.txt)"),
}


def palette_text(palette: Palette, suffix: str) -> str:
    return write_palette(suffix, palette.name, [(s.name, s.color, s.opacity) for s in palette.swatches])


def export_one(parent: QWidget, palette: Palette) -> None:
    filters = {_(text): suffix for suffix, text in FILTERS.items()}
    proposed = file_name(palette.name, [], "")
    path, chosen = QFileDialog.getSaveFileName(parent, _("Export Palette"), proposed, ";;".join(filters))
    if not path:
        return
    target = Path(path)
    if target.suffix.lower() not in WRITE_SUFFIXES:
        target = target.with_name(target.name + filters.get(chosen, ".gpl"))
    try:
        target.write_text(palette_text(palette, target.suffix.lower()), encoding="utf-8")
    except OSError as error:
        QMessageBox.warning(
            parent, _("Export Palette"), _("{name}: {error}").format(name=target.name, error=error.strerror or error)
        )


def export_names(palettes: Sequence[Palette], suffix: str) -> list[str]:
    """One file name per palette, unique within the batch."""
    names: list[str] = []
    for palette in palettes:
        names.append(file_name(palette.name, names, suffix))
    return names


def write_palettes(folder: Path, palettes: Sequence[Palette], suffix: str) -> list[tuple[str, str]]:
    """Writes every palette into `folder`; the files that failed, with the reason."""
    failures = []
    for palette, name in zip(palettes, export_names(palettes, suffix)):
        try:
            (folder / name).write_text(palette_text(palette, suffix), encoding="utf-8")
        except OSError as error:
            failures.append((name, str(error.strerror or error)))
    return failures


def export_many(parent: QWidget, palettes: Sequence[Palette]) -> None:
    chosen = QFileDialog.getExistingDirectory(parent, _("Export Palettes to Folder"))
    if not chosen:
        return
    labels = [_(text) for text in FILTERS.values()]
    label, accepted = QInputDialog.getItem(parent, _("Export Palettes"), _("Format:"), labels, 0, False)
    if not accepted:
        return
    suffix = list(FILTERS)[labels.index(label)]
    folder = Path(chosen)
    existing = [name for name in export_names(palettes, suffix) if (folder / name).exists()]
    if existing:
        answer = QMessageBox.question(
            parent,
            _("Export Palettes"),
            ngettext(
                "{count} file with this name already exists in the folder. Replace it?",
                "{count} files with these names already exist in the folder. Replace them?",
                len(existing),
            ).format(count=len(existing)),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
    failures = write_palettes(folder, palettes, suffix)
    if failures:
        QMessageBox.warning(
            parent,
            _("Export Palettes"),
            "\n".join(_("{name}: {error}").format(name=name, error=error) for name, error in failures),
        )
