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
