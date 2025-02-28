from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from waitress import serve
from models import db, Certifikat, Server
from datetime import datetime, timedelta, date
import pandas as pd
from openpyxl import Workbook
import os
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import re
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler
#from flask_mail import Mail, Message
import calendar

app = Flask(__name__,
           static_url_path='/evidence_certifikatu/static',  # Změna cesty pro statické soubory
           static_folder='static')

# Přidáme konfiguraci pro URL prefix
app.config['APPLICATION_ROOT'] = '/evidence_certifikatu'

# Přidáme debug výpisy
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'tajny_klic'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///certifikaty.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Vytvoříme složku pro logy, pokud neexistuje
if not os.path.exists('logs'):
    os.makedirs('logs')

# Konfigurace loggeru
logger = logging.getLogger('certifikaty')
logger.setLevel(logging.INFO)

# Handler pro rotující soubory (max 10MB, záloha posledních 10 souborů)
file_handler = RotatingFileHandler(
    'logs/app.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=10,
    encoding='utf-8'
)

# Formát logu: [DATUM ČASU] [ÚROVEŇ] zpráva (v souboru:řádek)
formatter = logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s (in %(pathname)s:%(lineno)d)'
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Přidáme také výpis do konzole pro development
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# Přidáme konfiguraci pro upload souborů
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# Vytvoříme složku pro uploady, pokud neexistuje
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# # Konfigurace e-mailu
# app.config['MAIL_SERVER'] = 'smtp.gmail.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USERNAME'] = 'vas@email.cz'
# app.config['MAIL_PASSWORD'] = 'vase_heslo_nebo_app_password'
# mail = Mail(app)

# Inicializace databáze
db.init_app(app)

@app.route('/evidence_certifikatu/')
def index():
    try:
        logger.info('Načítání hlavní stránky')
        servery = Server.query.all()
        servery_nazvy = [server.nazev for server in servery]
        aktivni_server = request.args.get('server', servery_nazvy[0] if servery_nazvy else None)
        
        if aktivni_server:
            logger.info(f'Načítání certifikátů pro server: {aktivni_server}')
            certifikaty = db.session.query(Certifikat).filter(
                Certifikat.server == aktivni_server
            ).order_by(Certifikat.expirace, Certifikat.cesta).all()
            logger.info(f'Načteno {len(certifikaty)} certifikátů')
        else:
            certifikaty = []
            logger.warning('Žádný aktivní server není vybrán')
            
        return render_template('index.html', 
                             certifikaty=certifikaty, 
                             servery=servery_nazvy, 
                             aktivni_server=aktivni_server)
    except Exception as e:
        logger.error(f'Chyba při načítání hlavní stránky: {str(e)}', exc_info=True)
        return f"Došlo k chybě: {str(e)}", 500

@app.route('/evidence_certifikatu/pridat', methods=['GET', 'POST'])
def pridat_certifikat():
    if request.method == 'POST':
        try:
            logger.info('Přidávání nového certifikátu')
            expirace = datetime.strptime(request.form['expirace'], '%d.%m.%Y')
            
            novy_cert = Certifikat(
                server=request.form['server'],
                cesta=request.form['cesta'],
                nazev=request.form['nazev'],
                expirace=expirace,
                poznamka=request.form.get('poznamka', '')
            )
            db.session.add(novy_cert)
            db.session.commit()
            logger.info(f'Certifikát úspěšně přidán: {novy_cert.nazev} pro server {novy_cert.server}')
            flash('Certifikát byl úspěšně přidán!')
            return redirect(url_for('index'))
        except ValueError as e:
            logger.error(f'Neplatný formát data: {str(e)}')
            flash('Neplatný formát data! Použijte formát dd.mm.yyyy')
            return redirect(url_for('pridat_certifikat'))
        except Exception as e:
            logger.error(f'Chyba při přidávání certifikátu: {str(e)}', exc_info=True)
            flash(f'Chyba při přidávání certifikátu: {str(e)}')
            return redirect(url_for('pridat_certifikat'))
    
    servery = Server.query.all()
    return render_template('formular.html', certifikat=None, servery=servery)

