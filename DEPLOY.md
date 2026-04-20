# Nasazení aplikace — Evidence certifikátů

Tento dokument popisuje celý proces: od první instalace na čistý server přes pravidelné aktualizace
až po migraci existující instalace (přejmenování TEST → UAT, přidání SIT a PRELIVE).

---

## Obsah

1. [Prostředí](#1-prostředí)
2. [Požadavky](#2-požadavky)
3. [Balení aplikace pro přenos (dev PC)](#3-balení-aplikace-pro-přenos-dev-pc)
4. [První instalace na novém serveru](#4-první-instalace-na-novém-serveru)
5. [Konfigurace IIS](#5-konfigurace-iis)
6. [Konfigurace aplikace (.env)](#6-konfigurace-aplikace-env)
7. [Aktualizace na novou verzi](#7-aktualizace-na-novou-verzi)
8. [Migrace existující instalace](#8-migrace-existující-instalace)
9. [Řešení problémů](#9-řešení-problémů)

---

## 1. Prostředí

Aplikace spravuje certifikáty napříč čtyřmi prostředími. Každé prostředí má vlastní SQLite databázi ve složce `instance/`.

| Prostředí | Soubor databáze              | Popis                              |
|-----------|------------------------------|------------------------------------|
| `live`    | `instance/certifikaty.db`    | Produkční data                     |
| `uat`     | `instance/certifikaty_uat.db`| User Acceptance Testing (dříve TEST) |
| `sit`     | `instance/certifikaty_sit.db`| System Integration Testing         |
| `prelive` | `instance/certifikaty_prelive.db` | Předprodukční prostředí       |

> **Poznámka:** Databázové soubory se **nikdy** neukládají do balíčku ani nepřepisují při aktualizaci.

---

## 2. Požadavky

| Komponenta         | Verze          | Poznámka                                        |
|--------------------|----------------|-------------------------------------------------|
| Windows Server     | 2016 / 2019 / 2022 |                                             |
| IIS                | 10+            | Role `Web Server (IIS)`                         |
| IIS URL Rewrite    | 2.1+           | Z offline instalátoru (součástí flash disku)    |
| ARR                | 3.0+           | Application Request Routing — pro reverse proxy |
| Python             | 3.12+          | Přidat do PATH při instalaci                    |
| NSSM               | 2.24+          | Non-Sucking Service Manager — pro Windows službu|

> **Internet není potřeba.** Všechny Python závislosti jsou součástí balíčku (`dependencies/`).

---

## 3. Balení aplikace pro přenos (dev PC)

Spusť na **dev PC** (kde máš přístup k internetu a repozitáři):

```bat
package.bat
```

Skript automaticky:
- Zapíše aktuální git hash do `VERSION.txt`
- Stáhne závislosti do `dependencies/` (offline pip install)
- Vytvoří ZIP: `certifikaty_deploy_YYYYMMDD_<git-hash>.zip`

**Co balíček obsahuje:**

```
certifikaty_deploy_YYYYMMDD_<hash>.zip
├── app/                  kód aplikace (Python moduly)
├── static/               CSS, JS, obrázky
├── dependencies/         offline Python balíčky (.whl)
├── app.py                vstupní bod aplikace
├── config.py             konfigurace prostředí
├── requirements.txt      seznam závislostí
├── deploy.bat            první instalace
├── update.bat            aktualizace existující instalace
├── .env.example          vzor konfigurace
└── VERSION.txt           git hash + datum sestavení
```

**Co balíček NEobsahuje** (záměrně — tato data na serveru přetrvávají):

| Vynecháno     | Důvod                                      |
|---------------|--------------------------------------------|
| `instance/`   | Databáze — nesmí se přepsat               |
| `logs/`       | Logy aplikace                              |
| `uploads/`    | Nahrané soubory uživatelů                  |
| `.env`        | Konfigurace s hesly a citlivými údaji      |
| `venv/`       | Generuje se na serveru                     |

Zkopíruj ZIP na flash disk a přenes na server.

---

## 4. První instalace na novém serveru

### 4.1 Příprava složky

Vytvoř cílovou složku aplikace:

```
C:\inetpub\certifikaty\
```

### 4.2 Rozbalení balíčku

Zkopíruj ZIP z flash disku do `C:\inetpub\certifikaty\` a rozbal ho:
- Pravé tlačítko na ZIP → **Extrahovat vše** → cílová složka `C:\inetpub\certifikaty\`

### 4.3 Spuštění instalace

Spusť **CMD jako Administrator** a přejdi do složky:

```bat
cd C:\inetpub\certifikaty
deploy.bat
```

Skript provede:

| Krok | Co se stane                                                    |
|------|----------------------------------------------------------------|
| 1    | Ověří dostupnost Pythonu                                       |
| 2    | Vytvoří virtuální prostředí `venv/`                            |
| 3    | Nainstaluje závislosti offline z `dependencies/`               |
| 4    | Vytvoří složky `logs/`, `uploads/`, `instance/`                |
| 5    | Inicializuje všechny 4 databáze (live, uat, sit, prelive)      |

### 4.4 Vytvoření konfigurace

```bat
copy .env.example .env
notepad .env
```

Vyplň minimálně `SECRET_KEY` (viz [sekce 6](#6-konfigurace-aplikace-env)).

### 4.5 Ověření funkčnosti

Před konfigurací IIS ověř, že aplikace startuje:

```bat
cd C:\inetpub\certifikaty
venv\Scripts\python.exe -m waitress --host=127.0.0.1 --port=8080 app:app
```

Otevři v prohlížeči: `http://localhost:8080/evidence_certifikatu`

Aplikace by měla odpovědět. Zastav ji pomocí `Ctrl+C` a pokračuj konfigurací IIS.

---

## 5. Konfigurace IIS

Aplikace běží jako Python WSGI proces (Waitress) na portu 8080. IIS slouží jako **reverse proxy**.

### 5.1 Vytvoření Application Poolu

1. Otevři **IIS Manager** (`inetmgr`)
2. **Application Pools** → **Add Application Pool**
   - Name: `CertifikátyPool` *(libovolný název, zapamatuj si ho pro update.bat)*
   - .NET CLR version: **No Managed Code**
   - Managed pipeline mode: **Integrated**
3. Klikni na pool → **Advanced Settings**:
   - **Identity**: `ApplicationPoolIdentity` (nebo dedikovaný servisní účet)
   - **Start Mode**: `AlwaysRunning`
   - **Idle Time-out**: `0` (zakáže automatické zastavení)

### 5.2 Vytvoření webu

1. **Sites** → **Add Website**
   - Site name: `Certifikáty`
   - Application pool: `CertifikátyPool`
   - Physical path: `C:\inetpub\certifikaty`
   - Port: `80` (nebo jiný)

### 5.3 Nastavení reverse proxy (URL Rewrite + ARR)

Ověř, že jsou nainstaleny **Application Request Routing (ARR)** a **URL Rewrite**.

Vytvoř soubor `C:\inetpub\certifikaty\web.config`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="Proxy to Waitress" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:8080/{R:1}" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
```

### 5.4 Spuštění Waitress jako Windows Service (NSSM)

Aby aplikace běžela na pozadí i po restartu serveru, použij **NSSM**.

1. Zkopíruj `nssm.exe` z flash disku do `C:\inetpub\certifikaty\` (nebo do `C:\Windows\System32\`)

2. Spusť CMD jako Administrator:
   ```bat
   nssm install evidence_cert
   ```

3. V GUI nastav:
   - **Path:** `C:\inetpub\certifikaty\venv\Scripts\python.exe`
   - **Arguments:** `-m waitress --host=127.0.0.1 --port=8080 app:app`
   - **Startup directory:** `C:\inetpub\certifikaty`
   - Záložka **Environment:** `FLASK_ENV=production`

4. Spusť službu:
   ```bat
   nssm start evidence_cert
   ```

5. Ověř, že služba běží:
   ```bat
   nssm status evidence_cert
   ```

> **Poznámka:** IIS Application Pool (`CertifikátyPool`) řídí IIS konfiguraci.
> Windows Service (`evidence_cert` přes NSSM) řídí samotný Python/Waitress proces.
> Obě věci musí běžet zároveň.

---

## 6. Konfigurace aplikace (.env)

Vytvoř soubor `.env` ve složce aplikace (`C:\inetpub\certifikaty\.env`).
Tento soubor **nikdy není součástí balíčku** — přetrvává mezi aktualizacemi.

```env
# ── Bezpečnost ────────────────────────────────────────────────────────────────
SECRET_KEY=změň-na-náhodný-řetězec-min-32-znaků

# ── Debug (pouze pro vývoj, NIKDY v produkci) ────────────────────────────────
FLASK_DEBUG=false

# ── SMTP (email notifikace) ───────────────────────────────────────────────────
MAIL_SERVER=smtp.firma.cz
MAIL_PORT=25
MAIL_USE_TLS=false
MAIL_SMTP_AUTH=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_SENDER_ADDRESS=certifikaty@firma.cz
MAIL_SENDER_NAME=Evidence certifikátů
MAIL_SUBJECT_PREFIX=[Certifikáty]
MAIL_RECIPIENTS=admin@firma.cz,security@firma.cz

# ── Prostředí zahrnutá do měsíčního reportu ──────────────────────────────────
# Možné hodnoty: live, uat, sit, prelive  (odděleno čárkou, bez mezer)
REPORT_ENVS=live

# ── Plán měsíčního reportu ────────────────────────────────────────────────────
REPORT_DAY=1      # den v měsíci (1 = první den)
REPORT_HOUR=9     # hodina (0-23)
REPORT_MINUTE=0   # minuta (0-59)
```

**Vygenerování SECRET_KEY:**

```bat
venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

**Alternativa — konfigurace přes XML:**

Pokud chceš SMTP načíst ze sdíleného XML souboru:

```env
MAIL_CONFIG_XML=C:\shared\config\mail_config.xml
```

Očekávaná struktura XML:
```xml
<configuration>
  <mail>
    <host>smtp.firma.cz</host>
    <port>25</port>
    <username></username>
    <password></password>
    <smtpAuth>false</smtpAuth>
    <startTlsEnabled>false</startTlsEnabled>
    <senderAddress>certifikaty@firma.cz</senderAddress>
    <senderName>Evidence certifikátů</senderName>
    <subject>[Certifikáty]</subject>
  </mail>
</configuration>
```

---

## 7. Aktualizace na novou verzi

Toto je nejčastější operace. Celý proces trvá **cca 2–3 minuty**.

### Architektura IIS deploymentu

```
Uživatel → IIS (port 80) → URL Rewrite (reverse proxy) → Waitress (port 8080) → Python app
             └── App Pool                                    └── NSSM služba
```

**Při aktualizaci musí být zastaven Waitress (NSSM služba)**, jinak má Python soubory
zamčené a nový kód by se nenačetl. IIS pool se zastaví, aby nepřijímal requesty v době výpadku.

### Na dev PC

```bat
package.bat
```

→ vytvoří `certifikaty_deploy_20260415_a1b2c3d.zip`

Zkopíruj ZIP na flash disk.

### Na serveru

1. Zkopíruj ZIP do složky aplikace: `C:\inetpub\certifikaty\`

2. Spusť **CMD jako Administrator:**

   ```bat
   cd C:\inetpub\certifikaty
   update.bat CertifikátyPool certifikaty_deploy_20260415_a1b2c3d.zip evidence_cert
   ```

   | Parametr        | Popis                                     | Příklad               |
   |-----------------|-------------------------------------------|-----------------------|
   | 1. App Pool     | Název IIS Application Poolu               | `CertifikátyPool`     |
   | 2. ZIP soubor   | Název balíčku (nebo vynech — najde sám)   | `certifikaty_deploy_…zip` |
   | 3. NSSM služba  | Název Windows služby Waitress             | `evidence_cert`      |

   Název NSSM služby lze vynechat — výchozí hodnota je `evidence_cert`.
   Pokud NSSM služba na serveru neexistuje, skript to oznámí a pokračuje.

Skript provede:

| Krok | Co se stane                                                           |
|------|-----------------------------------------------------------------------|
| 1    | Zastaví IIS Application Pool (přestane přijímat požadavky)           |
| 2    | Zastaví Waitress službu přes NSSM (uvolní zámky na Python souborech) |
| 3    | Extrahuje ZIP přes stávající soubory (přepíše kód, zachová data)      |
| 4    | Nainstaluje nové/aktualizované Python závislosti                       |
| 5    | DB migrace — přidá nové tabulky, zachová existující data              |
| 6    | Spustí Waitress (NSSM) → čeká 3s → spustí IIS Application Pool       |

**Co se NIKDY nepřepíše:**

| Složka / soubor   | Obsah                         |
|-------------------|-------------------------------|
| `instance/`       | Databáze (všechna 4 prostředí)|
| `logs/`           | Logy aplikace                 |
| `uploads/`        | Nahrané soubory               |
| `.env`            | Konfigurace prostředí         |

### Ověření po aktualizaci

1. Otevři aplikaci v prohlížeči
2. Zkontroluj `VERSION.txt` ve složce aplikace
3. Zkontroluj logy: `logs\app.log`

---

## 8. Migrace existující instalace

Tato sekce je určena pro **server, kde aplikace již běžela** s prostředím TEST,
a nyní přecházíme na UAT + přidáváme SIT a PRELIVE.

### 8.1 Přejmenování databáze TEST → UAT

Pokud existuje stará databáze `instance\certifikaty_test.db`:

```bat
cd C:\inetpub\certifikaty
copy instance\certifikaty_test.db instance\certifikaty_uat.db
```

> `certifikaty_test.db` lze po ověření smazat, aplikace ji již nepoužívá.

### 8.2 Inicializace nových databází SIT a PRELIVE

Po nasazení nového balíčku (viz sekce 7) se nové databáze vytvoří automaticky
v kroku DB migrace (`update.bat` krok 4).

Pokud chceš inicializovat ručně (bez update):

```bat
cd C:\inetpub\certifikaty
venv\Scripts\python.exe -c "from app import create_app,db; app=create_app(); ctx=app.app_context(); ctx.push(); meta=db.metadatas.get('live') if hasattr(db,'metadatas') else db.metadata; [meta.create_all(bind=db.engines[e]) or print('OK: '+e) for e in ('live','uat','sit','prelive')]; ctx.pop()"
```

Po provedení by měly existovat tyto soubory:

```
instance\
  certifikaty.db            ← live (existující)
  certifikaty_uat.db        ← UAT (zkopírováno z test nebo nové)
  certifikaty_sit.db        ← SIT (nové, prázdné)
  certifikaty_prelive.db    ← PRELIVE (nové, prázdné)
```

### 8.3 Aktualizace .env

Zkontroluj hodnotu `REPORT_ENVS` v `.env`:

```env
# Zahrnout do reportu pouze produkci (doporučeno):
REPORT_ENVS=live

# Nebo více prostředí:
REPORT_ENVS=live,uat
```

Hodnota `test` již není platná — nahraď ji `uat`.

### 8.4 Restart aplikace po migraci

```bat
cd C:\inetpub\certifikaty
C:\Windows\System32\inetsrv\appcmd.exe stop apppool /apppool.name:"CertifikátyPool"
C:\Windows\System32\inetsrv\appcmd.exe start apppool /apppool.name:"CertifikátyPool"
```

---

## 9. Řešení problémů

### Aplikace nereaguje po update

Zkontroluj oba procesy — musí běžet oba:

```bat
REM 1. Stav NSSM / Waitress služby
nssm status evidence_cert

REM 2. Stav IIS Application Poolu
C:\Windows\System32\inetsrv\appcmd.exe list apppool CertifikátyPool
```

Ruční restart obou:

```bat
REM Restart Waitress
nssm stop evidence_cert
nssm start evidence_cert

REM Restart IIS pool (po startu Waitressu)
C:\Windows\System32\inetsrv\appcmd.exe stop apppool /apppool.name:"CertifikátyPool"
C:\Windows\System32\inetsrv\appcmd.exe start apppool /apppool.name:"CertifikátyPool"
```

### Chyba při spuštění aplikace

Spusť ručně a sleduj výstup přímo v konzoli:

```bat
cd C:\inetpub\certifikaty
venv\Scripts\python.exe app.py
```

### Chybějící tabulky v databázi

```bat
cd C:\inetpub\certifikaty
venv\Scripts\python.exe -c "from app import create_app,db; app=create_app(); ctx=app.app_context(); ctx.push(); meta=db.metadatas.get('live') if hasattr(db,'metadatas') else db.metadata; [meta.create_all(bind=db.engines[e]) or print('OK: '+e) for e in ('live','uat','sit','prelive')]; ctx.pop()"
```

### NSSM služba nespustí aplikaci

```bat
REM Zkontroluj stav služby
nssm status evidence_cert

REM Zobraz logy NSSM
nssm dump evidence_cert

REM Restartuj službu
nssm restart evidence_cert
```

### Ověření, že Waitress naslouchá na portu 8080

```bat
netstat -ano | findstr :8080
```

### Logy aplikace

Aplikační logy: `logs\app.log` (automatická rotace, archivace jako `logs\app.log.YYYY-MM-DD.zip`)

### Stav databází — přehled souborů

```bat
dir C:\inetpub\certifikaty\instance\
```

Očekávaný výstup:
```
certifikaty.db
certifikaty_uat.db
certifikaty_sit.db
certifikaty_prelive.db
```

---

*Dokument aktualizován: 2026-04-15*
