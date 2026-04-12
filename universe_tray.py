"""Universe Server system tray launcher.

Double-click the desktop shortcut -> this script starts:
  1. Author Daemon (LangGraph writing engine)
  2. MCP Universe Server (Python, port 8001)
  3. Cloudflare Tunnel (cloudflared, routes tinyassets.io -> localhost:8001)

A system tray icon shows live status. Hover for startup progress.
Right-click to quit.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from PIL import Image, ImageDraw, ImageFont
from pystray import Icon, Menu, MenuItem

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MCP_PORT = 8001
MCP_URL = "https://tinyassets.io/mcp"
ACTIVE_UNIVERSE_FILE = "output/.active_universe"
TUNNEL_TOKEN = (
    "eyJhIjoiYTQ2ZWI0ZjY5MjhkN2M1MzhiMzlmYmNlYmRlYmE0OWIi"
    "LCJ0IjoiYjU5ZjNjZDktYTQ3YS00Yzk3LTgwZTQtNzgyNjUxM2RlNj"
    "MwIiwicyI6Ik1EQmlPVGN6WVRBdE5qWmtPQzAwTldWaUxUa3paR1V0"
    "T1RjeE16UXpNMll3WkdNMCJ9"
)

PROJECT_DIR = Path(__file__).resolve().parent
LOG_DIR = PROJECT_DIR / "logs"

# ---------------------------------------------------------------------------
# Icon rendering
# ---------------------------------------------------------------------------

GREEN  = (76, 175, 80)    # all healthy
YELLOW = (255, 193, 7)    # partial
RED    = (244, 67, 54)    # down
GRAY   = (158, 158, 158)  # starting


def make_icon(color: tuple, size: int = 64) -> Image.Image:
    """Draw a simple circle icon with 'U' in the center."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color,
    )
    try:
        font = ImageFont.truetype("arial.ttf", size // 2)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "U", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((size - tw) / 2, (size - th) / 2 - 2),
        "U",
        fill=(255, 255, 255),
        font=font,
    )
    return img


# ---------------------------------------------------------------------------
# Process manager
# ---------------------------------------------------------------------------

