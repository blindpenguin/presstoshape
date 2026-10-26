"""The Colour panel: fill/stroke pair, picker, numbers, hex and alpha, recent colours, document swatches and the
personal library. It edits the active paint of whatever queries.colour_target names."""

from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from presstoshape import icons
from presstoshape.editing import queries
from presstoshape.editing.operations import colours, palettes, swatches
from presstoshape.editing.operations.swatches import SwatchSet
from presstoshape.editing.session import Session
from presstoshape.geometry.colours import HSV, hex_to_rgb, hsv_for, hsv_to_hex, parse_hex_input
from presstoshape.i18n import N_, _
from presstoshape.models.app_state import AppState
from presstoshape.models.colours import Palette, Swatch
from presstoshape.models.shapes import LinearGradient, RadialGradient, Style, flat_color
from presstoshape.views import palette_export, palette_import
from presstoshape.views.actions import AppActions
from presstoshape.views.colour_picker import ColourPicker
from presstoshape.views.icon_engine import icon
from presstoshape.views.paint_pair import PaintPair
from presstoshape.views.swatch_grid import Cell, SwatchGrid, swatch_tooltip

_ICON_SIZE = QSize(18, 18)
# Number field ranges and labels per mode.
_NUMBERS = {
    "hsv": ((N_("H"), 360), (N_("S"), 100), (N_("V"), 100)),
    "rgb": ((N_("R"), 255), (N_("G"), 255), (N_("B"), 255)),
}


def _keyword(text: str) -> str | None:
    """SVG/CSS colour names ("teal") through Qt, which knows the same list."""
    return QColor(text).name() if QColor.isValidColorName(text) and not text.startswith("#") else None


