"""Shortcuts, icons and menu/toolbar layouts per command id. Presentation only; operations live in
presstoshape.editing.

Ids come from three places: registered operations (`presstoshape.editing.registry`), tools
(`presstoshape.tools.registry`) and window commands (dialogs and viewport, `WINDOW_COMMANDS`, implemented by
MainWindow).
"""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QKeySequence

from presstoshape import icons
from presstoshape.i18n import N_
from presstoshape.tools.registry import TOOLS

Keys = QKeySequence.StandardKey
# A tuple binds several shortcuts; standard keys expand to the platform's bindings when the action is built.
Shortcut = str | Keys | tuple[str | Keys, ...]


@dataclass(frozen=True)
class Binding:
    shortcut: Shortcut | None = None
    icon: Path | None = None


# Commands that need a dialog or the viewport; MainWindow maps each id to a method.
WINDOW_COMMANDS = {
    "file.new": N_("&New"),
    "file.open": N_("&Open…"),
    "file.save": N_("&Save"),
    "file.save_as": N_("Save &As…"),
    "file.place_image": N_("&Place Image…"),
    "file.place_reference": N_("Place as Re&ference…"),
    "file.export_png": N_("&Export PNG…"),
    "file.quit": N_("&Quit"),
    "edit.cut": N_("Cu&t"),
    "edit.copy": N_("&Copy"),
    "edit.paste": N_("&Paste"),
    "edit.paste_in_place": N_("Paste &in Place"),
    "view.zoom_fit": N_("Zoom to &Fit"),
    "edit.settings": N_("&Settings…"),
    "image.replace": N_("Re&place Image…"),
    "view.grid_settings": N_("Grid Se&ttings…"),
    "help.about": N_("&About PressToShape"),
}

