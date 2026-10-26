from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from presstoshape import icons
from presstoshape.editing.operations import palettes, swatches
from presstoshape.i18n import N_, _, ngettext
from presstoshape.models.colours import Palette
from presstoshape.views import palette_export, palette_import
from presstoshape.views.settings.pages import SettingsContext, SettingsPage
from presstoshape.views.swatch_grid import Cell, SwatchGrid, swatch_tooltip

_ID = Qt.ItemDataRole.UserRole
# How many names a delete question lists before "and N more".
_LISTED = 10


class _PaletteList(QListWidget):
    """Reorders by dragging; reports the new order of palette ids after a drop."""

    def __init__(self, on_reordered) -> None:
        super().__init__()
        self._on_reordered = on_reordered
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        self._on_reordered([self.item(row).data(_ID) for row in range(self.count())])


class PalettesPage(SettingsPage):
    """The stored palettes: list (drag to reorder), preview of the selected one, and what to do with them."""

    title = N_("Palettes")
    icon = icons.SETTINGS_PALETTES

    def __init__(self, context: SettingsContext) -> None:
        super().__init__(context)
        self._session = context.session
        layout = QVBoxLayout(self)
        if self._session is None:
            note = QLabel(_("Palettes can be managed when a drawing window is open."))
            note.setEnabled(False)
            layout.addWidget(note)
            layout.addStretch(1)
            return

        self._list = _PaletteList(lambda ids: palettes.set_palette_order(self._session, ids))
        self._list.itemSelectionChanged.connect(self._on_selection)
        self._list.itemDoubleClicked.connect(lambda item: self._rename())
        buttons = QVBoxLayout()
        self._buttons: dict[str, QPushButton] = {}
        for key, label, slot in (
            ("new", N_("New…"), self._new),
            ("rename", N_("Rename…"), self._rename),
            ("duplicate", N_("Duplicate"), self._duplicate),
            ("delete", N_("Delete…"), self._delete),
            (None, None, None),
            ("import", N_("Import…"), self._import),
            ("export", N_("Export…"), self._export),
            (None, None, None),
            ("open_folder", N_("Open Palettes Folder"), self._open_folder),
        ):
            if key is None:
                buttons.addSpacing(8)
                continue
            button = QPushButton(_(label))
            button.clicked.connect(lambda checked=False, run=slot: run())
            buttons.addWidget(button)
            self._buttons[key] = button
        buttons.addStretch(1)
        top = QHBoxLayout()
        top.addWidget(self._list, 1)
        top.addLayout(buttons)
        layout.addLayout(top, 3)

        self._preview_title = QLabel()
        layout.addWidget(self._preview_title)
        self._preview = SwatchGrid()
        self._preview.menu_requested.connect(self._swatch_menu)
        holder = QWidget()
        holder_layout = QGridLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.addWidget(self._preview, 0, 0, Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea()
        scroll.setWidget(holder)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll, 2)
        self.refresh()

    # --- state ---------------------------------------------------------------------------------------

    def _palettes(self) -> tuple[Palette, ...]:
        return self._session.state.colours.palettes

    def selected_ids(self) -> list[int]:
        return [item.data(_ID) for item in self._list.selectedItems()]

    def _selected(self) -> list[Palette]:
        ids = set(self.selected_ids())
        return [palette for palette in self._palettes() if palette.id in ids]

    def refresh(self, select: list[int] | None = None) -> None:
        """Rebuilds the list from the session, keeping (or setting) the selection by id."""
        keep = set(select if select is not None else self.selected_ids())
        self._list.blockSignals(True)
        self._list.clear()
        for palette in self._palettes():
            count = len(palette.swatches)
            text = ngettext("{name} ({count} colour)", "{name} ({count} colours)", count).format(
                name=palette.name, count=count
            )
            item = QListWidgetItem(text, self._list)
            item.setData(_ID, palette.id)
            item.setSelected(palette.id in keep)
        self._list.blockSignals(False)
        self._on_selection()

    def _on_selection(self) -> None:
        chosen = self._selected()
        one, some = len(chosen) == 1, bool(chosen)
        for key, enabled in (("rename", one), ("duplicate", one), ("delete", some), ("export", some)):
            self._buttons[key].setEnabled(enabled)
        if one:
            palette = chosen[0]
            self._preview_title.setText(
                ngettext("{name}: {count} colour", "{name}: {count} colours", len(palette.swatches)).format(
                    name=palette.name, count=len(palette.swatches)
                )
            )
            self._preview.set_cells(
                tuple(
                    Cell(s.id, s.color, s.opacity, swatch_tooltip(s.name, s.color, s.opacity)) for s in palette.swatches
                )
            )
        else:
            self._preview_title.setText(_("Select a palette to see its colours.") if not some else "")
            self._preview.set_cells(())

    # --- actions -------------------------------------------------------------------------------------

    def _ask_name(self, title: str, name: str = "") -> str | None:
        text, accepted = QInputDialog.getText(self, title, _("Name:"), text=name)
        return text if accepted else None

    def _new(self) -> None:
        name = self._ask_name(_("New Palette"))
        if name is not None:
            self.refresh([palettes.new_palette(self._session, name)])

    def _rename(self) -> None:
        chosen = self._selected()
        if len(chosen) != 1:
            return
        name = self._ask_name(_("Rename Palette"), chosen[0].name)
        if name is not None and not palettes.rename_palette(self._session, chosen[0].id, name):
            QMessageBox.warning(self, _("Rename Palette"), _("Another palette already has that name, or it is empty."))
        self.refresh()

    def _duplicate(self) -> None:
        chosen = self._selected()
        if len(chosen) == 1:
            copy = palettes.duplicate_palette(self._session, chosen[0].id)
            self.refresh([copy] if copy is not None else None)

    def _delete(self) -> None:
        chosen = self._selected()
        if not chosen or not self.confirm_delete(chosen):
            return
        palettes.delete_palettes(self._session, [palette.id for palette in chosen])
        self.refresh([])

    def confirm_delete(self, chosen: list[Palette]) -> bool:
        names = "\n".join(palette.name for palette in chosen[:_LISTED])
        if len(chosen) > _LISTED:
            names += "\n" + _("… and {count} more").format(count=len(chosen) - _LISTED)
        question = ngettext(
            "Delete this palette? Its file is removed too.",
            "Delete these {count} palettes? Their files are removed too.",
            len(chosen),
        ).format(count=len(chosen))
        answer = QMessageBox.question(self, _("Delete Palettes"), f"{question}\n\n{names}")
        return answer == QMessageBox.StandardButton.Yes

    def _import(self) -> None:
        paths = palette_import.ask_paths(self)
        if paths:
            before = {palette.id for palette in self._palettes()}
            palette_import.import_palettes(self, self._session, paths)
            self.refresh([palette.id for palette in self._palettes() if palette.id not in before])

    def _export(self) -> None:
        chosen = self._selected()
        if len(chosen) == 1:
            palette_export.export_one(self, chosen[0])
        elif chosen:
            palette_export.export_many(self, chosen)

    def _open_folder(self) -> None:
        folder = self._context.palettes_folder
        if folder is not None:
            folder.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _swatch_menu(self, key: object, position: QPoint) -> None:
        menu = self.swatch_menu(key)
        if menu is not None:
            menu.exec(position)
            self.refresh()

    def swatch_menu(self, key: object) -> QMenu | None:
        """Rename, move or delete a swatch of the previewed palette; None when there is nothing to act on."""
        chosen = self._selected()
        if len(chosen) != 1 or key is None:
            return None
        palette_id = chosen[0].id
        swatch = next((s for s in chosen[0].swatches if s.id == key), None)
        if swatch is None:
            return None
        session = self._session

        def rename() -> None:
            name = self._ask_name(_("Rename Swatch"), swatch.name)
            if name is not None:
                swatches.rename_swatch(session, "library", swatch.id, name, palette_id)

        menu = QMenu(self)
        menu.addAction(_("Rename…"), rename)
        menu.addAction(_("Move Left"), lambda: swatches.move_swatch(session, "library", swatch.id, -1, palette_id))
        menu.addAction(_("Move Right"), lambda: swatches.move_swatch(session, "library", swatch.id, 1, palette_id))
        menu.addSeparator()
        menu.addAction(_("Delete"), lambda: swatches.delete_swatch(session, "library", swatch.id, palette_id))
        return menu
