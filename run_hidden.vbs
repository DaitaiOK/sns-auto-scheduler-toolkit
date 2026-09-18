' ウィンドウを表示せずにスケジューラーをバックグラウンド実行するためのラッパー。
' タスクスケジューラーの「プログラム開始」にこのファイルを指定してください。
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
WshShell.Run chr(34) & scriptDir & "\run_scheduler.bat" & chr(34), 0
Set WshShell = Nothing
