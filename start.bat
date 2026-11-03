@echo off
setlocal EnableExtensions
chcp 65001 >nul
title 手勢控制滑鼠
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "STAMP=.venv\requirements.installed"

rem ---- 1. 檢查虛擬環境，壞掉或不存在就重建 ----
if exist "%VENV_PY%" (
    "%VENV_PY%" -c "import sys" >nul 2>&1 || (
        echo 虛擬環境無法使用，重新建立...
        rmdir /s /q .venv
    )
)

if exist "%VENV_PY%" goto :check_deps
call :find_python
if not defined PY_CMD goto :no_python
echo 第一次執行：建立虛擬環境（使用 %PY_CMD%）...
%PY_CMD% -m venv .venv
if errorlevel 1 goto :venv_failed

:check_deps

rem ---- 2. requirements.txt 有變動才安裝依賴 ----
set "NEED_INSTALL=1"
if exist "%STAMP%" (
    fc /b requirements.txt "%STAMP%" >nul 2>&1 && set "NEED_INSTALL=0"
)
if "%NEED_INSTALL%"=="1" (
    echo 安裝套件中，第一次大約需要幾分鐘...
    "%VENV_PY%" -m pip install --upgrade pip >nul
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 goto :install_failed
    copy /y requirements.txt "%STAMP%" >nul
)

rem ---- 3. 啟動 ----
echo 啟動手勢控制... 在預覽視窗按 q 或 Esc 結束。
"%VENV_PY%" -m gesture_mouse %*
if errorlevel 1 (
    echo.
    echo 程式異常結束，請看上面的錯誤訊息。
    pause
)
exit /b

rem ---- 找 Python 3.10 ~ 3.12 ----
:find_python
set "PY_CMD="
for %%V in (3.12 3.11 3.10) do (
    if not defined PY_CMD (
        py -%%V -c "import sys" >nul 2>&1 && set "PY_CMD=py -%%V"
    )
)
if not defined PY_CMD (
    python -c "import sys; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)" >nul 2>&1 && set "PY_CMD=python"
)
exit /b

:no_python
echo.
echo 找不到 Python 3.10 ~ 3.12。
echo 請到 https://www.python.org/downloads/ 下載 Python 3.12，
echo 安裝時記得勾選「Add python.exe to PATH」，裝好後再雙擊 start.bat。
pause
exit /b 1

:venv_failed
echo.
echo 建立虛擬環境失敗，請看上面的錯誤訊息。
pause
exit /b 1

:install_failed
echo.
echo 安裝套件失敗。請確認網路連線，然後再雙擊 start.bat 重試。
pause
exit /b 1
