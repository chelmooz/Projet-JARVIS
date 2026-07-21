@echo off
title JARVIS Portable Edition v5.4
cd /d "%~dp0.."

echo ===================================================
echo   JARVIS Portable Edition v5.4
echo   100%% portable — zero install systeme
echo ===================================================
echo.

:: 0 — Charger .env si present (surcharge OLLAMA_HOST, JARVIS_PORT...)
:: On ignore les lignes de commentaire (eol=#) et les lignes sans '='
:: (une valeur contenant '=' est conservee grace a tokens=1,*).
if exist ".env" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in (".env") do (
        if not "%%b"=="" (
            set "%%a=%%b"
        )
    )
)

:: 1 — Python portable
if not exist "%CD%\logs" mkdir "%CD%\logs"
set "PY=%CD%\portable_python\win\python.exe"

if not exist "%PY%" (
    echo [ERREUR] Python portable introuvable
    pause
    exit /b 1
)
echo  Python : %PY%

:: 2 — Lancer JARVIS (l'installation des dependances est deleguee a
::    services.system.ensure_venv() dans jarvis.py — source unique, pas de
::    race condition avec le shell).
echo  Imports : OK
echo.
echo ===================================================
echo   Demarrage de JARVIS...
echo   Attendez ~5s puis ouvrez http://localhost:8000
echo ===================================================
echo.

"%PY%" "%CD%\jarvis.py" 2>"%CD%\logs\jarvis_core.log"
if errorlevel 1 (
    echo [ERREUR] JARVIS s'est arrete avec le code %errorlevel%
    echo Voir logs\jarvis_core.log pour le detail
    pause
    exit /b 1
)

pause
