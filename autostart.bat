@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

rem 開機自動啟動的開關：沒開就開，已開就關
set "GM_TARGET=%~dp0start.bat"
set "GM_DIR=%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Join-Path ([Environment]::GetFolderPath('Startup')) '手勢控制滑鼠.lnk';" ^
  "if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p; Write-Host '已關閉開機自動啟動。' }" ^
  "else { $s = (New-Object -ComObject WScript.Shell).CreateShortcut($p);" ^
  "  $s.TargetPath = $env:GM_TARGET; $s.WorkingDirectory = $env:GM_DIR; $s.WindowStyle = 7;" ^
  "  $s.Description = '用鏡頭手勢控制滑鼠'; $s.Save();" ^
  "  Write-Host '已開啟開機自動啟動。再雙擊一次 autostart.bat 可以關閉。' }"
if errorlevel 1 echo 設定失敗，請看上面的錯誤訊息。
pause
