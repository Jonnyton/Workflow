' Silent launcher - no console window flicker
' Runs start-universe-server.bat completely hidden

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd /c start-universe-server.bat", 0, False