def _scrolled(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidget(widget)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return scroll


class ColourPanel(QWidget):
    """The fill/stroke pair above three tabs: Colour (picker, numbers, recent colours), Document and Library
    swatches, which scroll inside their tab however many there are.

    Edits go through operations; while the picker or alpha slider is dragged with shapes selected, the panel
    only emits `preview_changed(style changes)` for the canvas and commits one edit on release (None ends it)."""

    preview_changed = Signal(object)
    # "Manage Palettes…": the window opens Settings on the Palettes page.
    manage_palettes = Signal()

    def __init__(self, session: Session, actions: AppActions) -> None:
        super().__init__()
        self._session = session
        self._hsv: HSV = (0.0, 0.0, 0.0)
        self._alpha = 1.0
        self._previewing = False
        self._shown: tuple | None = None
        self._listed_palettes: tuple | None = None

        top = QHBoxLayout()
        top.setContentsMargins(4, 4, 4, 0)
        self._pair = PaintPair()
        self._pair.activated.connect(lambda slot: colours.set_active_paint(session, slot))
        top.addWidget(self._pair)
        for command_id in ("colour.swap", "colour.none", "colour.default"):
            button = QToolButton()
            button.setDefaultAction(actions[command_id])
            button.setIconSize(_ICON_SIZE)
            button.setAutoRaise(True)
            top.addWidget(button, 0, Qt.AlignmentFlag.AlignBottom)
        top.addStretch(1)

        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._colour_page = self._picker_page(session)
        self._tabs.addTab(_scrolled(self._colour_page), _("Colour"))
        self._grids: dict[SwatchSet, SwatchGrid] = {}
        for palette, title in (("document", _("Document")), ("library", _("Library"))):
            self._tabs.addTab(self._swatch_page(palette), title)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)
        outer.addLayout(top)
        outer.addWidget(self._tabs, 1)

    def _picker_page(self, session: Session) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        self._picker = ColourPicker()
        self._picker.dragged.connect(self._on_dragged)
        self._picker.released.connect(self._on_released)
        layout.addWidget(self._picker)
        self._gradient_note = QLabel(_("Gradient: picking a colour replaces it"))
        self._gradient_note.setWordWrap(True)
        self._gradient_note.setEnabled(False)
        layout.addWidget(self._gradient_note)

        numbers = QHBoxLayout()
        numbers.setSpacing(2)
        self._mode = QToolButton()
        self._mode.setAutoRaise(True)
        self._mode.setToolTip(_("Switch between HSV and RGB numbers"))
        self._mode.clicked.connect(lambda: self._toggle_mode())
        numbers.addWidget(self._mode)
        self._numbers: list[QSpinBox] = []
        for _index in range(3):
            box = QSpinBox()
            box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            box.setAlignment(Qt.AlignmentFlag.AlignRight)
            box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            box.valueChanged.connect(lambda value: self._on_numbers())
            box.editingFinished.connect(self._on_field_finished)
            numbers.addWidget(box, 1)
            self._numbers.append(box)
        layout.addLayout(numbers)

        hex_row = QHBoxLayout()
        hex_row.addWidget(QLabel(_("Hex")))
        self._hex = QLineEdit()
        self._hex.setPlaceholderText(_("None"))
        self._hex.setToolTip(_("#rrggbb, #rgb or a colour name"))
        self._hex.editingFinished.connect(self._on_hex)
        hex_row.addWidget(self._hex, 1)
        layout.addLayout(hex_row)

        alpha_row = QHBoxLayout()
        alpha_row.addWidget(QLabel(_("Alpha")))
        self._alpha_slider = QSlider(Qt.Orientation.Horizontal)
        self._alpha_slider.setRange(0, 100)
        self._alpha_slider.valueChanged.connect(self._on_alpha_slider)
        self._alpha_slider.sliderReleased.connect(self._on_alpha_released)
        alpha_row.addWidget(self._alpha_slider, 1)
        self._alpha_box = QSpinBox()
        self._alpha_box.setRange(0, 100)
        self._alpha_box.setSuffix(" %")
        self._alpha_box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._alpha_box.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._alpha_box.valueChanged.connect(lambda value: self._apply_alpha(value / 100))
        self._alpha_box.editingFinished.connect(session.end_merge)
        alpha_row.addWidget(self._alpha_box)
        layout.addLayout(alpha_row)

        recent_label = QLabel(_("Recent"))
        recent_label.setEnabled(False)
        layout.addWidget(recent_label)
        self._recent = SwatchGrid()
        self._recent.picked.connect(lambda color: colours.apply_colour(session, color))
        self._recent.menu_requested.connect(self._recent_menu)
        layout.addWidget(self._recent)
        layout.addStretch(1)
        return page

    def _swatch_page(self, palette: SwatchSet) -> QWidget:
        """The palette's grid, scrolling inside the tab, with its menu (add, import, export, …) above it."""
        grid = SwatchGrid(_("Add the current colour"))
        grid.picked.connect(lambda swatch_id: self._apply_swatch(palette, swatch_id))
        grid.add_requested.connect(lambda: self._add_current(palette))
        grid.menu_requested.connect(lambda key, position: self._swatch_menu(palette, key, position))
        self._grids[palette] = grid

        menu_button = QToolButton()
        menu_button.setIcon(icon(icons.SWATCH_MENU))
        menu_button.setIconSize(_ICON_SIZE)
        menu_button.setAutoRaise(True)
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu_button.setMenu(self._palette_menu(palette))
        menu_button.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        menu_button.setToolTip(_("Palette actions"))
        header = QHBoxLayout()
        header.setContentsMargins(4, 0, 0, 0)
        if palette == "library":
            self._palette_box = QComboBox()
            self._palette_box.setToolTip(_("Palette shown here"))
            self._palette_box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self._palette_box.setMinimumContentsLength(8)
            self._palette_box.activated.connect(
                lambda index: palettes.set_current_palette(self._session, self._palette_box.itemData(index))
            )
            header.addWidget(self._palette_box, 1)
        else:
            hint = QLabel(_("Click to apply, right-click for more"))
            hint.setEnabled(False)
            header.addWidget(hint, 1)
        header.addWidget(menu_button)

        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(4, 0, 4, 4)
        holder_layout.addWidget(grid)
        holder_layout.addStretch(1)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 2, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(header)
        if palette == "library":
            self._library_stack = QStackedWidget()
            self._library_stack.addWidget(_scrolled(holder))
            self._library_stack.addWidget(self._no_palettes())
            layout.addWidget(self._library_stack, 1)
        else:
            layout.addWidget(_scrolled(holder), 1)
        return page

    def _no_palettes(self) -> QWidget:
        """What the Library tab shows before there is any palette."""
        page = QWidget()
        layout = QVBoxLayout(page)
        note = QLabel(_("No palettes yet. Make one, or import palette files (Lospec downloads, GIMP palettes, …)."))
        note.setWordWrap(True)
        note.setEnabled(False)
        layout.addWidget(note)
        for text, slot in (
            (_("New Palette…"), self._new_palette),
            (_("Import Palettes…"), lambda: self._import("library")),
        ):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, run=slot: run())
            layout.addWidget(button)
        layout.addStretch(1)
        return page

    def sizeHint(self) -> QSize:
        # Scroll areas alone ask for little; the dock layout splits the height by these hints, so ask for room
        # to show the Colour tab without scrolling.
        hint = super().sizeHint()
        return QSize(
            hint.width(),
            self._pair.height() + self._tabs.tabBar().sizeHint().height() + self._colour_page.sizeHint().height() + 16,
        )

    # --- refresh ------------------------------------------------------------------------------------

    def refresh(self, state: AppState) -> None:
        target = queries.colour_target(state)
        enabled = target != "disabled"
        style = colours.target_style(state) if enabled else Style()
        fill = colours.target_paint(state, "fill") if enabled else None
        stroke = colours.target_paint(state, "stroke") if enabled else None
        slot = state.colours.active
        shown = (enabled, style, fill, stroke, slot, state.colours.numbers)
        if shown != self._shown:
            self._shown = shown
            self._show_target(enabled, style, fill, stroke, slot, state.colours.numbers)
        self._recent.set_cells(tuple(Cell(color, color, 1.0, color) for color in state.colours.recent))
        self._grids["document"].set_cells(self._swatch_cells(state.document.swatches))
        self._refresh_palettes(state)
        self._grids["library"].set_cells(self._swatch_cells(swatches.palette_swatches(self._session, "library")))

    def _refresh_palettes(self, state: AppState) -> None:
        listed = tuple((palette.id, palette.name) for palette in state.colours.palettes)
        if listed != self._listed_palettes:
            self._listed_palettes = listed
            self._palette_box.blockSignals(True)
            self._palette_box.clear()
            for palette_id, name in listed:
                self._palette_box.addItem(name, palette_id)
            self._palette_box.blockSignals(False)
        index = self._palette_box.findData(state.colours.current_palette)
        if index != self._palette_box.currentIndex():
            self._palette_box.blockSignals(True)
            self._palette_box.setCurrentIndex(index)
            self._palette_box.blockSignals(False)
        self._palette_box.setEnabled(bool(listed))
        self._library_stack.setCurrentIndex(0 if listed else 1)

    @staticmethod
    def _swatch_cells(items: tuple[Swatch, ...]) -> tuple[Cell, ...]:
        return tuple(Cell(s.id, s.color, s.opacity, swatch_tooltip(s.name, s.color, s.opacity)) for s in items)

    def _show_target(self, enabled, style: Style, fill, stroke, slot, mode) -> None:
        mixed = colours.MIXED
        self._pair.show_paints(
            None if fill is mixed else fill,
            style.fill_opacity,
            fill is mixed,
            None if stroke is mixed else stroke,
            style.stroke_opacity,
            stroke is mixed,
            slot,
        )
        paint = fill if slot == "fill" else stroke
        if paint is mixed:
            paint = getattr(style, slot)
        color = flat_color(paint)
        self._alpha = getattr(style, f"{slot}_opacity")
        if color is not None and color != hsv_to_hex(self._hsv) and not self._previewing:
            self._hsv = hsv_for(color, self._hsv)
            self._picker.set_hsv(self._hsv)
        self._gradient_note.setVisible(isinstance(paint, (LinearGradient, RadialGradient)))
        for widget in (self._picker, self._hex, self._alpha_slider, self._alpha_box, *self._numbers):
            widget.setEnabled(enabled)
        self._show_numbers(mode)
        self._show_hex(color)
        self._show_alpha()

    def _show_numbers(self, mode: str) -> None:
        self._mode.setText(mode.upper())
        if mode == "hsv":
            h, s, v = self._hsv
            values = (round(h) % 360, round(s * 100), round(v * 100))
        else:
            values = hex_to_rgb(hsv_to_hex(self._hsv))
        for box, (label, maximum), value in zip(self._numbers, _NUMBERS[mode], values):
            box.blockSignals(True)
            box.setPrefix(f"{_(label)} ")
            box.setRange(0, maximum)
            box.setValue(value)
            box.blockSignals(False)

    def _show_hex(self, color: str | None) -> None:
        if not self._hex.hasFocus():
            self._hex.setText(color or "")

    def _show_alpha(self) -> None:
        percent = round(self._alpha * 100)
        for widget in (self._alpha_slider, self._alpha_box):
            if widget.value() != percent and not (widget is self._alpha_slider and widget.isSliderDown()):
                widget.blockSignals(True)
                widget.setValue(percent)
                widget.blockSignals(False)

    def _mode_now(self) -> str:
        return self._session.state.colours.numbers

    # --- editing ------------------------------------------------------------------------------------

    def _slot(self) -> str:
        return self._session.state.colours.active

    def _selection_target(self) -> bool:
        return queries.colour_target(self._session.state) == "selection"

    def _on_dragged(self, hsv: HSV) -> None:
        self._hsv = hsv
        color = hsv_to_hex(hsv)
        self._show_numbers(self._mode_now())
        self._show_hex(color)
        if self._selection_target():
            self._previewing = True
            self.preview_changed.emit({self._slot(): color})
        else:
            colours.apply_colour(self._session, color, merge_key=f"colour.{self._slot()}")

    def _on_released(self, hsv: HSV) -> None:
        self._hsv = hsv
        self._end_preview()
        colours.apply_colour(self._session, hsv_to_hex(hsv))
        self._session.end_merge()

    def _end_preview(self) -> None:
        if self._previewing:
            self._previewing = False
            self.preview_changed.emit(None)

    def _on_numbers(self) -> None:
        values = [box.value() for box in self._numbers]
        if self._mode_now() == "hsv":
            self._hsv = (float(values[0]), values[1] / 100, values[2] / 100)
        else:
            color = "#{:02x}{:02x}{:02x}".format(*values)
            self._hsv = hsv_for(color, self._hsv)
        self._picker.set_hsv(self._hsv)
        colours.apply_colour(self._session, hsv_to_hex(self._hsv), merge_key=f"colour.{self._slot()}.numbers")

    def _on_field_finished(self) -> None:
        self._session.end_merge()
        colours.remember_colour(self._session, hsv_to_hex(self._hsv))

    def _on_hex(self) -> None:
        color = parse_hex_input(self._hex.text(), _keyword)
        current = hsv_to_hex(self._hsv)
        if color is None:
            self._hex.setText(current if self._hex.text() else "")
            return
        if color != current or flat_color(getattr(colours.target_style(self._session.state), self._slot())) != color:
            self._hsv = hsv_for(color, self._hsv)
            self._picker.set_hsv(self._hsv)
            colours.apply_colour(self._session, color)

    def _on_alpha_slider(self, percent: int) -> None:
        self._alpha_box.blockSignals(True)
        self._alpha_box.setValue(percent)
        self._alpha_box.blockSignals(False)
        if self._alpha_slider.isSliderDown() and self._selection_target():
            self._previewing = True
            self.preview_changed.emit({f"{self._slot()}_opacity": percent / 100})
        else:
            self._apply_alpha(percent / 100)

    def _on_alpha_released(self) -> None:
        self._end_preview()
        self._apply_alpha(self._alpha_slider.value() / 100)
        self._session.end_merge()

    def _apply_alpha(self, alpha: float) -> None:
        self._alpha = alpha
        colours.apply_opacity(self._session, alpha, merge_key=f"colour.{self._slot()}.alpha")

    def _toggle_mode(self) -> None:
        colours.set_number_mode(self._session, "rgb" if self._mode_now() == "hsv" else "hsv")

    # --- swatches -----------------------------------------------------------------------------------

    def _find(self, palette: SwatchSet, swatch_id: object) -> Swatch | None:
        return next((s for s in swatches.palette_swatches(self._session, palette) if s.id == swatch_id), None)

    def _apply_swatch(self, palette: SwatchSet, swatch_id: object) -> None:
        swatch = self._find(palette, swatch_id)
        if swatch is not None:
            colours.apply_colour(self._session, swatch.color, swatch.opacity)

    def _add_current(self, palette: SwatchSet) -> None:
        swatches.add_swatch(self._session, palette, hsv_to_hex(self._hsv), self._alpha)

    def _recent_menu(self, key: object, position: QPoint) -> None:
        menu = QMenu(self)
        clear = menu.addAction(_("Clear Recent Colours"))
        clear.setEnabled(bool(self._session.state.colours.recent))
        clear.triggered.connect(lambda: colours.clear_recent_colours(self._session))
        menu.exec(position)

    def _swatch_menu(self, palette: SwatchSet, key: object, position: QPoint) -> None:
        session = self._session
        swatch = self._find(palette, key)
        menu = QMenu(self)
        if swatch is None:
            menu.addAction(_("Add Current Colour"), lambda: self._add_current(palette))
            menu.exec(position)
            return
        menu.addAction(_("Rename…"), lambda: self._rename(palette, swatch))
        menu.addAction(
            _("Replace with Current Colour"),
            lambda: swatches.replace_swatch(session, palette, swatch.id, hsv_to_hex(self._hsv), self._alpha),
        )
        menu.addAction(_("Move Left"), lambda: swatches.move_swatch(session, palette, swatch.id, -1))
        menu.addAction(_("Move Right"), lambda: swatches.move_swatch(session, palette, swatch.id, 1))
        other = _("Add to Library") if palette == "document" else _("Add to Document")
        menu.addAction(other, lambda: swatches.copy_swatch(session, palette, swatch.id))
        menu.addSeparator()
        menu.addAction(_("Delete"), lambda: swatches.delete_swatch(session, palette, swatch.id))
        menu.exec(position)

    def _rename(self, palette: SwatchSet, swatch: Swatch) -> None:
        name, accepted = QInputDialog.getText(self, _("Rename Swatch"), _("Name:"), text=swatch.name)
        if accepted:
            swatches.rename_swatch(self._session, palette, swatch.id, name)

    def _palette_menu(self, palette: SwatchSet) -> QMenu:
        session = self._session
        menu = QMenu(self)
        if palette == "library":
            menu.addAction(_("New Palette…"), self._new_palette)
            rename = menu.addAction(_("Rename Palette…"), self._rename_palette)
            menu.addSeparator()
        menu.addAction(_("Add Current Colour"), lambda: self._add_current(palette))
        if palette == "document":
            menu.addAction(_("Add Colours Used in Document"), lambda: swatches.add_document_colours(session))
        menu.addSeparator()
        menu.addAction(
            _("Import Palettes…") if palette == "library" else _("Import Palette…"), lambda: self._import(palette)
        )
        export = menu.addAction(_("Export Palette…"), lambda: self._export(palette))
        menu.addSeparator()
        clear = menu.addAction(_("Delete All Swatches"), lambda: swatches.delete_all_swatches(session, palette))
        if palette == "library":
            menu.addSeparator()
            menu.addAction(_("Manage Palettes…"), lambda: self.manage_palettes.emit())

            def update() -> None:
                exists = palettes.current_palette(session.state) is not None
                for action in (rename, export, clear):
                    action.setEnabled(exists)

            menu.aboutToShow.connect(update)
        return menu

    def _new_palette(self) -> None:
        name, accepted = QInputDialog.getText(self, _("New Palette"), _("Name:"))
        if accepted:
            palettes.new_palette(self._session, name)

    def _rename_palette(self) -> None:
        current = palettes.current_palette(self._session.state)
        if current is None:
            return
        name, accepted = QInputDialog.getText(self, _("Rename Palette"), _("Name:"), text=current.name)
        if accepted and not palettes.rename_palette(self._session, current.id, name):
            QMessageBox.warning(self, _("Rename Palette"), _("Another palette already has that name, or it is empty."))

    def _import(self, palette: SwatchSet) -> None:
        if palette == "library":
            paths = palette_import.ask_paths(self)
            if paths:
                palette_import.import_palettes(self, self._session, paths)
            return
        path, _chosen = QFileDialog.getOpenFileName(self, _("Import Palette"), "", palette_import.open_filter())
        if not path:
            return
        try:
            _name, colors = palette_import.read_file(Path(path))
        except (OSError, ValueError):
            QMessageBox.warning(
                self,
                _("Import Palette"),
                _("{name} is not a palette file PressToShape can read.").format(name=Path(path).name),
            )
            return
        swatches.import_swatches(self._session, palette, colors)

    def _export(self, palette: SwatchSet) -> None:
        if palette == "library":
            stored = palettes.current_palette(self._session.state)
        else:
            stored = Palette(0, _("Document swatches"), self._session.state.document.swatches)
        if stored is not None:
            palette_export.export_one(self, stored)
