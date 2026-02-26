@echo off
setlocal
timeout /t 2 >nul

echo Killing processes...
if not "%~3"=="" (
    taskkill /f /im "%~nx3" >nul 2>&1
)

echo Copying files from %1 to %2 ...
xcopy /s /y /i "%~1\*.*" "%~2\" >nul
if errorlevel 1 (
    echo Copy failed!
    pause
    exit /b 1
)

echo Starting %3 ...
start "" "%~3"
exit
   