@app.route('/evidence_certifikatu/get-edit-form/<int:id>')
def get_edit_form(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        servery = Server.query.all()
        return render_template('edit_modal.html', certifikat=certifikat, servery=servery)
    except Exception as e:
        logger.error(f'Chyba při načítání editačního formuláře: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/evidence_certifikatu/upravit/<int:id>', methods=['POST'])
def upravit_certifikat(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        
        server = request.form['server']
        cesta = request.form['cesta']
        nazev = request.form['nazev']
        expirace_str = request.form['expirace']
        poznamka = request.form.get('poznamka', '')
        
        try:
            expirace = datetime.strptime(expirace_str, '%d.%m.%Y')
            
            certifikat.server = server
            certifikat.cesta = cesta
            certifikat.nazev = nazev
            certifikat.expirace = expirace
            certifikat.poznamka = poznamka
            
            db.session.commit()
            logger.info(f'Certifikát {certifikat.nazev} byl úspěšně upraven')
            
            return jsonify({
                'success': True,
                'message': 'Certifikát byl úspěšně upraven'
            })
        except ValueError:
            return jsonify({
                'success': False,
                'message': 'Neplatný formát data! Použijte formát dd.mm.yyyy'
            }), 400
            
    except Exception as e:
        logger.error(f'Chyba při úpravě certifikátu: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Chyba při úpravě certifikátu: {str(e)}'
        }), 500

@app.route('/evidence_certifikatu/smazat/<int:id>')
def smazat_certifikat(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        logger.info(f'Mazání certifikátu: {certifikat.nazev} ze serveru {certifikat.server}')
        db.session.delete(certifikat)
        db.session.commit()
        logger.info('Certifikát úspěšně smazán')
        flash('Certifikát byl smazán!')
    except Exception as e:
        logger.error(f'Chyba při mazání certifikátu: {str(e)}', exc_info=True)
        flash(f'Chyba při mazání certifikátu: {str(e)}')
    return redirect(url_for('index'))

@app.route('/evidence_certifikatu/smazat-vse')
def smazat_vse():
    try:
        # Smazání všech záznamů
        Certifikat.query.delete()
        db.session.commit()
        flash('Všechny certifikáty byly smazány!')
    except Exception as e:
        flash(f'Chyba při mazání: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('index'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/evidence_certifikatu/import-excel', methods=['POST'])
def import_excel():
    try:
        logger.info('Začátek importu z Excelu')
        if 'excel_file' not in request.files:
            logger.warning('Nebyl vybrán žádný soubor')
            return jsonify({'error': 'Nebyl vybrán žádný soubor'}), 400
        
        file = request.files['excel_file']
        if file.filename == '':
            logger.warning('Prázdný název souboru')
            return jsonify({'error': 'Nebyl vybrán žádný soubor'}), 400
        
        if not allowed_file(file.filename):
            logger.warning(f'Nepovolený typ souboru: {file.filename}')
            return jsonify({'error': 'Nepovolený typ souboru'}), 400
        
        # Uložíme soubor
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Načteme Excel
        df = pd.read_excel(filepath)
        
        logger.info(f"Import souboru: {filename}")
        logger.info(f"Původní sloupce: {df.columns.tolist()}")
        logger.info(f"Celkový počet řádků v Excelu: {len(df)}")
        
        # Vyplníme prázdné hodnoty v Server a Cesta hodnotami z předchozích řádků
        df['Server'] = df['Server'].fillna(method='ffill')
        df['Cesta'] = df['Cesta'].fillna(method='ffill')
        df['Název certifikátu'] = df['Název certifikátu'].fillna('Neznámý certifikát')
        
        # Vyčistíme data - odstraníme řádky kde je NaN v serveru
        df = df.dropna(subset=['Server'])
        logger.info(f"Počet řádků po odstranění prázdných serverů: {len(df)}")
        
        # Funkce pro kontrolu, zda je hodnota platné datum
        def is_valid_date(value):
            if pd.isna(value):
                return False
            try:
                if isinstance(value, str):
                    datetime.strptime(value, '%d.%m.%Y')
                elif isinstance(value, datetime):
                    return True
                else:
                    return False
                return True
            except ValueError:
                return False
        
        # Odfiltrujeme řádky, kde expirace není platné datum
        df = df[df['Expirace'].apply(is_valid_date)]
        logger.info(f"Počet řádků po kontrole data: {len(df)}")
        
        # Zkontrolujeme názvy sloupců
        logger.info(f"Dostupné sloupce: {df.columns.tolist()}")
        
        # Vypíšeme prvních pár řádků pro kontrolu
        logger.info("Prvních 5 řádků:")
        logger.info(df.head().to_string())
        
        # Nejprve vytvoříme všechny servery
        unique_servers = df['Server'].unique()
        print("\nUnikátní servery:", unique_servers)
        
        for server_name in unique_servers:
            # Přeskočíme prázdné hodnoty
            if pd.isna(server_name):
                print(f"Přeskakuji prázdný server")
                continue
            if not Server.query.filter_by(nazev=server_name).first():
                print(f"Přidávám nový server: {server_name}")
                new_server = Server(nazev=server_name)
                db.session.add(new_server)
        db.session.commit()
        
        # Počítadla pro statistiky
        pridano = 0
        aktualizovano = 0
        beze_zmeny = 0
        preskoceno = 0
        
        # Zpracujeme každý řádek
        for idx, row in df.iterrows():
            server = row['Server']
            cesta = row['Cesta']
            nazev = row['Název certifikátu']
            print(f"\nZpracovávám řádek {idx}:")
            print(f"Server: {server}, Cesta: {cesta}, Název: {nazev}")
            
            # Převedeme datum na správný formát
            try:
                if isinstance(row['Expirace'], str):
                    # Pokud je datum jako string, převedeme ho
                    expirace = datetime.strptime(row['Expirace'], '%d.%m.%Y').date()
                else:
                    # Pokud je to datetime, převedeme na date
                    expirace = row['Expirace'].date()
            except Exception as e:
                print(f"Chyba při konverzi data pro řádek {idx}: {str(e)}")
                continue
            
            # Kontrola existence certifikátu
            existing = Certifikat.query.filter(
                Certifikat.server == server,
                Certifikat.cesta == cesta,
                Certifikat.nazev == nazev
            ).first()
            
            if existing:
                if existing.expirace != expirace:
                    # Aktualizujeme pouze datum expirace
                    existing.expirace = expirace
                    aktualizovano += 1
                else:
                    beze_zmeny += 1
            else:
                # Kontrola úplných duplicit (včetně expirace)
                duplicates = Certifikat.query.filter(
                    Certifikat.server == server,
                    Certifikat.cesta == cesta,
                    Certifikat.nazev == nazev,
                    Certifikat.expirace == expirace
                ).all()
                
                # Pokud existují duplicity, smažeme je a necháme jen jeden záznam
                if duplicates:
                    # Ponecháme první záznam a smažeme ostatní
                    for dup in duplicates[1:]:
                        db.session.delete(dup)
                    beze_zmeny += 1
                else:
                    new_cert = Certifikat(
                        server=server,
                        cesta=cesta,
                        nazev=nazev,
                        expirace=expirace
                    )
                    db.session.add(new_cert)
                    pridano += 1
        
        db.session.commit()
        
        # Smažeme nahraný soubor
        os.remove(filepath)
        
        logger.info(f'Import dokončen. Přidáno: {pridano}, Aktualizováno: {aktualizovano}, Beze změny: {beze_zmeny}')
        return jsonify({
            'success': True,
            'message': f'Import dokončen. Přidáno: {pridano}, Aktualizováno: {aktualizovano}'
        })
        
    except Exception as e:
        logger.error(f'Chyba při importu: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Chyba při importu: {str(e)}'
        }), 400

@app.route('/evidence_certifikatu/export-excel')
def export_excel():
    try:
        # Přidáno řazení podle expirace
        certifikaty = Certifikat.query.order_by(Certifikat.expirace).all()
        
        # Vytvoření nového Excel souboru
        wb = Workbook()
        ws = wb.active
        ws.title = "Certifikáty"
        
        # Přidání hlavičky
        headers = ['Server', 'Cesta', 'Název certifikátu', 'Expirace', 'Poznámka']
        ws.append(headers)
        
        # Přidání dat
        for cert in certifikaty:
            ws.append([
                cert.server,
                cert.cesta,
                cert.nazev,
                cert.expirace.strftime('%d.%m.%Y'),
                cert.poznamka or ''
            ])
        
        # Nastavení šířky sloupců
        for column in ws.columns:
            max_length = 0
            column = list(column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column[0].column_letter].width = adjusted_width
        
        # Uložení souboru
        filename = f'certifikaty_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        filepath = os.path.join(app.root_path, 'static', filename)
        wb.save(filepath)
        
        flash('Excel soubor byl úspěšně vytvořen!')
        return redirect(url_for('static', filename=filename))
        
    except Exception as e:
        flash(f'Chyba při exportu do Excelu: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.template_filter('get_expiry_class')
def get_expiry_class(cert):
    """Vrátí CSS třídu podle doby do expirace"""
    try:
        today = datetime.now().date()
        
        # Převedeme datum expirace na date objekt
        if isinstance(cert.expirace, datetime):
            expiry_date = cert.expirace.date()
        else:
            expiry_date = cert.expirace
        
        # Vypočítáme rozdíl dnů
        days_to_expiry = (expiry_date - today).days
        
        # Certifikát je v minulosti nebo končí do 30 dnů (červená)
        if days_to_expiry <= 30:
            return 'cert-expired'
        # Certifikát končí za 31-60 dnů (oranžová)
        elif days_to_expiry <= 60:
            return 'cert-warning'
        # Certifikát končí tento rok (modrá)
        elif expiry_date.year == today.year:
            return 'cert-ending-year'
        
        return ''
    except Exception as e:
        return ''

# Přidáme funkci pro kontrolu certifikátů
def check_certificates():
    with app.app_context():
        try:
            today = datetime.now().date()
            expiring_certs = Certifikat.query.filter(
                Certifikat.expirace <= today + timedelta(days=60)
            ).all()
        except Exception as e:
            print(f"Chyba při kontrole certifikátů: {str(e)}")

# Nastavení plánovače
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_certificates, trigger="interval", hours=24)  # kontrola jednou denně místo každých 30 sekund
scheduler.start()

# Zastavení plánovače při ukončení aplikace
atexit.register(lambda: scheduler.shutdown())

@app.route('/evidence_certifikatu/dashboard')
def dashboard():
    try:
        today = datetime.now().date()
        
        ending_certs = db.session.query(Certifikat).filter(
            Certifikat.expirace.between(today, datetime(today.year, 12, 31).date())
        ).order_by(Certifikat.expirace).all()
        
        # Spočítáme statistiky
        stats = {
            'critical': sum(1 for cert in ending_certs if (cert.expirace - today).days <= 30),
            'warning': sum(1 for cert in ending_certs if 30 < (cert.expirace - today).days <= 60),
            'this_year': len(ending_certs)
        }
        
        # Statistiky podle serverů (už jen pro unikátní certifikáty)
        server_counts = {}
        for cert in ending_certs:
            server_counts[cert.server] = server_counts.get(cert.server, 0) + 1
        
        server_stats = [(server, count) for server, count in server_counts.items()]
        server_stats.sort(key=lambda x: x[1], reverse=True)
        
        return render_template('dashboard.html', 
                             stats=stats,
                             ending_certs=ending_certs,
                             server_stats=server_stats,
                             today=today)
    except Exception as e:
        flash(f'Chyba při načítání dashboardu: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/evidence_certifikatu/static/<path:filename>')
def static_files(filename):
    response = send_from_directory('static', filename)
    if filename.endswith('.css'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.route('/evidence_certifikatu/servery')
def servery():
    try:
        # Získáme všechny servery a počet jejich certifikátů
        servery_s_pocty = db.session.query(
            Server,
            db.func.count(Certifikat.id).label('pocet_certifikatu')
        ).outerjoin(
            Certifikat,
            Server.nazev == Certifikat.server
        ).group_by(Server.id).all()
        
        # Převedeme na seznam slovníků pro snadnější práci v šabloně
        servery_data = [{
            'id': server.id,
            'nazev': server.nazev,
            'popis': server.popis,
            'vytvoreno': server.vytvoreno,
            'pocet_certifikatu': pocet
        } for server, pocet in servery_s_pocty]
        
        return render_template('servery.html', servery=servery_data)
    except Exception as e:
        logger.error(f'Chyba při načítání seznamu serverů: {str(e)}', exc_info=True)
        flash(f'Chyba při načítání seznamu serverů: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/evidence_certifikatu/pridat-server', methods=['POST'])
def pridat_server():
    novy_server = request.form.get('nazev')
    if novy_server:
        try:
            # Zkontrolujeme, zda server již neexistuje
            existujici = Server.query.filter_by(nazev=novy_server).first()
            if existujici:
                flash(f'Server {novy_server} již existuje!', 'error')
            else:
                # Vytvoříme nový server
                server = Server(nazev=novy_server, popis=request.form.get('popis', ''))
                db.session.add(server)
                db.session.commit()
                flash(f'Server {novy_server} byl úspěšně přidán!')
        except Exception as e:
            db.session.rollback()
            flash(f'Chyba při přidávání serveru: {str(e)}', 'error')
    return redirect(url_for('servery'))

@app.route('/evidence_certifikatu/smazat-server/<int:id>')
def smazat_server(id):
    try:
        # Najdeme server podle ID
        server_obj = Server.query.get_or_404(id)
        if server_obj:
            # Smažeme všechny certifikáty pro daný server
            Certifikat.query.filter_by(server=server_obj.nazev).delete()
            # Smažeme samotný server
            db.session.delete(server_obj)
            db.session.commit()
            flash(f'Server {server_obj.nazev} a všechny jeho certifikáty byly smazány!')
        else:
            flash(f'Server nebyl nalezen!', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Chyba při mazání serveru: {str(e)}', 'error')
    return redirect(url_for('servery'))

@app.route('/evidence_certifikatu/favicon.ico')
def favicon():
    return send_from_directory('static',
                             'favicon.ico', 
                             mimetype='image/vnd.microsoft.icon')

@app.route('/evidence_certifikatu/get-certificates/<server>')
def get_certificates(server):
    try:
        certifikaty = Certifikat.query.filter_by(server=server)\
            .order_by(Certifikat.expirace, Certifikat.cesta).all()
        
        # Převedeme certifikáty na JSON
        certs_data = []
        for cert in certifikaty:
            certs_data.append({
                'id': cert.id,
                'server': cert.server,
                'cesta': cert.cesta,
                'nazev': cert.nazev,
                'expirace': cert.expirace.strftime('%Y-%m-%d'),
                'poznamka': cert.poznamka
            })
        
        return jsonify(certs_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/evidence_certifikatu/detail/<int:id>')
def detail_certifikatu(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        return render_template('detail_modal.html', certifikat=certifikat)
    except Exception as e:
        app.logger.error(f'Chyba při načítání detailu: {str(e)}')
        return f'Chyba při načítání detailu: {str(e)}', 500

@app.route('/evidence_certifikatu/reset-db')
def reset_db():
    try:
        # Smazat a vytvořit novou databázi
        db.drop_all()
        db.create_all()
        app.logger.info("Databáze byla resetována")
        flash('Databáze byla úspěšně resetována', 'success')
    except Exception as e:
        app.logger.error(f"Chyba při resetu databáze: {str(e)}")
        flash(f'Chyba při resetu databáze: {str(e)}', 'error')
    return redirect(url_for('index'))

@app.route('/evidence_certifikatu/smazat-db')
def smazat_db():
    try:
        # Smazat všechny certifikáty
        Certifikat.query.delete()
        # Smazat všechny servery
        Server.query.delete()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Databáze byla úspěšně smazána'
        })
    except Exception as e:
        app.logger.error(f"Chyba při mazání databáze: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Chyba při mazání databáze: {str(e)}'
        }), 400

# def send_expiry_notification(cert):
#     """Odešle notifikaci o blížící se expiraci certifikátu"""
#     days_to_expiry = (cert.expirace - datetime.now().date()).days
#     if days_to_expiry <= 30:
#         # Zde můžete implementovat odeslání e-mailu nebo jiné notifikace
#         pass
# 
# # Přidat do scheduleru
# scheduler = BackgroundScheduler()
# scheduler.add_job(check_expiring_certificates, 'cron', hour=8)  # Kontrola každý den v 8:00
# scheduler.start()

@app.route('/evidence_certifikatu/export/<format>')
def export(format):
    if format == 'pdf':
        return export_pdf()
    elif format == 'csv':
        return export_csv()
    elif format == 'json':
        return export_json()

def send_monthly_certificate_report():
    """Odešle měsíční report o končících certifikátech"""
    with app.app_context():
        today = date.today()
        # Získáme poslední den aktuálního měsíce
        _, last_day = calendar.monthrange(today.year, today.month)
        month_end = date(today.year, today.month, last_day)
        
        # Najdeme všechny certifikáty končící tento měsíc
        ending_certs = Certifikat.query.filter(
            Certifikat.expirace.between(today, month_end)
        ).order_by(Certifikat.expirace).all()
        
        if ending_certs:
            # Vytvoříme HTML tabulku s certifikáty
            html_content = """
            <h2>Přehled certifikátů končících v tomto měsíci</h2>
            <table border="1" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #f2f2f2;">
                    <th style="padding: 8px;">Server</th>
                    <th style="padding: 8px;">Cesta</th>
                    <th style="padding: 8px;">Název</th>
                    <th style="padding: 8px;">Expirace</th>
                    <th style="padding: 8px;">Zbývá dnů</th>
                </tr>
            """
            
            for cert in ending_certs:
                days_left = (cert.expirace - today).days
                row_color = '#fee2e2' if days_left <= 7 else '#fff7ed' if days_left <= 14 else '#ffffff'
                
                html_content += f"""
                <tr style="background-color: {row_color};">
                    <td style="padding: 8px;">{cert.server}</td>
                    <td style="padding: 8px;">{cert.cesta}</td>
                    <td style="padding: 8px;">{cert.nazev}</td>
                    <td style="padding: 8px;">{cert.expirace.strftime('%d.%m.%Y')}</td>
                    <td style="padding: 8px;">{days_left} dnů</td>
                </tr>
                """
            
            html_content += "</table>"
            
            # Vytvoříme a odešleme e-mail
            msg = Message(
                f'Měsíční přehled končících certifikátů - {today.strftime("%B %Y")}',
                sender=app.config['MAIL_USERNAME'],
                recipients=['admin@vase-firma.cz']  # Seznam příjemců
            )
            msg.html = html_content
            # mail.send(msg)
            
            app.logger.info(f"Odeslán měsíční report pro {len(ending_certs)} certifikátů")
        else:
            app.logger.info("Žádné certifikáty tento měsíc nekončí")

# Nastavení plánovače pro spuštění první den v měsíci v 8:00
scheduler = BackgroundScheduler()
scheduler.add_job(
    send_monthly_certificate_report, 
    'cron', 
    day='1',  # První den v měsíci
    hour=8,   # V 8:00
    minute=0
)
scheduler.start()

# Zajistíme správné vypnutí plánovače při ukončení aplikace
# atexit.register(lambda: scheduler.shutdown())

@app.route('/evidence_certifikatu/send-report', methods=['POST'])
def trigger_report():
    try:
        send_monthly_certificate_report()
        return jsonify({
            'success': True,
            'message': 'Report byl úspěšně odeslán'
        })
    except Exception as e:
        app.logger.error(f"Chyba při odesílání reportu: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Chyba při odesílání reportu: {str(e)}'
        }), 500

# Přidáme error handler pro logování chyb 404 a 500
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f'Stránka nenalezena: {request.url}')
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f'Interní chyba serveru: {str(error)}', exc_info=True)
    db.session.rollback()
    return render_template('500.html'), 500

