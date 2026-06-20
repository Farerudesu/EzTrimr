@echo off
echo ===================================================
echo Building EZTrimr Release Executable (Nuitka)...
echo ===================================================

:: Ensure python from .venv is used
set PYTHON_EXE=.venv\Scripts\python.exe

if not exist %PYTHON_EXE% (
    echo Error: Virtual environment python.exe not found at %PYTHON_EXE%
    exit /b 1
)

echo.
echo [1/4] Generating assets/icon.ico using tools/make_icon.py...
%PYTHON_EXE% tools/make_icon.py

if errorlevel 1 (
    echo Error: Icon generation failed.
    exit /b 1
)

echo.
echo [2/4] Cleaning up previous build directories...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [3/4] Detecting FFmpeg and FFprobe locations...
for /f "delims=" %%i in ('%PYTHON_EXE% -c "import config; print(config.FFMPEG_PATH)"') do set FFMPEG_PATH=%%i
for /f "delims=" %%i in ('%PYTHON_EXE% -c "import config; print(config.FFPROBE_PATH)"') do set FFPROBE_PATH=%%i

echo FFmpeg path: %FFMPEG_PATH%
echo FFprobe path: %FFPROBE_PATH%

echo.
echo [4/4] Running Nuitka compiler...
%PYTHON_EXE% -m nuitka ^
    --standalone ^
    --windows-disable-console ^
    --enable-plugin=pyqt6 ^
    --include-qt-plugins=multimedia ^
    --windows-icon-from-ico=assets/icon.ico ^
    --include-data-dir=assets=assets ^
    --include-data-file="%FFMPEG_PATH%"=ffmpeg.exe ^
    --include-data-file="%FFPROBE_PATH%"=ffprobe.exe ^
    --product-name=EZTrimr ^
    --company-name=EZTrimr ^
    --file-description="EZTrimr Video and Audio Trimmer" ^
    --file-version=1.0.0.0 ^
    --product-version=1.0.0.0 ^
    --copyright="Copyright 2026 EZTrimr" ^
    --assume-yes-for-downloads ^
    --output-dir=dist ^
    main.py

if errorlevel 1 (
    echo Error: Nuitka build failed.
    exit /b 1
)

echo.
echo [5/5] Moving program files to distribution root...
if exist dist\main.dist (
    xcopy /e /y dist\main.dist\* dist\ >nul
    rmdir /s /q dist\main.dist
    if exist dist\main.exe (
        rename dist\main.exe EZTrimr.exe
    )
)
if exist dist\main.build rmdir /s /q dist\main.build

:: Copy FFmpeg DLLs if it is a shared build
for %%A in ("%FFMPEG_PATH%") do set FFMPEG_DIR=%%~dpA
if exist "%FFMPEG_DIR%*.dll" (
    echo Copying FFmpeg shared DLLs from %FFMPEG_DIR%...
    copy /y "%FFMPEG_DIR%*.dll" dist\ >nul
)

:: Copy PyQt6 Multimedia plugins if not already present
if not exist "dist\PyQt6\Qt6\plugins\multimedia" (
    if exist ".venv\Lib\site-packages\PyQt6\Qt6\plugins\multimedia" (
        echo Copying PyQt6 Multimedia plugins manually...
        xcopy /e /y /i ".venv\Lib\site-packages\PyQt6\Qt6\plugins\multimedia" "dist\PyQt6\Qt6\plugins\multimedia" >nul
    )
)

echo.
echo [6/7] Creating Portable ZIP (EZTrimr-portable.zip)...
if exist EZTrimr-portable.zip del /f /q EZTrimr-portable.zip
powershell -Command "Compress-Archive -Path dist\* -DestinationPath EZTrimr-portable.zip -Force"

echo.
echo [7/7] Compiling Setup Installer (EZTrimr-Setup.exe)...
if exist dist_setup rmdir /s /q dist_setup
%PYTHON_EXE% -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-disable-console ^
    --enable-plugin=pyqt6 ^
    --windows-icon-from-ico=assets/icon.ico ^
    --include-data-file=EZTrimr-portable.zip=EZTrimr-portable.zip ^
    --product-name="EZTrimr Setup" ^
    --company-name=EZTrimr ^
    --file-description="EZTrimr Setup Installer" ^
    --file-version=1.0.0.0 ^
    --product-version=1.0.0.0 ^
    --copyright="Copyright 2026 EZTrimr" ^
    --assume-yes-for-downloads ^
    --output-dir=dist_setup ^
    tools/installer.py

if errorlevel 1 (
    echo Error: Installer build failed.
    exit /b 1
)

if exist dist_setup\installer.exe (
    move /y dist_setup\installer.exe dist\EZTrimr-Setup.exe >nul
)
if exist dist_setup rmdir /s /q dist_setup

echo.
echo ===================================================
echo Build completed successfully!
echo Executable: dist\EZTrimr.exe
echo Portable ZIP: EZTrimr-portable.zip
echo Setup Installer: dist\EZTrimr-Setup.exe
echo ===================================================
