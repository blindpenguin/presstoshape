"""Document sizes offered by the New Document dialog. Data only; adding a preset is one line."""

from dataclasses import dataclass

from presstoshape.i18n import N_
from presstoshape.models.app_state import Unit

PRINT = N_("Print")
SCREEN = N_("Screen")
WEB = N_("Web and social")
ICONS = N_("Icons")


@dataclass(frozen=True)
class DocumentPreset:
    # Stable id, remembered as the last used preset.
    id: str
    # Untranslated (N_) category and name; sizes are never translated.
    category: str
    name: str
    width: float
    height: float
    unit: Unit
    dpi: float


def _icon(size: int) -> DocumentPreset:
    return DocumentPreset(f"icon.{size}", ICONS, f"{size} × {size}", size, size, "px", 96.0)


PRESETS: tuple[DocumentPreset, ...] = (
    DocumentPreset("print.a3", PRINT, N_("A3"), 297, 420, "mm", 300.0),
    DocumentPreset("print.a4", PRINT, N_("A4"), 210, 297, "mm", 300.0),
    DocumentPreset("print.a5", PRINT, N_("A5"), 148, 210, "mm", 300.0),
    DocumentPreset("print.a6", PRINT, N_("A6"), 105, 148, "mm", 300.0),
    DocumentPreset("print.letter", PRINT, N_("US Letter"), 8.5, 11, "in", 300.0),
    DocumentPreset("print.legal", PRINT, N_("US Legal"), 8.5, 14, "in", 300.0),
    DocumentPreset("print.tabloid", PRINT, N_("Tabloid"), 11, 17, "in", 300.0),
    DocumentPreset("print.business_card", PRINT, N_("Business card"), 85, 55, "mm", 300.0),
    DocumentPreset("screen.hd", SCREEN, N_("HD"), 1280, 720, "px", 96.0),
    DocumentPreset("screen.full_hd", SCREEN, N_("Full HD"), 1920, 1080, "px", 96.0),
    DocumentPreset("screen.qhd", SCREEN, N_("QHD"), 2560, 1440, "px", 96.0),
    DocumentPreset("screen.uhd", SCREEN, N_("4K UHD"), 3840, 2160, "px", 96.0),
    DocumentPreset("web.square", WEB, N_("Square post"), 1080, 1080, "px", 96.0),
    DocumentPreset("web.portrait", WEB, N_("Portrait post"), 1080, 1350, "px", 96.0),
    DocumentPreset("web.story", WEB, N_("Story"), 1080, 1920, "px", 96.0),
    DocumentPreset("web.link_preview", WEB, N_("Link preview"), 1200, 630, "px", 96.0),
    *(_icon(size) for size in (16, 24, 32, 48, 64, 128, 256, 512, 1024)),
)

# What a document gets without the dialog (first start, cancelled startup dialog).
DEFAULT = DocumentPreset("default", "", N_("Default"), 600, 400, "px", 96.0)


def find(preset_id: str) -> DocumentPreset | None:
    return next((preset for preset in PRESETS if preset.id == preset_id), None)