# Přidáme logování při spuštění aplikace
logger.info('Aplikace spuštěna')

@app.route('/evidence_certifikatu/get-server-detail/<int:id>')
def get_server_detail(id):
    try:
        server = Server.query.get_or_404(id)
        pocet_certifikatu = Certifikat.query.filter_by(server=server.nazev).count()
        return render_template('server_detail_modal.html', 
                             server=server,
                             pocet_certifikatu=pocet_certifikatu)
    except Exception as e:
        logger.error(f'Chyba při načítání detailu serveru: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/evidence_certifikatu/get-server-edit-form/<int:id>')
def get_server_edit_form(id):
    try:
        server = Server.query.get_or_404(id)
        return render_template('server_edit_modal.html', server=server)
    except Exception as e:
        logger.error(f'Chyba při načítání editačního formuláře serveru: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/evidence_certifikatu/upravit-server/<int:id>', methods=['POST'])
def upravit_server(id):
    try:
        server = Server.query.get_or_404(id)
        
        nazev = request.form['nazev']
        popis = request.form.get('popis', '')
        
        server.nazev = nazev
        server.popis = popis
        
        db.session.commit()
        logger.info(f'Server {server.nazev} byl úspěšně upraven')
        
        return jsonify({
            'success': True,
            'message': 'Server byl úspěšně upraven'
        })
    except Exception as e:
        logger.error(f'Chyba při úpravě serveru: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Chyba při úpravě serveru: {str(e)}'
        }), 500

if __name__ == '__main__':
    with app.app_context():
        # Vytvoříme databázi pouze pokud neexistuje
        if not os.path.exists('certifikaty.db'):
            db.create_all()
            app.logger.info("Vytvořena nová databáze")
        else:
            app.logger.info("Použita existující databáze")
    
    # Zapneme debug mode
    #app.run(debug=True, port=5000) 
    port = int(os.environ.get("PORT", 5000))
    serve(app, host='0.0.0.0', port=port)