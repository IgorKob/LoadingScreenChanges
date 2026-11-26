@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [1/2] Установка зависимостей...
python -m pip install --upgrade pillow pyinstaller
if errorlevel 1 goto error
echo [2/2] Сборка EXE...
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name BlitzLoadingChanger ^
  main.py
if errorlevel 1 goto error
echo.
echo Готово: dist\BlitzLoadingChanger.exe
pause
exit /b 0
:error
echo.
echo Сборка не удалась. Проверьте, что установлен Python 3.10+ и доступен pip.
pause
exit /b 1
