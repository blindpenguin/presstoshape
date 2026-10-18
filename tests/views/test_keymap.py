import presstoshape.editing.operations  # noqa: F401  (registers every operation)
from presstoshape.editing import registry
from presstoshape.views import keymap


def _known_ids() -> set[str]:
    operations = {entry.id for entry in registry.operations()}
    return operations | set(keymap.WINDOW_COMMANDS) | set(keymap.TOOL_IDS)


def test_every_layout_id_resolves():
    layouts = [ids for _, ids in keymap.MENUS] + [keymap.MAIN_TOOLBAR, keymap.TOOL_STRIP]
    used = set()
    for ids in layouts:
        for entry in ids:
            if isinstance(entry, tuple):
                used.update(entry[1])
            elif entry not in (None, keymap.ZOOM_LABEL):
                used.add(entry)
    assert used - _known_ids() == set()


def test_every_binding_belongs_to_a_command():
    assert set(keymap.KEYMAP) - _known_ids() == set()


def test_window_commands_and_operations_dont_share_ids():
    assert not set(keymap.WINDOW_COMMANDS) & {entry.id for entry in registry.operations()}
