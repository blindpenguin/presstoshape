import datetime
import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_package.py"
_spec = importlib.util.spec_from_file_location("build_package", _SCRIPT)
build_package = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_package)

DAY = datetime.date(2026, 10, 19)
SHA = "6ba15e8c0ffee0123456789abcdef0123456789a"


def test_nightly_version_is_a_dev_release_with_the_commit():
    assert build_package.nightly_version("0.1.0", DAY, SHA) == "0.1.0.dev20261019+g6ba15e8"


def test_msi_version_counts_days_and_grows():
    assert build_package.msi_version("0.1.0", datetime.date(2026, 1, 1)) == "0.1.0"
    assert build_package.msi_version("0.1.0", DAY) == "0.1.291"
    assert build_package.msi_version("0.1.0", DAY + datetime.timedelta(days=1)) == "0.1.292"


def test_msi_version_rejects_what_windows_installer_cannot_hold():
    with pytest.raises(ValueError):
        build_package.msi_version("0.1.0", datetime.date(2025, 12, 31))
    with pytest.raises(ValueError):
        build_package.msi_version("256.0.0", DAY)


def test_asset_names_carry_version_platform_and_type():
    names = build_package.asset_names("0.1.0.dev20261019+g6ba15e8")
    assert names["msi"] == "PressToShape-0.1.0.dev20261019+g6ba15e8-windows-x64.msi"
    assert names["portable"].endswith("-windows-x64-portable.zip")
    assert names["appimage"].endswith("-linux-x86_64.AppImage")
    assert names["source"].endswith("-source.tar.gz")
    assert len(set(names.values())) == 4


def test_release_notes_name_build_files_and_changes():
    template = (build_package.PACKAGING / "release-notes.md").read_text(encoding="utf-8")
    notes = build_package.release_notes(template, "0.1.0.dev20261019+g6ba15e8", SHA, DAY, ["abc1234 Fix things"])
    assert f"{build_package.REPO_URL}/commit/{SHA}" in notes
    assert "2026-10-19" in notes and "`6ba15e8`" in notes
    assert "PressToShape-0.1.0.dev20261019+g6ba15e8-windows-x64.msi" in notes
    assert "- abc1234 Fix things" in notes
    assert "SmartScreen" in notes and "$" not in notes


def test_first_nightly_has_a_placeholder_change_list():
    template = (build_package.PACKAGING / "release-notes.md").read_text(encoding="utf-8")
    assert "- First nightly." in build_package.release_notes(template, "v", SHA, DAY, [])


def test_every_bundled_license_text_exists():
    missing = [name for name, source in build_package.license_sources().items() if not source.is_file()]
    assert missing == []


def test_excludelist_yields_plain_library_names():
    excluded = build_package._excluded_libraries()
    assert {"libc.so.6", "libstdc++.so.6", "libGL.so.1", "libxcb-dri3.so.0"} <= excluded
    assert not any("#" in name or " " in name for name in excluded)


def test_text_to_rtf_escapes_rtf_syntax_and_non_ascii():
    rtf = build_package.text_to_rtf("a {b} \\ c\nPaweł")
    assert rtf.startswith("{\\rtf1") and rtf.endswith("}")
    assert "a \\{b\\} \\\\ c\\par" in rtf
    assert "Pawe\\u322?" in rtf
    rtf.encode("ascii")
