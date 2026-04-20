@echo off
chcp 65001 >nul
echo ============================================
echo   Update - Evidence Certifikatu
echo ============================================
echo.
echo Data (databaze, logy, .env) zustanou zachovany.
echo.
echo Pouziti: update.bat [NazevNSSMSluzby] [balicek.zip]
echo Priklad: update.bat CertifikatyApp certifikaty_deploy_20260415.zip
echo.

set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

set "NSSM_SERVICE=%~1"
set "ZIP_PATH=%~2"

if "%NSSM_SERVICE%"=="" (
    set /p NSSM_SERVICE="Nazev NSSM sluzby (Windows Services): "
)
if "%NSSM_SERVICE%"=="" (
    echo [CHYBA] Nazev sluzby je povinny!
    pause
    exit /b 1
)

if "%ZIP_PATH%"=="" (
    echo Hledam nejnovejsi balicek...
    for /f "delims=" %%F in ('dir /b /o-d certifikaty_deploy_*.zip 2^>nul') do (
        set "ZIP_PATH=%%F"
        goto :found_zip
    )
    echo [CHYBA] Zadny balicek certifikaty_deploy_*.zip nenalezen.
    pause
    exit /b 1
    :found_zip
    echo [INFO] Nalezen balicek: %ZIP_PATH%
)

if not exist "%ZIP_PATH%" (
    echo [CHYBA] Soubor '%ZIP_PATH%' nenalezen!
    pause
    exit /b 1
)

echo.
echo Konfigurace:
echo   NSSM Sluzba : %NSSM_SERVICE%
echo   Balicek     : %ZIP_PATH%
echo.

echo [1/5] Zastavuji sluzbu '%NSSM_SERVICE%' ...
nssm stop "%NSSM_SERVICE%" confirm
if errorlevel 1 (
    echo [CHYBA] Sluzbu se nepodarilo zastavit!
    echo         Over nazev: nssm status %NSSM_SERVICE%
    pause
    exit /b 1
)
echo [OK] Sluzba zastavena

echo [2/5] Extrahuji %ZIP_PATH% ...
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP_PATH%' -DestinationPath '%APP_DIR%' -Force"
if errorlevel 1 (
    echo [CHYBA] Extrakce selhala!
    nssm start "%NSSM_SERVICE%"
    pause
    exit /b 1
)
echo [OK] Soubory aktualizovany

echo [3/5] Instaluji zavislosti ...
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Virtualni prostredi nenalezeno, vytvarim...
    python -m venv venv
)
venv\Scripts\python.exe -m pip install --no-index --find-links=dependencies -r requirements.txt --quiet
if errorlevel 1 (
    echo [VAROVANI] Instalace zavislosti selhala. Pokracuji...
) else (
    echo [OK] Zavislosti aktualizovany
)

echo [4/5] Migrace databazi (live, uat, sit, prelive) ...
venv\Scripts\python.exe -c "from app import create_app,db; app=create_app(); ctx=app.app_context(); ctx.push(); meta=db.metadatas.get('live') if hasattr(db,'metadatas') else db.metadata; [meta.create_all(bind=db.engines[e]) or print('[OK] DB: '+e) for e in ('live','uat','sit','prelive')]; ctx.pop()"
if errorlevel 1 (
    echo [VAROVANI] DB migrace selhala - tabulky budou overeny pri startu.
) else (
    echo [OK] Databaze migrovany
)

echo [5/5] Spoustim sluzbu '%NSSM_SERVICE%' ...
nssm start "%NSSM_SERVICE%"
if errorlevel 1 (
    echo [CHYBA] Sluzbu se nepodarilo spustit!
    pause
    exit /b 1
)
echo [OK] Sluzba spustena

echo.
if exist "VERSION.txt" (
    echo Nasazena verze:
    type VERSION.txt
)

echo.
echo ============================================
echo   Update dokoncen!
echo ============================================
echo.
pause