KEYMAP: dict[str, Binding] = {
    "file.new": Binding(Keys.New, icons.NEW),
    "file.open": Binding(Keys.Open, icons.OPEN),
    "file.save": Binding(Keys.Save, icons.SAVE),
    "file.save_as": Binding(Keys.SaveAs),
    "file.place_image": Binding(icon=icons.IMAGE_PLACE),
    "image.replace": Binding(icon=icons.IMAGE_REPLACE),
    "view.show_references": Binding(icon=icons.IMAGE_REFERENCES_HIDDEN),
    "file.export_png": Binding("Ctrl+Shift+E"),
    "file.quit": Binding(Keys.Quit),
    "edit.undo": Binding(Keys.Undo, icons.UNDO),
    "edit.redo": Binding((Keys.Redo, "Ctrl+Y"), icons.REDO),
    "edit.cut": Binding(Keys.Cut),
    "edit.copy": Binding(Keys.Copy),
    "edit.paste": Binding(Keys.Paste),
    # Inkscape's Ctrl+Alt+V is Divide here, so Illustrator's binding.
    "edit.paste_in_place": Binding("Ctrl+Shift+V"),
    "edit.duplicate": Binding("Ctrl+D"),
    "edit.settings": Binding(icon=icons.SETTINGS),
    "edit.select_all": Binding(Keys.SelectAll),
    # Not Keys.Delete: on KDE that also expands to Ctrl+D, which is Duplicate.
    "edit.delete": Binding("Del", icons.DELETE),
    # Inkscape's shortcuts plus Ctrl+Alt+letter, which works on every keyboard layout (^ is a dead key on
    # German/French layouts, so Exclude leads with Ctrl+Alt+X).
    "path.union": Binding(("Ctrl++", "Ctrl+Alt+U"), icons.UNION),
    "path.difference": Binding(("Ctrl+-", "Ctrl+Alt+D"), icons.DIFFERENCE),
    "path.intersection": Binding(("Ctrl+*", "Ctrl+Alt+I"), icons.INTERSECTION),
    "path.exclude": Binding(("Ctrl+Alt+X", "Ctrl+^"), icons.EXCLUDE),
    "path.divide": Binding(("Ctrl+/", "Ctrl+Alt+V"), icons.DIVIDE),
    "path.object_to_path": Binding("Ctrl+Shift+C"),
    "path.node_corner": Binding(icon=icons.NODE_CORNER),
    "path.node_smooth": Binding(icon=icons.NODE_SMOOTH),
    "path.node_symmetric": Binding(icon=icons.NODE_SYMMETRIC),
    "path.make_line": Binding(icon=icons.MAKE_LINE),
    "path.make_curve": Binding(icon=icons.MAKE_CURVE),
    "path.break_nodes": Binding(icon=icons.BREAK_NODES),
    "path.join_nodes": Binding(icon=icons.JOIN_NODES),
    "path.join_segment": Binding(icon=icons.JOIN_SEGMENT),
    "path.delete_segment": Binding(icon=icons.DELETE_SEGMENT),
    "path.close": Binding(icon=icons.PATH_CLOSE),
    "path.open": Binding(icon=icons.PATH_OPEN),
    "path.reverse": Binding(icon=icons.PATH_REVERSE),
    "path.combine": Binding(icon=icons.PATH_COMBINE),
    "path.split": Binding(icon=icons.PATH_SPLIT),
    "view.zoom_in": Binding(("+", "="), icons.ZOOM_IN),
    "view.zoom_out": Binding("-", icons.ZOOM_OUT),
    "view.zoom_fit": Binding("5", icons.ZOOM_FIT),
    "view.zoom_actual": Binding("1"),
    # Inkscape's keys for the frequent precision toggles; Illustrator's Ctrl+R for rulers.
    "view.show_rulers": Binding("Ctrl+R"),
    "view.show_grid": Binding("#"),
    "view.show_guides": Binding("|"),
    "view.snapping": Binding("%", icons.SNAPPING),
    "object.align_left": Binding(icon=icons.OBJECT_ALIGN_LEFT),
    "object.align_hcenter": Binding(icon=icons.OBJECT_ALIGN_HCENTER),
    "object.align_right": Binding(icon=icons.OBJECT_ALIGN_RIGHT),
    "object.align_top": Binding(icon=icons.OBJECT_ALIGN_TOP),
    "object.align_vcenter": Binding(icon=icons.OBJECT_ALIGN_VCENTER),
    "object.align_bottom": Binding(icon=icons.OBJECT_ALIGN_BOTTOM),
    "object.distribute_x": Binding(icon=icons.DISTRIBUTE_X),
    "object.distribute_y": Binding(icon=icons.DISTRIBUTE_Y),
    "object.distribute_centers_x": Binding(icon=icons.DISTRIBUTE_CENTERS_X),
    "object.distribute_centers_y": Binding(icon=icons.DISTRIBUTE_CENTERS_Y),
    "path.make_composite": Binding("Ctrl+Alt+C"),
    "object.group": Binding("Ctrl+G"),
    "object.ungroup": Binding("Ctrl+Shift+G"),
    "object.hide": Binding("Ctrl+3", icons.HIDDEN),
    "object.show_all": Binding("Ctrl+Alt+3"),
    "object.lock": Binding("Ctrl+2", icons.LOCKED),
    "object.unlock_all": Binding("Ctrl+Alt+2"),
    # Figma's bindings; Inkscape's plain H / V would clash with the Select tool's V.
    "object.flip_horizontal": Binding("Shift+H"),
    "object.flip_vertical": Binding("Shift+V"),
    "object.raise": Binding("PgUp"),
    "object.lower": Binding("PgDown"),
    "object.raise_to_top": Binding("Home"),
    "object.lower_to_bottom": Binding("End"),
    "tool.select": Binding("V", icons.TOOL_SELECT),
    "tool.node": Binding("N", icons.TOOL_NODE),
    "tool.pen": Binding("P", icons.TOOL_PEN),
    "tool.pencil": Binding("F", icons.TOOL_PENCIL),
    "tool.rectangle": Binding("R", icons.TOOL_RECTANGLE),
    "tool.ellipse": Binding("E", icons.TOOL_ELLIPSE),
    "tool.text": Binding("T", icons.TOOL_TEXT),
}

TOOL_IDS = [entry.id for entry in TOOLS]
BOOLEAN_IDS = ["path.union", "path.difference", "path.intersection", "path.exclude", "path.divide"]

