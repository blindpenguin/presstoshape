"""Importing palette files: one or many at once (a set of Lospec downloads, chosen together). Each file becomes its
own stored palette; name clashes are settled in a dialog before anything changes, and a summary lists the rest."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from presstoshape.editing.operations import palettes
from presstoshape.editing.operations.palettes import Choice, ImportCounts, ImportItem
from presstoshape.editing.session import Session
from presstoshape.formats.palettes import READ_SUFFIXES, PaletteColor, colors_from_pixels, read_named_palette
from presstoshape.i18n import N_, _, ngettext

MAX_FILES = 1000
MAX_COLORS = 1024
ALL_PALETTES_FILTER = N_("Palettes (*.gpl *.hex *.pal *.txt *.png)")
FILE_FILTERS = (
    ALL_PALETTES_FILTER,
    N_("GIMP palette (*.gpl)"),
    N_("Hex palette (*.hex)"),
    N_("JASC palette (*.pal)"),
    N_("Paint.NET palette (*.txt)"),
    N_("Palette image (*.png)"),
)
_CHOICES: tuple[tuple[Choice, str], ...] = (
    ("keep", N_("Keep both")),
    ("replace", N_("Replace")),
    ("skip", N_("Skip")),
)


def open_filter() -> str:
    return ";;".join(_(text) for text in FILE_FILTERS)


def read_file(path: Path) -> tuple[str | None, list[PaletteColor]]:
    """The name stored in the file (None if it has none) and its colours: text palettes by header or suffix,
    images (Lospec's PNG palettes) by their pixel colours. Raises OSError or ValueError."""
    if path.suffix.lower() in READ_SUFFIXES:
        return read_named_palette(path.suffix, path.read_text(encoding="utf-8", errors="replace"))
    image = QImage(str(path))
    if image.isNull():
        raise ValueError("not a palette file or image")
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return None, colors_from_pixels(image.width(), image.height(), bytes(image.constBits())[: image.sizeInBytes()])


@dataclass
class ReadResult:
    items: list[ImportItem] = field(default_factory=list)
    # The file for each item, by item index.
    sources: list[Path] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)


def read_items(files: Sequence[Path], parent: QWidget | None = None) -> ReadResult | None:
    """Reads every file into an import item named by the file (stored name, else file name); files that fail are
    listed with the reason. Shows progress when it takes longer than a second; None if the user cancels."""
    result = ReadResult()
    progress = QProgressDialog(_("Reading palettes…"), _("Cancel"), 0, len(files), parent)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(1000)
    for number, path in enumerate(files):
        progress.setValue(number)
        if progress.wasCanceled():
            return None
        try:
            name, colors = read_file(path)
        except OSError:
            result.failures.append((path.name, _("can't be read")))
            continue
        except ValueError:
            result.failures.append((path.name, _("isn't a palette PressToShape can read")))
            continue
        if not colors:
            result.failures.append((path.name, _("has no colours")))
        elif len(colors) > MAX_COLORS:
            result.failures.append((path.name, _("has more than {count} colours").format(count=MAX_COLORS)))
        else:
            result.items.append(ImportItem(name or path.stem, tuple(colors)))
            result.sources.append(path)
    progress.setValue(len(files))
    return result


