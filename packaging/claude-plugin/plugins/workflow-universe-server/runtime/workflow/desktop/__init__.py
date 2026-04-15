"""Desktop application -- system tray, dashboard, notifications, launcher.

Re-exports
----------
TrayApp              -- pystray system tray icon (run_detached)
DashboardHandler     -- processes graph stream events for display
NotificationManager  -- toast / balloon notifications
LauncherApp          -- tkinter launcher GUI
create_icon_image    -- generate a branded icon PIL Image
generate_icon        -- generate multi-size .ico file
"""

from workflow.desktop.dashboard import DashboardHandler, DashboardMetrics
from workflow.desktop.host_tray import HostTrayService
from workflow.desktop.icon_gen import create_icon_image, generate_icon
from workflow.desktop.launcher import LauncherApp
from workflow.desktop.notifications import NotificationManager
from workflow.desktop.tray import TrayApp

__all__ = [
    "DashboardHandler",
    "DashboardMetrics",
    "HostTrayService",
    "LauncherApp",
    "NotificationManager",
    "TrayApp",
    "create_icon_image",
    "generate_icon",
]
