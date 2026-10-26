# Packaging and nightlies

- `.github/workflows/nightly.yml` only orchestrates; all packaging logic is in `scripts/build_package.py` (subcommands `version`, `linux`, `windows`, `test-msi`, `source`, `notes`), which runs the same locally: `uv run --group build python scripts/build_package.py linux`. Build tools live in the `build` dependency group; outputs go to `dist/` and `build/` (gitignored).
- Static inputs are in `packaging/` (PyInstaller spec, WiX source, desktop entry, AppImage excludelist, release-notes template, license texts that wheels don't ship). Every bundled component needs its license in `license_sources()`; the build fails on a missing one.
- PyInstaller runs in onedir mode (Qt as separate libraries for the LGPL). Assets are found through `Path(__file__)`, which works frozen; keep it that way.
- `presstoshape/version.py` reads the generated, gitignored `presstoshape/_build_info.py` in builds, `pyproject.toml` from source. `main.py --self-test` is the headless smoke check every build must pass; extend it when adding something a frozen bundle could miss (new data files, plugins, native libraries).
- Pin everything: actions by commit SHA, WiX by version (its v7 EULA is accepted with `-acceptEula wix7`; free under the OSMF revenue threshold), downloaded tools by SHA-256 in `build_package.py`.
- The portable ZIP (only) contains `portable.txt` next to the exe; `views/app_settings.py` then stores settings in `settings.ini` there instead of the registry. `test-msi` checks the installed app doesn't have it.
- Trial runs never publish to `nightly`: only `main` defaults to that tag, other refs to `nightly-test`.
