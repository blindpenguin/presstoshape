import sys
import types

from presstoshape import version


def test_packaged_build_reports_the_stamped_version(monkeypatch):
    build_info = types.ModuleType("presstoshape._build_info")
    build_info.VERSION = "0.1.0.dev20261019+g6ba15e8"
    monkeypatch.setitem(sys.modules, "presstoshape._build_info", build_info)
    assert version.app_version() == "0.1.0.dev20261019+g6ba15e8"


def test_source_run_reports_the_pyproject_version():
    assert version.app_version().endswith(" (source)")
    assert version.app_version().split()[0].count(".") == 2


def test_missing_pyproject_reports_unknown(monkeypatch, tmp_path):
    monkeypatch.setattr(version, "_PYPROJECT", tmp_path / "missing.toml")
    assert version.app_version() == "unknown"