class UniverseServerManager:
    """Manages daemon + MCP server + cloudflared tunnel."""

    def __init__(self) -> None:
        self.daemon_proc: subprocess.Popen | None = None
        self.mcp_proc: subprocess.Popen | None = None
        self.tunnel_proc: subprocess.Popen | None = None
        self._icon: Icon | None = None
        self._stop_event = threading.Event()

        # Granular startup tracking
        self._phase = "Initializing..."
        self._daemon_alive = False
        self._mcp_alive = False
        self._mcp_serving = False
        self._tunnel_alive = False
        self._tunnel_ok = False

        # Active universe tracking
        self._active_universe = self._read_active_universe()
        self._ensure_active_universe_file()

    def _read_active_universe(self) -> str:
        """Read the active universe from the marker file, or pick first available."""
        marker = PROJECT_DIR / ACTIVE_UNIVERSE_FILE
        if marker.exists():
            uid = marker.read_text(encoding="utf-8").strip()
            if uid and (PROJECT_DIR / "output" / uid).is_dir():
                return uid

        # Fall back to first universe that has a PROGRAM.md
        output_dir = PROJECT_DIR / "output"
        if output_dir.is_dir():
            for child in sorted(output_dir.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    if (child / "PROGRAM.md").exists():
                        return child.name
            # If nothing has a premise, just pick the first
            for child in sorted(output_dir.iterdir()):
                if child.is_dir() and not child.name.startswith("."):
                    return child.name
        return "default-universe"

    def _ensure_active_universe_file(self) -> None:
        """Write the current active universe to the marker file."""
        marker = PROJECT_DIR / ACTIVE_UNIVERSE_FILE
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(self._active_universe, encoding="utf-8")

    def _check_universe_switch(self) -> bool:
        """Return True if the active universe file changed (MCP triggered a switch)."""
        marker = PROJECT_DIR / ACTIVE_UNIVERSE_FILE
        if not marker.exists():
            return False
        uid = marker.read_text(encoding="utf-8").strip()
        if uid and uid != self._active_universe and (PROJECT_DIR / "output" / uid).is_dir():
            self._active_universe = uid
            return True
        return False

    # -- Status ----------------------------------------------------------

    @property
    def status_text(self) -> str:
        parts = []
        daemon_label = "Running" if self._daemon_alive else "Down"
        parts.append(f"Daemon: {daemon_label} ({self._active_universe})")
        if self._mcp_serving:
            parts.append("MCP: Serving")
        elif self._mcp_alive:
            parts.append("MCP: Loading")
        else:
            parts.append("MCP: Down")
        if self._tunnel_ok:
            parts.append("Tunnel: Connected")
        elif self._tunnel_alive:
            parts.append("Tunnel: Connecting")
        else:
            parts.append("Tunnel: Down")
        return " | ".join(parts)

    @property
    def hover_text(self) -> str:
        if self._daemon_alive and self._mcp_serving and self._tunnel_ok:
            return "Universe Server - Live at tinyassets.io/mcp"
        return f"Universe Server - {self._phase}"

    @property
    def icon_color(self) -> tuple:
        if self._daemon_alive and self._mcp_serving and self._tunnel_ok:
            return GREEN
        elif self._daemon_alive or self._mcp_alive or self._tunnel_alive:
            return YELLOW
        elif self._stop_event.is_set():
            return RED
        else:
            return GRAY

    # -- Process lifecycle -----------------------------------------------

    def start_daemon(self) -> None:
        """Launch the Fantasy Author daemon."""
        LOG_DIR.mkdir(exist_ok=True)

        log = open(LOG_DIR / "daemon.log", "a")
        log.write(f"\n--- Daemon start {time.strftime('%H:%M:%S')} ---\n")
        log.flush()

        universe_path = PROJECT_DIR / "output" / self._active_universe
        self.daemon_proc = subprocess.Popen(
            [
                sys.executable, "-m", "fantasy_author",
                "--universe", str(universe_path),
                "--no-tray",
            ],
            cwd=str(PROJECT_DIR),
            env=os.environ.copy(),
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def start_mcp(self) -> None:
        """Launch the MCP Universe Server."""
        LOG_DIR.mkdir(exist_ok=True)
        env = os.environ.copy()
        env["UNIVERSE_SERVER_BASE"] = "output"

        log = open(LOG_DIR / "mcp_server.log", "a")
        log.write(f"\n--- MCP start {time.strftime('%H:%M:%S')} ---\n")
        log.flush()

        self.mcp_proc = subprocess.Popen(
            [
                sys.executable, "-c",
                "from fantasy_author.universe_server import mcp; "
                f"mcp.run(transport='streamable-http', host='0.0.0.0', port={MCP_PORT})"
            ],
            cwd=str(PROJECT_DIR),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def start_tunnel(self) -> None:
        """Launch cloudflared tunnel."""
        LOG_DIR.mkdir(exist_ok=True)

        log = open(LOG_DIR / "tunnel.log", "a")
        log.write(f"\n--- Tunnel start {time.strftime('%H:%M:%S')} ---\n")
        log.flush()

        self.tunnel_proc = subprocess.Popen(
            ["cloudflared", "tunnel", "run", "--token", TUNNEL_TOKEN],
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def check_health(self) -> None:
        """Poll subprocess liveness + actual HTTP readiness."""
        # Process liveness
        self._daemon_alive = (
            self.daemon_proc is not None and self.daemon_proc.poll() is None
        )
        self._mcp_alive = (
            self.mcp_proc is not None and self.mcp_proc.poll() is None
        )
        self._tunnel_alive = (
            self.tunnel_proc is not None and self.tunnel_proc.poll() is None
        )

        # Daemon: just process alive is enough (no HTTP endpoint)
        if not self._daemon_alive and self.daemon_proc is not None:
            self._phase = "Daemon not running"

        # MCP server: probe localhost
        if self._mcp_alive and not self._mcp_serving:
            self._phase = "MCP server started, waiting for HTTP ready..."
            self._mcp_serving = self._probe_url(
                f"http://localhost:{MCP_PORT}/mcp", timeout=3
            )
            if self._mcp_serving:
                self._phase = "MCP server ready"
        elif not self._mcp_alive:
            self._mcp_serving = False

        # Tunnel: check public URL end-to-end
        if self._mcp_serving and self._tunnel_alive and not self._tunnel_ok:
            self._phase = "Verifying public endpoint..."
            self._tunnel_ok = self._probe_url(MCP_URL, timeout=5)
            if self._tunnel_ok:
                if self._daemon_alive:
                    self._phase = "Live"
                else:
                    self._phase = "MCP live, daemon down"
        elif not self._tunnel_alive:
            self._tunnel_ok = False

        # Summary phases
        if self._daemon_alive and self._mcp_serving and self._tunnel_ok:
            self._phase = "Live"
        elif not self._daemon_alive and not self._mcp_alive and not self._tunnel_alive:
            if not self._stop_event.is_set():
                self._phase = "All processes down, restarting..."

    @staticmethod
    def _probe_url(url: str, timeout: int = 3) -> bool:
        """Return True if the URL responds with ANY HTTP status."""
        try:
            resp = urlopen(url, timeout=timeout)  # noqa: S310
            resp.close()
            return True
        except URLError as e:
            if hasattr(e, "code"):
                return True
            return False
        except Exception:
            return False

    def _kill_daemon(self) -> None:
        """Terminate only the daemon process."""
        if self.daemon_proc and self.daemon_proc.poll() is None:
            self.daemon_proc.terminate()
            try:
                self.daemon_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.daemon_proc.kill()
        self.daemon_proc = None
        self._daemon_alive = False

    def kill_all(self) -> None:
        """Terminate all processes."""
        for proc in (self.daemon_proc, self.mcp_proc, self.tunnel_proc):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        self.daemon_proc = None
        self.mcp_proc = None
        self.tunnel_proc = None
        self._daemon_alive = False
        self._mcp_alive = False
        self._mcp_serving = False
        self._tunnel_alive = False
        self._tunnel_ok = False

    # -- Tray icon -------------------------------------------------------

    def _build_menu(self) -> Menu:
        return Menu(
            MenuItem(
                lambda _: self.status_text,
                action=None,
                enabled=False,
            ),
            Menu.SEPARATOR,
            MenuItem(
                "Open tinyassets.io/mcp",
                lambda: webbrowser.open(MCP_URL),
                enabled=lambda _: self._mcp_serving and self._tunnel_ok,
            ),
            MenuItem(
                "Open localhost:8001",
                lambda: webbrowser.open(f"http://localhost:{MCP_PORT}/mcp"),
                enabled=lambda _: self._mcp_serving,
            ),
            Menu.SEPARATOR,
            MenuItem(
                "Restart All",
                self._on_restart,
            ),
            MenuItem(
                "Open Logs",
                lambda: os.startfile(str(LOG_DIR)),  # noqa: S606
            ),
            MenuItem(
                "Quit",
                self._on_quit,
            ),
        )

    def _update_icon(self) -> None:
        """Refresh icon image and tooltip."""
        if self._icon is None:
            return
        self._icon.icon = make_icon(self.icon_color)
        self._icon.title = self.hover_text

    def _on_restart(self) -> None:
        """Kill and restart all processes."""
        self._phase = "Restarting..."
        self.kill_all()
        time.sleep(1)
        self._phase = "Starting Author daemon..."
        self.start_daemon()
        time.sleep(2)
        self._phase = "Starting MCP server on port 8001..."
        self.start_mcp()
        time.sleep(2)
        self._phase = "Starting Cloudflare tunnel..."
        self.start_tunnel()

    def _on_quit(self, icon=None, item=None) -> None:
        """Clean shutdown."""
        self._stop_event.set()
        self.kill_all()
        if self._icon:
            self._icon.stop()

    # -- Monitor thread --------------------------------------------------

    def _monitor_loop(self) -> None:
        """Background thread: poll health, update icon, auto-restart."""
        restart_backoff = 0
        self._stop_event.wait(3)

        while not self._stop_event.is_set():
            self.check_health()
            self._update_icon()

            if not self._stop_event.is_set():
                # Check if MCP triggered a universe switch
                if self._check_universe_switch():
                    self._phase = f"Switching to {self._active_universe}..."
                    self._kill_daemon()
                    time.sleep(1)
                    self.start_daemon()

                restarted = False
                if not self._daemon_alive and self.daemon_proc is not None:
                    self._phase = "Daemon died, restarting..."
                    self.start_daemon()
                    restarted = True
                if not self._mcp_alive and self.mcp_proc is not None:
                    self._phase = "MCP server died, restarting..."
                    self.start_mcp()
                    restarted = True
                if not self._tunnel_alive and self.tunnel_proc is not None:
                    self._phase = "Tunnel died, restarting..."
                    self.start_tunnel()
                    restarted = True

                if restarted:
                    restart_backoff = min(restart_backoff + 1, 6)
                    wait = 5 * (2 ** restart_backoff)
                elif self._daemon_alive and self._mcp_serving and self._tunnel_ok:
                    restart_backoff = 0
                    wait = 10
                else:
                    restart_backoff = 0
                    wait = 3

            self._stop_event.wait(wait)

    # -- Main entry ------------------------------------------------------

    def run(self) -> None:
        """Start everything and block until quit."""
        print("Starting Universe Server...")
        print(f"  Project:  {PROJECT_DIR}")
        print(f"  Universe: {self._active_universe}")
        print(f"  Endpoint: {MCP_URL}")
        print()

        # 1. Launch daemon
        self._phase = f"Starting Author daemon ({self._active_universe})..."
        self.start_daemon()
        print(f"  [OK] Author daemon starting ({self._active_universe})")

        time.sleep(2)

        # 2. Launch MCP server
        self._phase = "Starting MCP server on port 8001..."
        self.start_mcp()
        print("  [OK] MCP server starting on port 8001")

        time.sleep(2)

        # 3. Launch tunnel
        self._phase = "Starting Cloudflare tunnel..."
        self.start_tunnel()
        print("  [OK] Cloudflare tunnel starting")
        print()
        print("  Look for the 'U' icon in your system tray.")
        print("  Right-click it to quit.")

        # Start health monitor
        monitor = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor.start()

        # Create and run tray icon (blocks on main thread)
        self._icon = Icon(
            "Universe Server",
            make_icon(GRAY),
            title="Universe Server - Starting...",
            menu=self._build_menu(),
        )

        signal.signal(signal.SIGINT, lambda *_: self._on_quit())
        signal.signal(signal.SIGTERM, lambda *_: self._on_quit())

        self._icon.run()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mgr = UniverseServerManager()
    try:
        mgr.run()
    except KeyboardInterrupt:
        mgr.kill_all()
