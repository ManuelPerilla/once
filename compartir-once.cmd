@echo off
setlocal
set "ONCE_PAUSE="
if "%~1"=="" set "ONCE_PAUSE=1"
cd /d "%~dp0"
if errorlevel 1 goto missing_directory

set "ONCE_PYTHON="
if not exist ".venv\Scripts\python.exe" goto try_launcher
".venv\Scripts\python.exe" -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul
if errorlevel 1 goto try_launcher
set "ONCE_PYTHON=.venv\Scripts\python.exe"
goto run

:try_launcher
py -3.12 -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul
if errorlevel 1 goto try_python
set "ONCE_PYTHON=py -3.12"
goto run

:try_python
python -c "import sys; sys.exit(sys.version_info < (3, 12))" >nul 2>nul
if errorlevel 1 goto missing_python
set "ONCE_PYTHON=python"

:run
echo ONCE - Acceso desde otros equipos
if "%~1"=="" (
    %ONCE_PYTHON% -m scripts.network lan
) else (
    %ONCE_PYTHON% -m scripts.network %*
)
set "ONCE_EXIT=%ERRORLEVEL%"
goto finish

:missing_python
echo Instala Python 3.12 o posterior y vuelve a ejecutar compartir-once.cmd.
set "ONCE_EXIT=1"
goto finish

:missing_directory
echo No se pudo abrir la carpeta de ONCE.
set "ONCE_EXIT=1"

:finish
if defined ONCE_PAUSE pause
exit /b %ONCE_EXIT%
