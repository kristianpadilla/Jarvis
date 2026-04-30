Set objShell = CreateObject("WScript.Shell")
objShell.Run "rundll32.exe powrprof.dll,SetSuspendState 0,1,0", 0, False
