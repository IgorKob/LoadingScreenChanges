@echo off
cd /d "%~dp0"
echo [1/2] Installing dependencies...
python -m pip install --upgrade pillow PySide6 pyinstaller
if errorlevel 1 goto error
echo [2/2] Building EXE (folder mode, no unpacking at startup)...
python -m PyInstaller --noconfirm --clean --onedir --windowed --uac-admin ^
  --name BlitzCustom ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  main.py
if errorlevel 1 goto error
echo.
echo Done: dist\BlitzCustom\BlitzCustom.exe
pause
exit /b 0
:error
echo.
echo Build failed. Check that Python 3.10+ and pip are available.
pause
exit /b 1
