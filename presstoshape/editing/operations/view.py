"""Non-document state: active tool, zoom, the style and font size drawing tools give new shapes. No undo."""

from dataclasses import replace

from presstoshape.editing.registry import operation, register
from presstoshape.editing.session import Session
from presstoshape.i18n import N_, _, pgettext
from presstoshape.models.app_state import Tool
from presstoshape.models.shapes import sanitized

MIN_ZOOM, MAX_ZOOM = 10, 800
_ZOOM_STEP = 1.25


def tool_name(tool: Tool) -> str:
    """The tool's name without mnemonic, for the status bar and panel titles."""
    names = {
        Tool.SELECT: pgettext("tool", "Select"),
        Tool.NODE: pgettext("tool", "Node"),
        Tool.PEN: pgettext("tool", "Pen"),
        Tool.PENCIL: pgettext("tool", "Pencil"),
        Tool.RECTANGLE: pgettext("tool", "Rectangle"),
        Tool.ELLIPSE: pgettext("tool", "Ellipse"),
        Tool.TEXT: pgettext("tool", "Text"),
    }
    return names[tool]


def select_tool(session: Session, tool: Tool) -> None:
    state = session.state
    state.active_tool = tool
    state.node_selection = frozenset()
    state.status_message = _("Tool: {name}").format(name=tool_name(tool))
    session.notify()


def set_zoom(session: Session, zoom_percent: float) -> None:
    zoom = max(MIN_ZOOM, min(MAX_ZOOM, round(zoom_percent)))
    if zoom == session.state.zoom_percent:
        return
    session.state.zoom_percent = zoom
    session.notify()


def take_restore_view_center(session: Session) -> tuple[float, float] | None:
    """The view a freshly opened .p2s file asks for, handed out once. Nothing displays it, so no notify."""
    center = session.state.restore_view_center
    session.state.restore_view_center = None
    return center


@operation("view.zoom_in", N_("Zoom &In"))
def zoom_in(session: Session) -> None:
    set_zoom(session, session.state.zoom_percent * _ZOOM_STEP)


@operation("view.zoom_out", N_("Zoom &Out"))
def zoom_out(session: Session) -> None:
    set_zoom(session, session.state.zoom_percent / _ZOOM_STEP)


register("view.zoom_actual", N_("&Actual Size"), lambda session: set_zoom(session, 100))


def set_tool_style(session: Session, tool: Tool, **changes) -> None:
    """Changes the style `tool` gives new shapes. Not a document edit, so no undo step."""
    styles = session.state.tool_styles
    styles[tool] = sanitized(replace(styles[tool], **changes))
    session.notify()


def clear_import_notes(session: Session) -> None:
    """The window showed the notes of the last opened file. Nothing displays them otherwise, so no notify."""
    session.state.import_notes = []


def set_pencil_smoothing(session: Session, value: int) -> None:
    """Tool setting, not a document edit."""
    session.state.pencil_smoothing = min(100, max(0, round(value)))
    session.notify()


def set_font_size(session: Session, size: float) -> None:
    session.state.font_size = max(1.0, size)
    session.notify()


# --- rulers, grid, guides and snapping: view state, not undo steps ---------------------------------------


def _toggle_view(session: Session, field: str, on: str, off: str) -> None:
    state = session.state
    value = not getattr(state.view, field)
    state.view = replace(state.view, **{field: value})
    state.status_message = on if value else off
    session.notify()


@operation("view.show_rulers", N_("Show &Rulers"), checked=lambda session: session.state.view.show_rulers)
def toggle_rulers(session: Session) -> None:
    _toggle_view(session, "show_rulers", _("Rulers shown"), _("Rulers hidden"))


@operation("view.show_grid", N_("Show &Grid"), checked=lambda session: session.state.view.show_grid)
def toggle_grid(session: Session) -> None:
    _toggle_view(session, "show_grid", _("Grid shown"), _("Grid hidden"))


@operation("view.show_guides", N_("Show G&uides"), checked=lambda session: session.state.view.show_guides)
def toggle_guides(session: Session) -> None:
    _toggle_view(session, "show_guides", _("Guides shown"), _("Guides hidden"))


@operation("view.lock_guides", N_("&Lock Guides"), checked=lambda session: session.state.view.lock_guides)
def toggle_lock_guides(session: Session) -> None:
    _toggle_view(session, "lock_guides", _("Guides locked"), _("Guides unlocked"))


@operation("view.show_references", N_("Show Referen&ces"), checked=lambda session: session.state.view.show_references)
def toggle_references(session: Session) -> None:
    _toggle_view(session, "show_references", _("Reference images shown"), _("Reference images hidden"))


def set_show_references(session: Session, shown: bool) -> None:
    """Shows or hides reference images (view state, not an undo step)."""
    state = session.state
    if state.view.show_references != shown:
        toggle_references(session)


@operation("view.snapping", N_("&Snapping"), checked=lambda session: session.state.snapping.enabled)
def toggle_snapping(session: Session) -> None:
    state = session.state
    state.snapping = replace(state.snapping, enabled=not state.snapping.enabled)
    state.status_message = _("Snapping on") if state.snapping.enabled else _("Snapping off")
    session.notify()


SNAP_TARGETS = ("grid", "guides", "artboard", "objects", "nodes")
# Target -> menu label in View → Snap To.
SNAP_TARGET_LABELS = {
    "grid": N_("&Grid"),
    "guides": N_("G&uides"),
    "artboard": N_("&Artboard"),
    "objects": N_("&Objects"),
    "nodes": N_("&Nodes"),
}


def set_snap_target(session: Session, target: str, on: bool) -> None:
    if target not in SNAP_TARGETS:
        raise ValueError(f"unknown snap target {target!r}")
    state = session.state
    state.snapping = replace(state.snapping, **{target: on})
    session.notify()


def set_snap_distance(session: Session, distance_px: float) -> None:
    session.state.snapping = replace(session.state.snapping, distance_px=min(30.0, max(2.0, float(distance_px))))
    session.notify()


def _snap_target_command(target: str):
    def run(session: Session) -> None:
        set_snap_target(session, target, not getattr(session.state.snapping, target))

    return run


for _target in SNAP_TARGETS:
    register(
        f"view.snap_{_target}",
        SNAP_TARGET_LABELS[_target],
        _snap_target_command(_target),
        checked=lambda session, target=_target: getattr(session.state.snapping, target),
    )
