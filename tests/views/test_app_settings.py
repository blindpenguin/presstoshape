from PySide6.QtCore import QSettings

from presstoshape.views.app_settings import PORTABLE_MARKER, PORTABLE_SETTINGS, open_settings


def test_portable_build_keeps_settings_next_to_the_executable(tmp_path):
    (tmp_path / PORTABLE_MARKER).write_text("portable")
    settings = open_settings(str(tmp_path / "PressToShape.exe"), frozen=True)
    assert settings.format() == QSettings.Format.IniFormat
    assert settings.fileName() == str(tmp_path / PORTABLE_SETTINGS)


def test_installed_build_and_source_runs_use_the_platform_location(tmp_path):
    installed = open_settings(str(tmp_path / "PressToShape.exe"), frozen=True)
    (tmp_path / PORTABLE_MARKER).write_text("portable")
    source_run = open_settings(str(tmp_path / "python"), frozen=False)
    for settings in (installed, source_run):
        assert settings.format() == QSettings.Format.NativeFormat
        assert str(tmp_path) not in settings.fileName()


def test_translations_folder_is_portable_or_app_data(tmp_path):
    from presstoshape.views.app_settings import PORTABLE_TRANSLATIONS, translations_folder

    installed = translations_folder(str(tmp_path / "PressToShape.exe"), frozen=True)
    assert installed.name == "translations" and tmp_path not in installed.parents
    (tmp_path / PORTABLE_MARKER).write_text("portable")
    assert translations_folder(str(tmp_path / "PressToShape.exe"), frozen=True) == tmp_path / PORTABLE_TRANSLATIONS


def test_language_and_renderer_settings(tmp_path):
    from presstoshape.views import app_settings

    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    assert app_settings.language(settings) is None
    assert app_settings.renderer(settings) == "auto"
    app_settings.set_language(settings, "de")
    app_settings.set_renderer(settings, "cpu")
    assert (app_settings.language(settings), app_settings.renderer(settings)) == ("de", "cpu")
    app_settings.set_language(settings, None)
    assert app_settings.language(settings) is None
    settings.setValue("renderer", "metal")
    assert app_settings.renderer(settings) == "auto"