class ClashDialog(QDialog):
    """One row per clashing palette with what to do about it; Import returns the choices, Cancel imports nothing."""

    def __init__(self, items: Sequence[ImportItem], sources: Sequence[Path], clashing: Sequence[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Palettes Already There"))
        self._rows = list(clashing)
        intro = QLabel(
            ngettext(
                "A palette with this name already exists. Replacing overwrites its colours.",
                "Palettes with these names already exist. Replacing overwrites their colours.",
                len(self._rows),
            )
        )
        intro.setWordWrap(True)
        self._table = QTableWidget(len(self._rows), 3)
        self._table.setHorizontalHeaderLabels([_("Palette"), _("File"), _("Action")])
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._boxes: list[QComboBox] = []
        for row, index in enumerate(self._rows):
            self._table.setItem(row, 0, QTableWidgetItem(items[index].name))
            self._table.setItem(row, 1, QTableWidgetItem(sources[index].name))
            box = QComboBox()
            for value, label in _CHOICES:
                box.addItem(_(label), value)
            self._table.setCellWidget(row, 2, box)
            self._boxes.append(box)
        all_row = QHBoxLayout()
        for value, label in (
            ("keep", N_("Keep All")),
            ("replace", N_("Replace All")),
            ("skip", N_("Skip All")),
        ):
            button = QPushButton(_(label))
            button.clicked.connect(lambda checked=False, v=value: self.set_all(v))
            all_row.addWidget(button)
        all_row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton(_("Import"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self._table, 1)
        layout.addLayout(all_row)
        layout.addWidget(buttons)
        self.resize(560, 360)

    def set_all(self, choice: Choice) -> None:
        for box in self._boxes:
            box.setCurrentIndex(box.findData(choice))

    def set_choice(self, row: int, choice: Choice) -> None:
        self._boxes[row].setCurrentIndex(self._boxes[row].findData(choice))

    def choices(self) -> dict[int, Choice]:
        return {index: box.currentData() for index, box in zip(self._rows, self._boxes)}


def _ask_choices(parent, items, sources, clashing) -> Mapping[int, Choice] | None:
    dialog = ClashDialog(items, sources, clashing, parent)
    return dialog.choices() if dialog.exec() == QDialog.DialogCode.Accepted else None


def summary_text(counts: ImportCounts, failures: Sequence[tuple[str, str]]) -> str:
    lines = [
        ngettext("{count} palette imported.", "{count} palettes imported.", counts.imported).format(
            count=counts.imported
        )
    ]
    if counts.replaced:
        lines.append(ngettext("{count} replaced.", "{count} replaced.", counts.replaced).format(count=counts.replaced))
    if counts.skipped:
        lines.append(ngettext("{count} skipped.", "{count} skipped.", counts.skipped).format(count=counts.skipped))
    if failures:
        lines.append("")
        lines.append(ngettext("This file couldn't be imported:", "These files couldn't be imported:", len(failures)))
        shown = failures[:20]
        lines += [_("{name}: {reason}").format(name=name, reason=reason) for name, reason in shown]
        if len(failures) > len(shown):
            lines.append(_("… and {count} more").format(count=len(failures) - len(shown)))
    return "\n".join(lines)


def _show_summary(parent, text: str) -> None:
    QMessageBox.information(parent, _("Import Palettes"), text)


def ask_paths(parent: QWidget) -> list[Path]:
    """The palette files the user picks; several can be selected at once."""
    paths, _chosen = QFileDialog.getOpenFileNames(parent, _("Import Palettes"), "", open_filter())
    return [Path(path) for path in paths]


def import_palettes(
    parent: QWidget | None,
    session: Session,
    paths: Sequence[Path],
    ask: Callable[..., Mapping[int, Choice] | None] = _ask_choices,
    report: Callable[[QWidget | None, str], None] = _show_summary,
) -> ImportCounts | None:
    """The whole flow for the chosen files; None when nothing was imported (cancelled, refused)."""
    files = list(paths)
    if len(files) > MAX_FILES:
        report(
            parent,
            _("That's {count} palette files; PressToShape imports at most {limit} at once.").format(
                count=len(files), limit=MAX_FILES
            ),
        )
        return None
    if not files:
        return None
    read = read_items(files, parent)
    if read is None:
        return None
    clashing = palettes.clashes(session.state.colours.palettes, read.items)
    choices: Mapping[int, Choice] = {}
    if clashing:
        asked = ask(parent, read.items, read.sources, clashing)
        if asked is None:
            return None
        choices = asked
    counts = palettes.apply_import(session, read.items, choices) if read.items else ImportCounts()
    if len(files) > 1 or read.failures or counts.replaced or counts.skipped:
        report(parent, summary_text(counts, read.failures))
    return counts
