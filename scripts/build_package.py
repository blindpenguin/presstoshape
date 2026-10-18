"""Dev/CI-only: builds the nightly packages. The same commands run in .github/workflows/nightly.yml and locally.

Usage: uv run --group build python scripts/build_package.py <command> [options]
  version  [--date YYYY-MM-DD] [--sha SHA]       print version, msi_version and date as key=value lines
  source   --version V                           source tarball of HEAD (tracked files only)
  notes    --version V --sha SHA --previous SHA  release notes with the commits since the previous nightly
  linux    [--version V --sha SHA --date D]      frozen app + AppImage (self-tested)
  windows  [--version V --msi-version M ...]     frozen app + portable ZIP + MSI (self-tested; needs wix 7)
  test-msi PATH                                  install the MSI silently, self-test the installed app, uninstall
Outputs go to dist/release/. With DISPLAY set (e.g. under xvfb-run) the self-test also runs on the real platform.
"""

import argparse
import datetime
import hashlib
import os
import re
import shutil
import string
import subprocess
import sys
import sysconfig
import tempfile
import urllib.request
import zipfile
from importlib.metadata import distribution
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = ROOT / "dist" / "release"
PACKAGING = ROOT / "packaging"
REPO_URL = "https://github.com/blindpenguin/presstoshape"
NAME = "PressToShape"
# The MSI build number counts days from here; Windows Installer caps that field at 65535.
_MSI_EPOCH = datetime.date(2026, 1, 1)
GENERATED = ROOT / "build" / "packaging"
TOOLS = ROOT / "build" / "tools"
FROZEN = ROOT / "dist" / NAME
BUILD_INFO = ROOT / "presstoshape" / "_build_info.py"
ICON_SVG = ROOT / "presstoshape" / "assets" / "app" / "presstoshape.svg"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
SELF_TEST_TIMEOUT = 120
# Must match presstoshape/views/app_settings.py (this script doesn't import the app).
PORTABLE_MARKER = "portable.txt"
PORTABLE_NOTE = (
    "This file makes PressToShape portable: its settings are stored in settings.ini in this folder\n"
    "instead of the Windows registry. Delete this file to use the normal per-user settings.\n"
)
# Pinned downloads: (url, sha256). appimagetool would otherwise fetch an unpinned runtime at build time.
APPIMAGETOOL = (
    "https://github.com/AppImage/appimagetool/releases/download/1.9.1/appimagetool-x86_64.AppImage",
    "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0",
)
APPIMAGE_RUNTIME = (
    "https://github.com/AppImage/type2-runtime/releases/download/20251108/runtime-x86_64",
    "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d",
)


def base_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def nightly_version(base: str, day: datetime.date, sha: str) -> str:
    """PEP 440 dev release with the commit as local label: 0.1.0.dev20261019+g6ba15e8."""
    return f"{base}.dev{day:%Y%m%d}+g{sha[:7]}"


def msi_version(base: str, day: datetime.date) -> str:
    """major.minor.build with build = days since _MSI_EPOCH, so each day's nightly upgrades the previous one."""
    major, minor = (int(part) for part in base.split(".")[:2])
    build = (day - _MSI_EPOCH).days
    if not (0 <= major <= 255 and 0 <= minor <= 255 and 0 <= build <= 65535):
        raise ValueError(f"version {base} on {day} doesn't fit an MSI version")
    return f"{major}.{minor}.{build}"


def asset_names(version: str) -> dict[str, str]:
    stem = f"{NAME}-{version}"
    return {
        "msi": f"{stem}-windows-x64.msi",
        "portable": f"{stem}-windows-x64-portable.zip",
        "appimage": f"{stem}-linux-x86_64.AppImage",
        "source": f"{stem}-source.tar.gz",
    }


def release_notes(template: str, version: str, sha: str, day: datetime.date, commits: list[str]) -> str:
    changes = "\n".join(f"- {line}" for line in commits) or "- First nightly."
    return string.Template(template).substitute(
        version=version,
        date=day.isoformat(),
        sha=sha,
        short_sha=sha[:7],
        repo_url=REPO_URL,
        changes=changes,
        **asset_names(version),
    )