COMPOSITE_IDS: list[str | None | tuple[str, list[str]]] = [
    "path.make_composite",
    (N_("Make Composite &As"), [f"path.make_composite_{mode}" for mode in ("add", "subtract", "intersect", "exclude")]),
    "path.release_composite",
    "path.flatten_composite",
]
NODE_TYPE_IDS = ["path.node_corner", "path.node_smooth", "path.node_symmetric", "path.make_line", "path.make_curve"]
NODE_STRUCTURE_IDS = ["path.break_nodes", "path.join_nodes", "path.join_segment", "path.delete_segment"]
SUBPATH_IDS = ["path.close", "path.open", "path.reverse"]
CLIP_IDS = ["object.clip.make", "object.clip.release"]
MASK_IDS: list[str | None | tuple[str, list[str]]] = [
    "object.mask.make",
    "object.mask.release",
    None,
    "object.mask.invert",
    "object.mask.type_luminance",
    "object.mask.type_alpha",
]
IMAGE_IDS: list[str | None] = [
    "image.reset_size",
    "image.fit_page",
    "image.replace",
    None,
    "image.make_reference",
    "image.make_artwork",
]
ARRANGE_IDS = ["object.raise_to_top", "object.raise", "object.lower", "object.lower_to_bottom"]
ALIGN_IDS = [
    "object.align_left",
    "object.align_hcenter",
    "object.align_right",
    "object.align_top",
    "object.align_vcenter",
    "object.align_bottom",
]
DISTRIBUTE_IDS = [
    "object.distribute_x",
    "object.distribute_y",
    "object.distribute_centers_x",
    "object.distribute_centers_y",
]
SNAP_TARGET_IDS = ["view.snap_grid", "view.snap_guides", "view.snap_artboard", "view.snap_objects", "view.snap_nodes"]

# The File menu's recent files submenu; menu_bar_view creates it here and MainWindow fills it when it opens.
RECENT_MENU = "file.open_recent"
RECENT_MENU_TITLE = N_("Open &Recent")

# None is a separator; a (title, ids) tuple is a submenu.
MENUS: list[tuple[str, list[str | None | tuple[str, list[str]]]]] = [
    (
        N_("&File"),
        [
            "file.new",
            "file.open",
            RECENT_MENU,
            "file.save",
            "file.save_as",
            None,
            "file.place_image",
            "file.place_reference",
            None,
            "file.export_png",
            None,
            "file.quit",
        ],
    ),
    (
        N_("&Edit"),
        [
            "edit.undo",
            "edit.redo",
            None,
            "edit.cut",
            "edit.copy",
            "edit.paste",
            "edit.paste_in_place",
            "edit.duplicate",
            "edit.delete",
            None,
            "edit.select_all",
            None,
            "edit.settings",
        ],
    ),  # fmt: skip
    (
        N_("&Path"),
        [
            *BOOLEAN_IDS,
            None,
            *COMPOSITE_IDS,
            None,
            "path.combine",
            "path.split",
            None,
            *SUBPATH_IDS,
            (N_("Selected &Nodes"), [*NODE_TYPE_IDS, None, *NODE_STRUCTURE_IDS]),
            None,
            "path.object_to_path",
        ],
    ),
    (
        N_("&Object"),
        [
            "object.group",
            "object.ungroup",
            None,
            (N_("&Clipping Mask"), CLIP_IDS),
            (N_("Opacity &Mask"), MASK_IDS),
            "object.mask.to_mask",
            "object.mask.to_content",
            None,
            (N_("&Picture"), IMAGE_IDS),
            None,
            "object.hide",
            "object.show_all",
            "object.lock",
            "object.unlock_all",
            None,
            "object.flip_horizontal",
            "object.flip_vertical",
            None,
            (N_("&Align"), ALIGN_IDS),
            (N_("&Distribute"), DISTRIBUTE_IDS),
            None,
            *ARRANGE_IDS,
        ],
    ),  # fmt: skip
    (
        N_("&View"),
        [
            "view.zoom_in",
            "view.zoom_out",
            "view.zoom_fit",
            "view.zoom_actual",
            None,
            "view.show_rulers",
            "view.show_grid",
            "view.show_guides",
            "view.lock_guides",
            "view.clear_guides",
            "view.grid_settings",
            "view.show_references",
            None,
            "view.snapping",
            (N_("S&nap To"), SNAP_TARGET_IDS),
        ],
    ),  # fmt: skip
    (N_("&Tools"), TOOL_IDS),
    (N_("&Help"), ["help.about"]),
]

# The zoom percentage label sits between zoom out and zoom in; toolbar_view inserts it at this marker.
ZOOM_LABEL = "view.zoom_label"
MAIN_TOOLBAR: list[str | None] = [
    "file.new", "file.open", "file.save", None,
    "edit.undo", "edit.redo", None,
    "view.zoom_out", ZOOM_LABEL, "view.zoom_in", "view.zoom_fit", None,
    "view.snapping",
]  # fmt: skip
TOOL_STRIP: list[str | None] = [*TOOL_IDS, None, *BOOLEAN_IDS, "edit.delete"]
