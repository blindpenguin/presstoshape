from collections.abc import Callable
from functools import partial

from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QWidget

from presstoshape.editing import registry
from presstoshape.editing.operations import view
from presstoshape.editing.session import Session
from presstoshape.i18n import _
from presstoshape.models.app_state import AppState, Tool
from presstoshape.tools.registry import TOOLS
from presstoshape.views.icon_engine import icon
from presstoshape.views.keymap import KEYMAP, WINDOW_COMMANDS, Binding, Shortcut


def _sequences(item: str | QKeySequence.StandardKey) -> list[QKeySequence]:
    if isinstance(item, QKeySequence.StandardKey):
        return QKeySequence.keyBindings(item)
    return [QKeySequence(item)]


def _tooltip_keys(shortcut: Shortcut) -> str:
    """The shortcuts as declared in the keymap, not every platform alias of a standard key."""
    items = shortcut if isinstance(shortcut, tuple) else (shortcut,)
    names = [QKeySequence(item).toString(QKeySequence.SequenceFormat.NativeText) for item in items]
    return ", ".join(dict.fromkeys(name for name in names if name))


class AppActions:
    """One QAction per command id (operations, tools, window commands), shared by menus and toolbars."""

    def __init__(self, parent: QWidget, session: Session, window_commands: dict[str, Callable[[], object]]) -> None:
        self._parent = parent
        self._session = session
        self._actions: dict[str, QAction] = {}
        for entry in registry.operations():
            action = self._add(entry.id, _(entry.label), partial(entry.invoke, session))
            action.setCheckable(entry.checked is not None)
        for command_id, slot in window_commands.items():
            self._add(command_id, _(WINDOW_COMMANDS[command_id]), slot)
        self._tool_group = QActionGroup(parent)
        self._tool_actions: dict[Tool, QAction] = {}
        for entry in TOOLS:
            action = self._add(entry.id, _(entry.label), partial(view.select_tool, session, entry.tool))
            action.setCheckable(True)
            self._tool_group.addAction(action)
            self._tool_actions[entry.tool] = action

    def __getitem__(self, command_id: str) -> QAction:
        return self._actions[command_id]

    def _add(self, command_id: str, text: str, slot: Callable[[], object]) -> QAction:
        binding = KEYMAP.get(command_id, Binding())
        action = QAction(text, self._parent)
        if binding.icon is not None:
            action.setIcon(icon(binding.icon))
        if binding.shortcut is not None:
            # Every platform binding of a standard key (Paste is also Shift+Ins), each sequence once.
            items = binding.shortcut if isinstance(binding.shortcut, tuple) else (binding.shortcut,)
            keys = [key for item in items for key in _sequences(item)]
            action.setShortcuts(list({key.toString(): key for key in keys}.values()))
            action.setToolTip(f"{text.replace('&', '')} ({_tooltip_keys(binding.shortcut)})")
        # Lambda swallows triggered(checked) so it isn't passed into slots with optional args.
        action.triggered.connect(lambda: slot())
        self._actions[command_id] = action
        return action

    def set_enabled(self, command_id: str, enabled: bool) -> None:
        """For window commands, whose availability the window knows (registered operations use can_run)."""
        self._actions[command_id].setEnabled(enabled)

    def refresh(self, state: AppState) -> None:
        session = self._session
        for entry in registry.operations():
            action = self._actions[entry.id]
            action.setEnabled(entry.can_run(session))
            if entry.checked is not None:
                # Qt toggles a checkable action itself on click; the state decides what it shows.
                action.blockSignals(True)
                action.setChecked(entry.checked(session))
                action.blockSignals(False)
        self._label_history("edit.undo", _("&Undo"), session.undo_label)
        self._label_history("edit.redo", _("&Redo"), session.redo_label)
        self._tool_actions[state.active_tool].setChecked(True)

    def _label_history(self, command_id: str, base: str, step: str | None) -> None:
        # Escape '&' in labels so Qt doesn't read it as a mnemonic.
        self._actions[command_id].setText(f"{base} {step.replace('&', '&&')}" if step else base)
