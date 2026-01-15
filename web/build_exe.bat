@echo off
REM Build script to create web_browser.exe using PyInstaller
REM Run this from the web folder: build_exe.bat

echo Building web_browser.exe...
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Build the exe
pyinstaller web_browser.spec --distpath ..\bin --buildpath ..\build

echo.
echo Build complete!
echo Output: ..\bin\web_browser.exe
pause
