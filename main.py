import os
import sys


def main() -> None:
    # Imports stay inside so --version answers without loading Qt.
    if "--version" in sys.argv[1:]:
        from presstoshape.version import app_version

        print(f"PressToShape {app_version()}")
        return
    from presstoshape.app import App

    if "--self-test" in sys.argv[1:]:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        sys.exit(App(language="en").run(self_test=True))
    sys.exit(App().run())


if __name__ == "__main__":
    main()
