@echo off
REM run_integration_tests.bat — Lance les tests d'integration avec le Ollama portable
REM Usage: scripts\run_integration_tests.bat

setlocal enabledelayedexpansion
set "ROOT=%~dp0.."
set "OLLAMA_BIN=%ROOT%\bin\win\ollama.exe"
set "OLLAMA_PORT=11436"
set "OLLAMA_HOST=127.0.0.1:%OLLAMA_PORT%"
set "OLLAMA_MODELS=%ROOT%\models\ollama"

echo === Integration Tests JARVIS ===
echo Ollama : %OLLAMA_BIN%
echo Port   : %OLLAMA_PORT%

if not exist "%OLLAMA_BIN%" (
    echo ERREUR: Ollama introuvable dans %OLLAMA_BIN%
    exit /b 1
)

if not exist "%OLLAMA_MODELS%" mkdir "%OLLAMA_MODELS%"

REM Tuer les processus Ollama residuels
taskkill /f /im ollama.exe 2>nul
timeout /t 2 /nobreak >nul

echo Demarrage d'Ollama...
start "Ollama" "%OLLAMA_BIN%" serve

REM Attendre qu'Ollama soit pret
echo Attente d'Ollama...
for /l %%i in (1,1,30) do (
    curl -s http://%OLLAMA_HOST%/api/tags >nul 2>&1
    if not errorlevel 1 (
        echo Ollama pret (tentative %%i)
        goto :run_tests
    )
    timeout /t 2 /nobreak >nul
)

echo ERREUR: Ollama n'a pas demarre
exit /b 1

:run_tests
echo.
echo Execution des tests d'integration...
cd /d "%ROOT%"
python -m pytest tests\test_integration_ollama.py -v --tb=long
set "EXIT_CODE=%ERRORLEVEL%"

REM Nettoyage
echo.
echo Arret d'Ollama...
taskkill /f /im ollama.exe 2>nul

exit /b %EXIT_CODE%
