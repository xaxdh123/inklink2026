@echo off
setlocal
chcp 65001 >nul
:: 检查参数数量
if "%~4"=="" (
    echo Usage: %0 ^<source_folder^> ^<destination_folder^> ^<executable_path^> ^<process_name^>
    exit /b
)

set "SOURCE_FOLDER=%~1"
set "DESTINATION_FOLDER=%~2"
set "EXECUTABLE=%~3"
set "PROCESS_NAME=%~4"

echo Closing the process if it is running...
taskkill /IM "%PROCESS_NAME%" /F >nul 2>&1
if %errorlevel% == 0 (
    echo WScript.Echo "Process closed successfully." > tempmsg.vbs
) else (
    echo WScript.Echo "Process was not running or failed to close." > tempmsg.vbs
)
wscript //B tempmsg.vbs
del tempmsg.vbs

timeout /t 3 /nobreak >nul

echo Deleting old version files...
del /F /Q "%DESTINATION_FOLDER%\\%PROCESS_NAME%" >nul 2>&1

echo Copying files from source to destination...
xcopy "%SOURCE_FOLDER%" "%DESTINATION_FOLDER%" /E /I /Y /Q
echo WScript.Echo "Files copied successfully." > tempmsg.vbs
wscript //B tempmsg.vbs
del tempmsg.vbs

echo Starting the application...
start "" "%EXECUTABLE%"
echo WScript.Echo "Application started." > tempmsg.vbs
wscript //B tempmsg.vbs
del tempmsg.vbs

echo Operation completed.
endlocal
exit