"""Operations: the only code that changes app state. Importing this package registers every command."""

from veccy.editing.operations import (  # noqa: F401
    documents,
    history,
    layers,
    node_editing,
    paths,
    selection,
    shapes,
    style,
    transform,
    view,
)
