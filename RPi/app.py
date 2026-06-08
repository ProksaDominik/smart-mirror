"""SmartMirror — entry point."""

from __future__ import annotations

from config import AppConfig
from services.bootstrap import bootstrap_app, shutdown_app
from ui.smartmirror_dashboard import build_smartmirror_dashboard, launch_smartmirror_dashboard


def main() -> None:
    ctx = bootstrap_app(AppConfig())
    demo = build_smartmirror_dashboard(ctx)

    try:
        launch_smartmirror_dashboard(ctx, demo)
    finally:
        shutdown_app(ctx)


if __name__ == "__main__":
    main()
