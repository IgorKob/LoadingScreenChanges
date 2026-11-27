@echo off
cd /d "%~dp0"
echo [1/2] Installing dependencies...
python -m pip install --upgrade pillow PySide6 pyinstaller
if errorlevel 1 goto error
echo [2/2] Building single-file EXE...
python -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin ^
  --runtime-tmpdir ".blc_runtime" ^
  --name BlitzCustom ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  main.py
if errorlevel 1 goto error
echo.
echo Done: dist\BlitzCustom.exe
pause
exit /b 0
:error
echo.
echo Build failed. Check that Python 3.10+ and pip are available.
pause
exit /b 1
