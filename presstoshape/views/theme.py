from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

ICON_NORMAL = "#d4d4d8"
ICON_ACTIVE = "#60a5fa"
ICON_DISABLED = "#52525b"

PASTEBOARD = "#1e1e22"
ARTBOARD = "#ffffff"
ARTBOARD_BORDER = "#52525b"
PREVIEW_STROKE = "#60a5fa"
SELECTION = "#2563eb"
GUIDE = "#06b6d4"
GRID = "#94a3b8"
SNAP = "#f97316"
WARNING = "#ef4444"
MASK_OUTLINE = "#a855f7"


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setPalette(_palette())


def _palette() -> QPalette:
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, "#27272a"),
        (QPalette.ColorRole.WindowText, "#e4e4e7"),
        (QPalette.ColorRole.Base, "#18181b"),
        (QPalette.ColorRole.AlternateBase, "#27272a"),
        (QPalette.ColorRole.Text, "#e4e4e7"),
        (QPalette.ColorRole.Button, "#3f3f46"),
        (QPalette.ColorRole.ButtonText, "#e4e4e7"),
        (QPalette.ColorRole.Highlight, "#2563eb"),
        (QPalette.ColorRole.HighlightedText, "#ffffff"),
        (QPalette.ColorRole.ToolTipBase, "#3f3f46"),
        (QPalette.ColorRole.ToolTipText, "#e4e4e7"),
        (QPalette.ColorRole.PlaceholderText, "#71717a"),
    ):
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText, QPalette.ColorRole.WindowText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor("#71717a"))
    return palette