def _python_license() -> Path:
    candidates = [Path(sys.base_prefix) / "LICENSE.txt", Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"]
    return next((path for path in candidates if path.is_file()), candidates[0])


def _dist_license(name: str) -> Path:
    for file in distribution(name).files or ():
        if file.name.upper().startswith(("LICENSE", "COPYING")):
            return Path(file.locate())
    return Path(f"<no license file in {name}>")


def license_sources() -> dict[str, Path]:
    """Bundled license texts: file name in the package's licenses/ folder -> source file."""
    return {
        "PressToShape-GPL-3.0.txt": ROOT / "LICENSE",
        "Python.txt": _python_license(),
        "Qt-PySide6-LGPL-3.0.txt": PACKAGING / "licenses" / "lgpl-3.0.txt",
        "skia-python.txt": _dist_license("skia-python"),
        "skia-pathops.txt": _dist_license("skia-pathops"),
        "svgelements.txt": _dist_license("svgelements"),
        "Tabler-icons.txt": PACKAGING / "licenses" / "tabler-icons.txt",
    }


def collect_licenses(target: Path) -> None:
    missing = [str(source) for source in license_sources().values() if not source.is_file()]
    if missing:
        raise SystemExit(f"missing license files: {', '.join(missing)}")
    target.mkdir(parents=True, exist_ok=True)
    for name, source in license_sources().items():
        (target / name).write_bytes(source.read_bytes())


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def _commits_since(previous: str) -> list[str]:
    if not previous:
        return []
    return [line for line in _git("log", "--no-merges", "--format=%h %s", f"{previous}..HEAD").splitlines() if line]


def _build_day(args: argparse.Namespace) -> datetime.date:
    return datetime.date.fromisoformat(args.date) if args.date else datetime.datetime.now(datetime.UTC).date()


def _command_version(args: argparse.Namespace) -> None:
    day = _build_day(args)
    sha = args.sha or _git("rev-parse", "HEAD")
    base = base_version()
    print(f"version={nightly_version(base, day, sha)}")
    print(f"msi_version={msi_version(base, day)}")
    print(f"date={day.isoformat()}")


# --- freezing -------------------------------------------------------------------------------


def _render_icons() -> None:
    """App icon as PNGs (AppImage) and a multi-size .ico (Windows exe and MSI), rendered from the SVG."""
    from PIL import Image
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - QPainter needs it
    GENERATED.mkdir(parents=True, exist_ok=True)
    renderer = QSvgRenderer(str(ICON_SVG))
    if not renderer.isValid():
        raise SystemExit(f"can't render {ICON_SVG}")
    for size in ICON_SIZES:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image.save(str(GENERATED / f"presstoshape-{size}.png"))
    largest = Image.open(GENERATED / f"presstoshape-{ICON_SIZES[-1]}.png")
    largest.save(GENERATED / "presstoshape.ico", sizes=[(size, size) for size in ICON_SIZES])


def _executable(folder: Path) -> Path:
    return folder / (f"{NAME}.exe" if sys.platform == "win32" else NAME)


def self_test(command: list[str], platform: str | None = "offscreen") -> None:
    """Runs a built app with --self-test; `platform` None uses the system's display (X11/Wayland)."""
    env = dict(os.environ, APPIMAGE_EXTRACT_AND_RUN="1")
    env.pop("QT_QPA_PLATFORM", None)
    if platform is not None:
        env["QT_QPA_PLATFORM"] = platform
    label = platform or "native display"
    log = Path(tempfile.gettempdir()) / "presstoshape-self-test.log"
    try:
        result = subprocess.run([*command, "--self-test"], env=env, timeout=SELF_TEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise SystemExit(f"self-test ({label}) timed out after {SELF_TEST_TIMEOUT} s") from None
    if result.returncode != 0:
        tail = log.read_text(encoding="utf-8").splitlines()[-3:] if log.is_file() else ["(no log)"]
        raise SystemExit(f"self-test ({label}) failed with exit code {result.returncode}:\n" + "\n".join(tail))
    print(f"self-test ({label}) passed")


def _self_tests(command: list[str]) -> None:
    self_test(command)
    if sys.platform == "win32" or os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        self_test(command, platform=None)


def freeze(version: str, sha: str, day: datetime.date) -> Path:
    """PyInstaller onedir bundle in dist/PressToShape with licenses next to the executable, self-tested."""
    _render_icons()
    BUILD_INFO.write_text(
        f'VERSION = "{version}"\nCOMMIT = "{sha}"\nBUILD_DATE = "{day.isoformat()}"\n', encoding="utf-8"
    )
    try:
        subprocess.run(
            [
                sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                "--distpath", str(FROZEN.parent), "--workpath", str(ROOT / "build" / "pyinstaller"),
                str(PACKAGING / "presstoshape.spec"),
            ],
            cwd=ROOT,
            check=True,
        )  # fmt: skip
    finally:
        # A leftover stamp would make source runs report the nightly version.
        BUILD_INFO.unlink(missing_ok=True)
    collect_licenses(FROZEN / "licenses")
    _self_tests([str(_executable(FROZEN))])
    return FROZEN


def _download(source: tuple[str, str], target: Path) -> Path:
    url, expected = source
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected:
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        actual = hashlib.sha256(data).hexdigest()
        if actual != expected:
            raise SystemExit(f"checksum mismatch for {url}: {actual}")
        target.write_bytes(data)
        target.chmod(0o755)
    return target


# --- Linux ------------------------------------------------------------------------------------


def _bundle_xcb_cursor(folder: Path) -> None:
    """Qt's xcb platform plugin needs libxcb-cursor, which many distributions don't install by default."""
    if any(folder.rglob("libxcb-cursor.so.0")):
        return
    listing = subprocess.run(["ldconfig", "-p"], check=True, capture_output=True, text=True).stdout
    paths = [line.split(" => ")[-1] for line in listing.splitlines() if "libxcb-cursor.so.0 " in line]
    if not paths:
        raise SystemExit("libxcb-cursor.so.0 not found on the build machine (apt install libxcb-cursor0)")
    shutil.copy2(paths[0], folder / "_internal" / "libxcb-cursor.so.0")


def _excluded_libraries() -> set[str]:
    lines = (PACKAGING / "linux" / "excludelist").read_text(encoding="utf-8").splitlines()
    return {line.split("#")[0].strip() for line in lines} - {""}


def _needed_libraries(path: Path) -> set[str]:
    output = subprocess.run(["readelf", "-d", "-W", str(path)], capture_output=True, text=True).stdout
    return set(re.findall(r"\(NEEDED\)\s+Shared library: \[(.+?)\]", output))


def _is_elf(path: Path) -> bool:
    with path.open("rb") as file:
        return file.read(4) == b"\x7fELF"


def prune_linux_bundle(folder: Path) -> list[str]:
    """Drops what an AppImage must take from the host: excludelist libraries (GPU drivers, libc, X11, fonts) and
    Qt's GTK theme plugin with the GTK stack it drags in. Then removes top-level libraries nothing needs anymore.
    Returns the removed names."""
    internal = folder / "_internal"
    removed = []
    (internal / "PySide6" / "Qt" / "plugins" / "platformthemes" / "libqgtk3.so").unlink(missing_ok=True)
    excluded = _excluded_libraries()
    for library in internal.glob("*.so*"):
        if library.name in excluded:
            library.unlink()
            removed.append(library.name)
    needed_by: dict[Path, set[str]] = {}
    while True:
        files = [path for path in folder.rglob("*") if path.is_file() and not path.is_symlink() and _is_elf(path)]
        needed = set().union(*(needed_by.setdefault(path, _needed_libraries(path)) for path in files))
        # libpython is loaded by the PyInstaller bootloader with dlopen, so no ELF lists it.
        orphans = [
            library
            for library in internal.glob("lib*.so*")
            if library.name not in needed and not library.name.startswith("libpython")
        ]
        if not orphans:
            return removed
        for library in orphans:
            needed_by.pop(library, None)
            library.unlink()
            removed.append(library.name)


def _identity(args: argparse.Namespace) -> tuple[str, str, datetime.date]:
    day = _build_day(args)
    sha = args.sha or _git("rev-parse", "HEAD")
    return args.version or nightly_version(base_version(), day, sha), sha, day


def _command_linux(args: argparse.Namespace) -> None:
    version, sha, day = _identity(args)
    frozen = freeze(version, sha, day)
    _bundle_xcb_cursor(frozen)
    print("removed from bundle:", " ".join(sorted(prune_linux_bundle(frozen))))

    app_dir = ROOT / "build" / "AppDir"
    shutil.rmtree(app_dir, ignore_errors=True)
    shutil.copytree(frozen, app_dir / "usr" / "bin" / NAME, symlinks=True)
    shutil.copy2(PACKAGING / "linux" / "AppRun", app_dir / "AppRun")
    shutil.copy2(PACKAGING / "linux" / "presstoshape.desktop", app_dir / "presstoshape.desktop")
    shutil.copy2(GENERATED / "presstoshape-256.png", app_dir / "presstoshape.png")
    (app_dir / ".DirIcon").symlink_to("presstoshape.png")

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    target = RELEASE_DIR / asset_names(version)["appimage"]
    tool = _download(APPIMAGETOOL, TOOLS / "appimagetool-1.9.1-x86_64.AppImage")
    runtime = _download(APPIMAGE_RUNTIME, TOOLS / "runtime-20251108-x86_64")
    env = dict(os.environ, ARCH="x86_64", APPIMAGE_EXTRACT_AND_RUN="1")
    subprocess.run(
        [str(tool), "--no-appstream", "--runtime-file", str(runtime), str(app_dir), str(target)], env=env, check=True
    )
    _self_tests([str(target)])
    print(target)


def _command_source(args: argparse.Namespace) -> None:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    target = RELEASE_DIR / asset_names(args.version)["source"]
    _git("archive", "--format=tar.gz", f"--prefix={NAME}-{args.version}/", f"--output={target}", "HEAD")
    print(target)


def _command_notes(args: argparse.Namespace) -> None:
    template = (PACKAGING / "release-notes.md").read_text(encoding="utf-8")
    day = datetime.date.fromisoformat(args.date) if args.date else datetime.datetime.now(datetime.UTC).date()
    notes = release_notes(template, args.version, args.sha, day, _commits_since(args.previous))
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    target = RELEASE_DIR.parent / "release-notes.md"
    target.write_text(notes, encoding="utf-8")
    print(target)


# --- Windows ----------------------------------------------------------------------------------


def text_to_rtf(text: str) -> str:
    """Plain text as a minimal RTF document (the MSI license page only shows RTF)."""
    escaped = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    escaped = "".join(char if ord(char) < 128 else f"\\u{ord(char)}?" for char in escaped)
    body = "\\par\n".join(escaped.splitlines())
    return "{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0 Consolas;}}\\f0\\fs16\n" + body + "\n}"


def _command_windows(args: argparse.Namespace) -> None:
    version, sha, day = _identity(args)
    msi = args.msi_version or msi_version(base_version(), day)
    frozen = freeze(version, sha, day)
    names = asset_names(version)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)

    # The marker makes the app keep its settings in the extracted folder instead of the registry; only the ZIP
    # gets it, the MSI is built from the same folder afterwards.
    marker = frozen / PORTABLE_MARKER
    marker.write_text(PORTABLE_NOTE, encoding="utf-8")
    try:
        portable = RELEASE_DIR / names["portable"]
        archive = shutil.make_archive(
            str(portable.with_suffix("")), "zip", root_dir=frozen.parent, base_dir=frozen.name
        )
    finally:
        marker.unlink()
    with zipfile.ZipFile(archive) as contents:
        if f"{frozen.name}/{PORTABLE_MARKER}" not in contents.namelist():
            raise SystemExit(f"{PORTABLE_MARKER} missing from {archive}")
    print(archive)

    license_rtf = GENERATED / "license.rtf"
    license_rtf.write_text(text_to_rtf((ROOT / "LICENSE").read_text(encoding="utf-8")), encoding="ascii")
    target = RELEASE_DIR / names["msi"]
    subprocess.run(
        [
            "wix", "build", "-acceptEula", "wix7", "-arch", "x64", "-ext", "WixToolset.UI.wixext",
            "-d", f"Version={msi}", "-d", f"IconFile={GENERATED / 'presstoshape.ico'}",
            "-d", f"LicenseRtf={license_rtf}", "-bindpath", f"app={frozen}",
            "-o", str(target), str(PACKAGING / "windows" / "PressToShape.wxs"),
        ],
        check=True,
    )  # fmt: skip
    print(target)


def _command_test_msi(args: argparse.Namespace) -> None:
    """Install, self-test and uninstall on a throwaway machine (CI); checks upgrade code, files and removal."""
    msi = Path(args.path).resolve()
    installed = Path(os.environ.get("ProgramW6432", r"C:\Program Files")) / NAME
    log = ROOT / "build" / "msi-install.log"
    subprocess.run(["msiexec", "/i", str(msi), "/qn", "/norestart", "/l*v", str(log)], check=True)
    try:
        if not (installed / f"{NAME}.exe").is_file():
            raise SystemExit(f"{installed / NAME}.exe missing after install (log: {log})")
        if (installed / PORTABLE_MARKER).exists():
            raise SystemExit(f"the installed app has {PORTABLE_MARKER}, so it would act like the portable build")
        _self_tests([str(installed / f"{NAME}.exe")])
    finally:
        subprocess.run(["msiexec", "/x", str(msi), "/qn", "/norestart"], check=True)
    if (installed / f"{NAME}.exe").exists():
        raise SystemExit(f"{installed} still there after uninstall")
    print("MSI install, self-test and uninstall passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    version = commands.add_parser("version")
    version.add_argument("--date")
    version.add_argument("--sha")
    version.set_defaults(run=_command_version)
    source = commands.add_parser("source")
    source.add_argument("--version", required=True)
    source.set_defaults(run=_command_source)
    notes = commands.add_parser("notes")
    notes.add_argument("--version", required=True)
    notes.add_argument("--sha", required=True)
    notes.add_argument("--previous", default="")
    notes.add_argument("--date")
    notes.set_defaults(run=_command_notes)
    for name, run in (("linux", _command_linux), ("windows", _command_windows)):
        build = commands.add_parser(name)
        build.add_argument("--version")
        build.add_argument("--sha")
        build.add_argument("--date")
        if name == "windows":
            build.add_argument("--msi-version")
        build.set_defaults(run=run)
    test_msi = commands.add_parser("test-msi")
    test_msi.add_argument("path")
    test_msi.set_defaults(run=_command_test_msi)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
