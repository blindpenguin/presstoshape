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


def _menu_labels(entries) -> list[list[str]]:
    """Translated labels per menu (submenus as their own menu), with every command's label."""
    from presstoshape.i18n import _
    from presstoshape.tools.registry import TOOLS

    labels = {entry.id: entry.label for entry in registry.operations()}
    labels.update(keymap.WINDOW_COMMANDS)
    labels.update({entry.id: entry.label for entry in TOOLS})
    menus, current = [], []
    for entry in entries:
        if isinstance(entry, tuple):
            current.append(_(entry[0]))
            menus.extend(_menu_labels(entry[1]))
        elif entry is not None:
            current.append(_(labels[entry]))
    return [current, *menus]


def _mnemonic(label: str) -> str | None:
    index = label.replace("&&", "").find("&")
    return label.replace("&&", "")[index + 1].lower() if index >= 0 else None


def _assert_unique_mnemonics():
    from presstoshape.i18n import _

    groups = [[_(title) for title, _entries in keymap.MENUS]]
    for _title, entries in keymap.MENUS:
        groups.extend(_menu_labels(entries))
    for labels in groups:
        keys = [_mnemonic(label) for label in labels]
        assert None not in keys, labels
        assert len(keys) == len(set(keys)), labels


def test_menu_mnemonics_are_unique_in_english():
    _assert_unique_mnemonics()


def test_menu_mnemonics_are_unique_in_german(german):
    _assert_unique_mnemonics()
