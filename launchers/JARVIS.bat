@echo off
title JARVIS Portable Edition v5.10
cd /d "%~dp0.."

:: Read version from pyproject.toml
for /f "delims=" %%a in ('python -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])" 2^>nul') do set "JARVIS_VERSION=%%a"
if "%JARVIS_VERSION%"=="" set "JARVIS_VERSION=5.10"

echo ===================================================
echo   JARVIS Portable Edition v%JARVIS_VERSION%
echo   100%% portable -- zero install systeme
echo ===================================================
echo.

:: 0 -- Python portable
if not exist "%CD%\logs" mkdir "%CD%\logs"
set "PY=%CD%\portable_python\win\python.exe"

if not exist "%PY%" (
    echo [ERREUR] Python portable introuvable
    pause
    exit /b 1
)
echo  Python : %PY%

:: 1 -- Lancer JARVIS via module de lancement unifié (gère .env, logs, signaux)
::    L'installation des dépendances est déléguée à services.system.ensure_venv()
::    dans jarvis.py -- source unique, pas de race condition avec le shell.
echo  Imports : OK
echo.
echo ===================================================
echo   Demarrage de JARVIS...
echo   Attendez ~5s puis ouvrez http://localhost:8000
echo ===================================================
echo.

"%PY%" -m services.launcher_win >> "%CD%\logs\jarvis_core.log" 2>&1

if errorlevel 1 (
    echo [ERREUR] JARVIS s'est arrete avec le code %errorlevel%
    echo Voir logs\jarvis_core.log pour le detail
    pause
    exit /b 1
)

pause