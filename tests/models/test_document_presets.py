from presstoshape.geometry.units import MAX_DOCUMENT_PX, MAX_DPI, MIN_DPI, UNITS, to_px
from presstoshape.models.document_presets import DEFAULT, PRESETS, PRINT, find


def test_ids_are_unique_and_findable():
    ids = [preset.id for preset in PRESETS]
    assert len(ids) == len(set(ids))
    assert find("print.a4").name == "A4"
    assert find("nope") is None


def test_every_preset_is_a_valid_document():
    for preset in (*PRESETS, DEFAULT):
        assert preset.unit in UNITS
        assert MIN_DPI <= preset.dpi <= MAX_DPI
        for side in (preset.width, preset.height):
            assert 1 <= to_px(side, preset.unit, preset.dpi) <= MAX_DOCUMENT_PX


def test_paper_formats_are_portrait():
    paper = [preset for preset in PRESETS if preset.category == PRINT and preset.id != "print.business_card"]
    assert paper and all(preset.width < preset.height for preset in paper)


def test_default_matches_the_documents_built_in_size():
    from presstoshape.models.app_state import Document

    document = Document()
    assert (DEFAULT.width, DEFAULT.height, DEFAULT.unit, DEFAULT.dpi) == (
        document.width,
        document.height,
        document.unit,
        document.dpi,
    )
