' Silent launcher - no console window flicker
' Runs start-workflow-server.bat completely hidden

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd /c start-workflow-server.bat", 0, False
