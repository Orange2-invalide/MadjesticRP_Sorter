@echo off
chcp 65001 >nul
echo.
echo ========================================
echo    Сборка MajesticSorter v4.0
echo ========================================
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Проверяем иконку
if not exist "icon.ico" (
    echo [!] icon.ico не найден!
    echo     Создайте иконку или скачайте готовую.
    pause
    exit /b 1
)

echo [1/3] Удаляю старую сборку...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo [2/3] Собираю .exe...
echo.

pyinstaller --onefile --windowed --name MajesticSorter --icon=icon.ico ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=customtkinter ^
    --hidden-import=rapidocr_onnxruntime ^
    --hidden-import=onnxruntime ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=loguru ^
    --hidden-import=yaml ^
    --collect-all customtkinter ^
    --collect-all rapidocr_onnxruntime ^
    --collect-data rapidocr_onnxruntime ^
    main.py

echo.
echo ========================================
if exist "dist\MajesticSorter.exe" (
    echo [3/3] ГОТОВО!
    echo.
    echo    Файл: dist\MajesticSorter.exe
    for %%A in ("dist\MajesticSorter.exe") do echo    Размер: %%~zA байт
    echo.
    echo    Данные будут храниться в:
    echo    %%APPDATA%%\MajesticSorter\
    echo.
    explorer dist
) else (
    echo [X] ОШИБКА сборки!
)
echo ========================================
pause@echo off
chcp 65001 >nul
echo.
echo ========================================
echo    Сборка MajesticSorter v4.0
echo ========================================
echo.

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Проверяем иконку
if not exist "icon.ico" (
    echo [!] icon.ico не найден!
    echo     Создайте иконку или скачайте готовую.
    pause
    exit /b 1
)

echo [1/3] Удаляю старую сборку...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo [2/3] Собираю .exe...
echo.

pyinstaller --onefile --windowed --name MajesticSorter --icon=icon.ico ^
    --hidden-import=PIL._tkinter_finder ^
    --hidden-import=customtkinter ^
    --hidden-import=rapidocr_onnxruntime ^
    --hidden-import=onnxruntime ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=loguru ^
    --hidden-import=yaml ^
    --collect-all customtkinter ^
    --collect-all rapidocr_onnxruntime ^
    --collect-data rapidocr_onnxruntime ^
    main.py

echo.
echo ========================================
if exist "dist\MajesticSorter.exe" (
    echo [3/3] ГОТОВО!
    echo.
    echo    Файл: dist\MajesticSorter.exe
    for %%A in ("dist\MajesticSorter.exe") do echo    Размер: %%~zA байт
    echo.
    echo    Данные будут храниться в:
    echo    %%APPDATA%%\MajesticSorter\
    echo.
    explorer dist
) else (
    echo [X] ОШИБКА сборки!
)
echo ========================================
pause
