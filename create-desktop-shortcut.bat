@echo off
:: Creates a desktop shortcut for the Universe Server launcher
:: Run this ONCE, then delete it

set SCRIPT_PATH=%~dp0start-universe-server.vbs
set SHORTCUT_PATH=%USERPROFILE%\Desktop\Universe Server.lnk

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT_PATH%'); $sc.TargetPath = 'wscript.exe'; $sc.Arguments = '%SCRIPT_PATH%'; $sc.WorkingDirectory = '%~dp0'; $sc.Description = 'Start Universe Server - https://tinyassets.io/mcp'; $sc.WindowStyle = 7; $sc.Save()"

if exist "%SHORTCUT_PATH%" (
    echo.
    echo  Done! "Universe Server" shortcut created on your Desktop.
    echo  You can delete this setup script now.
    echo.
) else (
    echo  Failed to create shortcut. You can manually create one
    echo  pointing to: %SCRIPT_PATH%
)
pause
