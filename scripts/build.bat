@echo off
setlocal

.venv\Scripts\python.exe -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name MultiTapKey ^
    --paths . ^
    --add-data "multitapkey\i18n\translations;multitapkey\i18n\translations" ^
    multitapkey\__main__.py

if errorlevel 1 (
    echo BUILD FAILED
    exit /b 1
)

echo BUILD SUCCESS
echo Output: dist\MultiTapKey.exe

endlocal
