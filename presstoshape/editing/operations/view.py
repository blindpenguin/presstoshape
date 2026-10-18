"""Non-document state: active tool, zoom, the style and font size drawing tools give new shapes. No undo."""

from dataclasses import replace

from presstoshape.editing.registry import operation, register
from presstoshape.editing.session import Session
from presstoshape.models.app_state import Tool

MIN_ZOOM, MAX_ZOOM = 10, 800
_ZOOM_STEP = 1.25


def select_tool(session: Session, tool: Tool) -> None:
    state = session.state
    state.active_tool = tool
    state.node_selection = frozenset()
    state.status_message = f"Tool: {tool.name.title()}"
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


@operation("view.zoom_in", "Zoom &In")
def zoom_in(session: Session) -> None:
    set_zoom(session, session.state.zoom_percent * _ZOOM_STEP)


@operation("view.zoom_out", "Zoom &Out")
def zoom_out(session: Session) -> None:
    set_zoom(session, session.state.zoom_percent / _ZOOM_STEP)


register("view.zoom_actual", "&Actual Size", lambda session: set_zoom(session, 100))


def set_tool_style(session: Session, tool: Tool, **changes) -> None:
    """Changes the style `tool` gives new shapes. Not a document edit, so no undo step."""
    if "stroke_width" in changes:
        changes["stroke_width"] = max(0.0, changes["stroke_width"])
    styles = session.state.tool_styles
    styles[tool] = replace(styles[tool], **changes)
    session.notify()


def set_font_size(session: Session, size: float) -> None:
    session.state.font_size = max(1.0, size)
    session.notify()
