"""System tray icon using pystray.

Provides start/pause/resume controls, status display, toast
notifications, and an open-output-folder action.

IMPORTANT: Uses ``icon.run_detached()`` not ``icon.run()`` to avoid
blocking the event loop.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

logger = logging.getLogger(__name__)


def _create_icon_image(size: int = 64) -> Image.Image:
    """Generate a simple branded icon image."""
    image = Image.new("RGB", (size, size), color=(73, 109, 137))
    draw = ImageDraw.Draw(image)
    # Draw "FA" text centred.
    draw.text((size // 6, size // 6), "FA", fill=(255, 255, 255))
    return image


def _load_icon_image(icon_path: str | Path | None = None) -> Image.Image:
    """Load icon from file, falling back to generated image."""
    if icon_path is None:
        icon_path = Path(__file__).parent / "app.ico"
    else:
        icon_path = Path(icon_path)

    if icon_path.exists():
        try:
            img = Image.open(icon_path)
            img.load()  # Force read before returning
            return img.convert("RGBA")
        except Exception:
            logger.debug("Failed to load icon from %s, using generated", icon_path)

    return _create_icon_image()


class TrayApp:
    """System tray integration for Fantasy Author.

    Parameters
    ----------
    on_start : callable
        Called when user clicks Start.
    on_pause : callable
        Called when user clicks Pause.
    on_resume : callable
        Called when user clicks Resume.
    on_quit : callable
        Called when user clicks Quit.
    on_show_window : callable
        Called when user double-clicks or clicks "Show Window".
    output_dir : str
        Path to the output directory for "Open Output" action.
    icon_path : str or Path, optional
        Path to a .ico file. Falls back to generated icon.
    """

    # Minimum seconds between toast notifications to prevent OS spam.
    _NOTIFY_COOLDOWN = 30.0
    # Minimum seconds between menu rebuilds to prevent Win32 message pump flood.
    _MENU_COOLDOWN = 10.0

    def __init__(
        self,
        on_start: Callable[[], Any] | None = None,
        on_pause: Callable[[], Any] | None = None,
        on_resume: Callable[[], Any] | None = None,
        on_quit: Callable[[], Any] | None = None,
        on_show_window: Callable[[], Any] | None = None,
        output_dir: str = ".",
        icon_path: str | Path | None = None,
        extra_menu_items_factory: Callable[[], list] | None = None,
        show_default_runtime_controls: bool = True,
        show_output_action: bool = True,
        show_window_action: bool = True,
    ) -> None:
        self._on_start = on_start or (lambda: None)
        self._on_pause = on_pause or (lambda: None)
        self._on_resume = on_resume or (lambda: None)
        self._on_quit = on_quit or (lambda: None)
        self._on_show_window = on_show_window or (lambda: None)
        self._output_dir = output_dir
        self._icon_path = icon_path
        self._extra_menu_items_factory = extra_menu_items_factory
        self._show_default_runtime_controls = show_default_runtime_controls
        self._show_output_action = show_output_action
        self._show_window_action = show_window_action
        self._status = "Idle"
        self._paused = False
        self._icon: Icon | None = None
        self._lock = threading.Lock()
        self._last_notify_time: float = 0.0
        self._last_menu_refresh: float = 0.0
        self._menu_refresh_pending = False
        # Extended status fields for rich tray display
        self._universe_name: str = ""
        self._word_count: int = 0
        self._tunnel_url: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Create the tray icon and run it in a detached thread.

        Idempotent: safe to call multiple times (already running is a no-op).
        """
        if self._icon is not None:
            logger.debug("Tray already running, skipping start()")
            return

        menu = self._build_menu()
        self._icon = Icon(
            "Fantasy Author",
            _load_icon_image(self._icon_path),
            menu=menu,
        )
        # run_detached so we don't block the caller's event loop.
        self._icon.run_detached()
        logger.info("System tray started (detached)")

    def stop(self) -> None:
        """Remove the tray icon and clean up."""
        if self._icon is not None:
            self._icon.stop()
            self._icon = None
            logger.info("System tray stopped")

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    def update_status(self, status: str) -> None:
        """Update the status text shown in the tray menu.

        Throttled to avoid flooding the Win32 message pump with rapid
        menu rebuilds that can freeze the desktop.
        """
        with self._lock:
            self._status = status
        self._update_tooltip()
        self._throttled_menu_refresh()

    def update_extended_status(
        self,
        *,
        universe_name: str | None = None,
        word_count: int | None = None,
        tunnel_url: str | None = None,
        phase: str | None = None,
    ) -> None:
        """Update rich status fields shown in the tray menu/tooltip."""
        with self._lock:
            if universe_name is not None:
                self._universe_name = universe_name
            if word_count is not None:
                self._word_count = word_count
            if tunnel_url is not None:
                self._tunnel_url = tunnel_url
            if phase is not None:
                self._status = phase
        self._update_tooltip()
        self._throttled_menu_refresh()

    def _update_tooltip(self) -> None:
        """Update the hover tooltip with current status summary."""
        if self._icon is None:
            return
        with self._lock:
            parts = ["Fantasy Author"]
            if self._universe_name:
                parts.append(self._universe_name)
            parts.append(self._status)
            if self._word_count:
                parts.append(f"{self._word_count:,} words")
        try:
            self._icon.title = " | ".join(parts)
        except Exception:
            pass  # pystray may not support title on all platforms

    def notify(self, title: str, message: str = "") -> None:
        """Show a toast / balloon notification.

        Throttled to prevent notification spam that can overwhelm the OS
        notification system and cause cascading UI freezes.
        """
        if self._icon is None:
            return

        now = time.monotonic()
        with self._lock:
            elapsed = now - self._last_notify_time
            if elapsed < self._NOTIFY_COOLDOWN:
                logger.debug(
                    "Notification suppressed (%.1fs < %.1fs cooldown): %s",
                    elapsed, self._NOTIFY_COOLDOWN, title,
                )
                return
            self._last_notify_time = now

        try:
            self._icon.notify(message, title=title)
        except Exception:
            logger.debug("Toast notification failed", exc_info=True)

    # ------------------------------------------------------------------
    # Menu building
    # ------------------------------------------------------------------

    def _build_menu(self) -> Menu:
        with self._lock:
            status = self._status
            paused = self._paused
            universe = self._universe_name
            words = self._word_count
            tunnel = self._tunnel_url

        items: list[MenuItem | Menu] = []

        # Status header section
        if universe:
            items.append(MenuItem(f"Universe: {universe}", lambda _: None, enabled=False))
        items.append(MenuItem(f"Phase: {status}", lambda _: None, enabled=False))
        if words:
            items.append(MenuItem(f"Words: {words:,}", lambda _: None, enabled=False))
        if tunnel:
            # Show abbreviated URL
            short = tunnel.replace("https://", "")
            items.append(MenuItem(f"Tunnel: {short}", lambda _: None, enabled=False))

        # Extra menu items factory (for HostTrayService dashboard aggregation)
        if self._extra_menu_items_factory:
            extra = self._extra_menu_items_factory()
            if extra:
                items.append(Menu.SEPARATOR)
                items.extend(extra)

        # Default runtime controls (show window, pause/resume)
        if self._show_default_runtime_controls:
            items.append(Menu.SEPARATOR)

            if self._show_window_action:
                items.append(MenuItem(
                    "Show Window",
                    self._handle_show_window,
                    default=True,
                ))
            items.append(MenuItem(
                "Pause",
                self._handle_pause,
                visible=not paused,
            ))
            items.append(MenuItem(
                "Resume",
                self._handle_resume,
                visible=paused,
            ))

        # Output and quit
        if self._show_output_action:
            items.append(Menu.SEPARATOR)
            items.append(MenuItem("Open Output", self._handle_open_output))
        items.append(Menu.SEPARATOR)
        items.append(MenuItem("Quit", self._handle_quit))

        return Menu(*items)

    def _throttled_menu_refresh(self) -> None:
        """Schedule a menu rebuild, throttled to avoid flooding the message pump."""
        now = time.monotonic()
        with self._lock:
            elapsed = now - self._last_menu_refresh
            if elapsed < self._MENU_COOLDOWN:
                if not self._menu_refresh_pending:
                    self._menu_refresh_pending = True
                    delay = self._MENU_COOLDOWN - elapsed
                    threading.Timer(delay, self._deferred_menu_refresh).start()
                return
            self._last_menu_refresh = now
        self._do_menu_refresh()

    def _deferred_menu_refresh(self) -> None:
        """Execute a deferred menu refresh after the cooldown expires."""
        with self._lock:
            self._menu_refresh_pending = False
            self._last_menu_refresh = time.monotonic()
        self._do_menu_refresh()

    def _do_menu_refresh(self) -> None:
        """Actually rebuild and reassign the menu."""
        if self._icon is not None:
            self._icon.menu = self._build_menu()
            try:
                self._icon.update_menu()
            except Exception:
                logger.debug("Menu update failed", exc_info=True)

    def refresh_menu(self) -> None:
        """Explicitly refresh the menu immediately (used by HostTrayService)."""
        self._do_menu_refresh()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _handle_show_window(self, _icon: Any = None, _item: Any = None) -> None:
        logger.info("Tray: Show Window clicked")
        self._on_show_window()

    def _handle_start(self, _icon: Any = None, _item: Any = None) -> None:
        logger.info("Tray: Start clicked")
        self._on_start()
        self.update_status("Running")

    def _handle_pause(self, _icon: Any = None, _item: Any = None) -> None:
        logger.info("Tray: Pause clicked")
        with self._lock:
            self._paused = True
        self._on_pause()
        self.update_status("Paused")

    def _handle_resume(self, _icon: Any = None, _item: Any = None) -> None:
        logger.info("Tray: Resume clicked")
        with self._lock:
            self._paused = False
        self._on_resume()
        self.update_status("Running")

    def _handle_open_output(
        self, _icon: Any = None, _item: Any = None
    ) -> None:
        """Open the output directory in the system file manager."""
        path = os.path.abspath(self._output_dir)
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            logger.warning("Could not open output directory: %s", path)

    def _handle_quit(self, _icon: Any = None, _item: Any = None) -> None:
        logger.info("Tray: Quit clicked")
        self._on_quit()
        self.stop()
