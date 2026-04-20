@echo off
chcp 65001 >nul
echo ============================================
echo   Baleni aplikace pro prenos na server
echo ============================================
echo.

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

REM Git hash
for /f %%G in ('git rev-parse --short HEAD 2^>nul') do set "GIT_HASH=%%G"
if "%GIT_HASH%"=="" set "GIT_HASH=unknown"

REM Datum pres PowerShell (locale-independent)
for /f %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "BUILD_DATE=%%D"
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format HH:mm"') do set "BUILD_TIME=%%T"

REM VERSION.txt
echo [INFO] Generuji VERSION.txt...
(echo Verze:    %GIT_HASH%) > VERSION.txt
(echo Zabaleno: %BUILD_DATE% %BUILD_TIME%) >> VERSION.txt
echo [OK] VERSION.txt (%GIT_HASH%)

REM Zavislosti
echo [INFO] Stahuji zavislosti do dependencies/ ...
if not exist "dependencies" mkdir dependencies
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -m pip download -r requirements.txt -d dependencies --quiet
) else (
    python -m pip download -r requirements.txt -d dependencies --quiet
)
if errorlevel 1 (
    echo [VAROVANI] Stazeni zavislosti selhalo, pouzivam existujici obsah dependencies/
) else (
    echo [OK] Zavislosti aktualizovany
)

REM ZIP
set "ZIPNAME=certifikaty_deploy_%BUILD_DATE%_%GIT_HASH%.zip"
echo [INFO] Vytvarim %ZIPNAME% ...
if exist "%ZIPNAME%" del "%ZIPNAME%"

powershell -NoProfile -Command "Compress-Archive -Force -Path 'app','static','dependencies','app.py','config.py','requirements.txt','deploy.bat','update.bat','package.bat','VERSION.txt','DEPLOY.md','.env.example' -DestinationPath '%ZIPNAME%'"

if not exist "%ZIPNAME%" (
    echo [CHYBA] Nepodarilo se vytvorit ZIP!
    pause
    exit /b 1
)

for /f %%S in ('powershell -NoProfile -Command "[math]::Round((Get-Item ''%ZIPNAME%'').Length / 1MB, 1)"') do set "ZIP_MB=%%S"
echo [OK] Balicek vytvoren: %ZIPNAME% (%ZIP_MB% MB)
echo.
echo Obsah: app\, static\, dependencies\, *.py, *.txt, deploy.bat, update.bat
echo Vynechano: instance\ (databaze), logs\, uploads\, .env
echo.
echo Na serveru:
echo   update.bat CertifikatyPool %ZIPNAME% evidence_cert
echo.
pause
