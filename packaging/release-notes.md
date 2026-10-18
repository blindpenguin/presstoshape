**Nightly build $version**, built $date from [`$short_sha`]($repo_url/commit/$sha).

> [!WARNING]
> Nightlies are automatic development builds of the newest code. They passed the automated tests and a start-up check, but nobody tried them by hand. Expect bugs, and keep copies of files you care about.

### Which file?

| File | For |
|---|---|
| `$msi` | Windows 10/11, 64-bit: installs PressToShape (Start menu, uninstall via Installed apps). Installing a newer nightly replaces the old one. |
| `$portable` | Windows, no installation: unzip anywhere, run `PressToShape.exe`. Settings stay in that folder (`settings.ini`), nothing goes into the registry. |
| `$appimage` | Linux x86_64: make it executable (`chmod +x`, or Properties → allow executing), then run it. |
| `$source` | Source code of exactly this build: `uv sync`, then `uv run python main.py`. |
| `SHA256SUMS` | Checksums: `sha256sum -c SHA256SUMS --ignore-missing`. |

The builds aren't code-signed yet. Windows SmartScreen may warn about an unknown publisher: choose *More info* → *Run anyway*. Licenses of PressToShape and bundled components are in the `licenses` folder of each package.

### Changes since the previous nightly

$changes
