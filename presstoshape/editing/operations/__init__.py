"""Operations: the only code that changes app state. Importing this package registers every command."""

from presstoshape.editing.operations import (  # noqa: F401
    arrange,
    booleans,
    composites,
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
