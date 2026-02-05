@echo off
setlocal

echo ================================
echo Building InkLink modules...
echo ================================

REM 1️⃣ 删除旧 bin 目录，避免提示删除确认
if exist .\bin\customer_service {
    echo Deleting old customer_service directory...
    rmdir /s /q bin\customer_service
}
if exist ./bin/floating_plugin  {
    echo Deleting old bin/floating_plugin directory...
    rmdir /s /q bin/floating_plugin
}
if exist ./bin/system_setting  {
    echo Deleting old bin/system_setting directory...
    rmdir /s /q bin/system_setting
}
if exist ./bin/third_party  {
    echo Deleting old bin/third_party directory...
    rmdir /s /q bin/third_party
}
if exist ./bin/design_center  {
    echo Deleting old bin/design_center  directory...
    rmdir /s /q bin/design_center
}


REM 2️⃣ 确保 PyInstaller 安装
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM 3️⃣ 打包
echo.
echo Running PyInstaller...
python -m PyInstaller ink2026.spec --distpath ./bin

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
)

REM 4️⃣ 自动签名（如果有证书）
for %%f in (
    bin\customer_service\customer_service.exe
    bin\floating_plugin\floating_plugin.exe
    bin\system_setting\system_setting.exe
    bin\third_party\third_party.exe
    bin\design_center\design_center.exe
) do (
    if exist %%f (
        echo Signing %%f...
        signtool sign /fd SHA256 /a %%f
    )
)

echo.
echo Build + Sign complete!
pause
