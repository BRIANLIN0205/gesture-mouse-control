@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem 在桌面建立「手勢控制滑鼠」捷徑，指向 start.bat
set "GM_TARGET=%~dp0start.bat"
set "GM_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d = [Environment]::GetFolderPath('Desktop');" ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d '手勢控制滑鼠.lnk'));" ^
  "$s.TargetPath = $env:GM_TARGET; $s.WorkingDirectory = $env:GM_DIR;" ^
  "$s.Description = '用鏡頭手勢控制滑鼠'; $s.Save();" ^
  "Write-Host ('已在桌面建立捷徑：' + $s.FullName)"
if errorlevel 1 echo 建立捷徑失敗，請看上面的錯誤訊息。
pause
