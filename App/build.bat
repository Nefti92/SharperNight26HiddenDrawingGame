@echo off
setlocal
cd /d "%~dp0"

set "APP_NAME=NotteDeiRicercatori"
set "PY_EXE="
set "LOG_FILE=build_log.txt"

cls
echo ==========================================
echo BUILD %APP_NAME%
echo ==========================================
echo.

> "%LOG_FILE%" echo BUILD STARTED
>> "%LOG_FILE%" echo Directory: %cd%
>> "%LOG_FILE%" echo Date and time: %date% %time%
>> "%LOG_FILE%" echo.

echo [1/9] Looking for Python 3.11...
>> "%LOG_FILE%" echo [1/9] Looking for Python 3.11...

if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
)

if not defined PY_EXE (
    for /f "delims=" %%p in ('where python 2^>nul') do (
        if not defined PY_EXE set "PY_EXE=%%p"
    )
)

if not defined PY_EXE (
    echo.
    echo ERROR: Python not found.
    >> "%LOG_FILE%" echo ERROR: Python not found.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('"%PY_EXE%" --version 2^>^&1') do set "PY_VERSION=%%v"

echo Python found: %PY_EXE%
echo Version: %PY_VERSION%
>> "%LOG_FILE%" echo Python found: %PY_EXE%
>> "%LOG_FILE%" echo Version: %PY_VERSION%

echo %PY_VERSION% | findstr /b "3.11." >nul
if errorlevel 1 (
    echo.
    echo ERROR: Python 3.11 is required.
    echo Detected version: %PY_VERSION%
    >> "%LOG_FILE%" echo ERROR: Incorrect Python version: %PY_VERSION%
    pause
    exit /b 1
)

echo.
echo [2/9] Checking required files...
>> "%LOG_FILE%" echo [2/9] Checking required files...

if not exist "src\main.py" (
    echo ERROR: src\main.py not found.
    >> "%LOG_FILE%" echo ERROR: src\main.py not found.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.
    >> "%LOG_FILE%" echo ERROR: requirements.txt not found.
    pause
    exit /b 1
)

for %%F in (Animali.png Natura.png Feste.png Fantasy.png icona.ico) do (
    if not exist "assets\%%F" (
        echo ERROR: assets\%%F not found.
        >> "%LOG_FILE%" echo ERROR: assets\%%F not found.
        goto :missing_assets
    )
)

echo All required files found.

echo.
echo [3/9] Cleaning previous build...
>> "%LOG_FILE%" echo [3/9] Cleaning previous build...

if exist ".venv" rmdir /s /q ".venv"
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

echo Cleanup completed.

echo.
echo [4/9] Creating virtual environment...
>> "%LOG_FILE%" echo [4/9] Creating virtual environment...

"%PY_EXE%" -m venv .venv >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :venv_error

echo Virtual environment created.

echo.
echo [5/9] Upgrading pip...
>> "%LOG_FILE%" echo [5/9] Upgrading pip...

".venv\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :pip_error

echo Pip upgraded.

echo.
echo [6/9] Installing dependencies...
>> "%LOG_FILE%" echo [6/9] Installing dependencies...

".venv\Scripts\python.exe" -m pip install -r requirements.txt >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :requirements_error

echo Dependencies installed.

echo.
echo [7/9] Building executable...
>> "%LOG_FILE%" echo [7/9] Building executable...
echo Embedding EXE icon: %CD%\assets\icona.ico
>> "%LOG_FILE%" echo EXE icon: %CD%\assets\icona.ico

".venv\Scripts\python.exe" -m PyInstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --icon "%CD%\assets\icona.ico" ^
    --add-data "assets;assets" ^
    src\main.py >> "%LOG_FILE%" 2>&1

if errorlevel 1 goto :build_error

echo Executable created.

echo.
echo [8/9] Verifying embedded Windows icon...
>> "%LOG_FILE%" echo [8/9] Verifying embedded Windows icon...

".venv\Scripts\python.exe" -c "import pefile; p=pefile.PE(r'dist\%APP_NAME%.exe', fast_load=True); p.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_RESOURCE']]); r=getattr(p, 'DIRECTORY_ENTRY_RESOURCE', None); ids={item.id for item in r.entries} if r is not None else set(); assert {3,14}.issubset(ids), 'EXE is missing Windows icon resources'; print('RT_ICON and RT_GROUP_ICON resources found')" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :icon_error

echo Windows icon resources verified.

echo.
echo [9/9] Verifying output file...
>> "%LOG_FILE%" echo [9/9] Verifying output file...

if not exist "dist\%APP_NAME%.exe" (
    echo ERROR: Executable not found.
    >> "%LOG_FILE%" echo ERROR: Executable not found.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo BUILD COMPLETED SUCCESSFULLY
echo ==========================================
echo.
echo Output file:
echo dist\%APP_NAME%.exe
echo.
echo Log file:
echo %LOG_FILE%
echo.
echo If Explorer still shows an old icon, refresh the folder or rename the EXE once.

>> "%LOG_FILE%" echo.
>> "%LOG_FILE%" echo BUILD COMPLETED SUCCESSFULLY
>> "%LOG_FILE%" echo Output file: dist\%APP_NAME%.exe

pause
exit /b 0

:venv_error
echo.
echo ERROR: Failed to create the virtual environment.
goto :show_error

:pip_error
echo.
echo ERROR: Failed to upgrade pip.
goto :show_error

:requirements_error
echo.
echo ERROR: Failed to install dependencies.
goto :show_error

:build_error
echo.
echo ERROR: Failed to build the executable.
goto :show_error

:icon_error
echo.
echo ERROR: The EXE was created, but its icon resources could not be verified.
goto :show_error

:show_error
echo.
echo Check the %LOG_FILE% file for details.
echo.
type "%LOG_FILE%"
pause
exit /b 1

:missing_assets
echo.
echo Check the files in the assets folder and try again.
pause
exit /b 1
