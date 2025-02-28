from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from flask_sqlalchemy import SQLAlchemy
from models import db, Certifikat, Server
from datetime import datetime, timedelta
import pandas as pd
from openpyxl import Workbook
import os
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import re
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
# Přidáme debug výpisy
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'tajny_klic'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///certifikaty.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Konfigurace logování
if not os.path.exists('logs'):
    os.makedirs('logs')

# Nastavení loggeru
file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Aplikace spuštěna')

# Přidáme konfiguraci pro upload souborů
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# Vytvoříme složku pro uploady, pokud neexistuje
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Inicializace databáze
db.init_app(app)

@app.route('/')
def index():
    try:
        servery = Server.query.all()
        servery_nazvy = [server.nazev for server in servery]
        aktivni_server = request.args.get('server', servery_nazvy[0] if servery_nazvy else None)
        
        if aktivni_server:
            certifikaty = db.session.query(Certifikat).filter(
                Certifikat.server == aktivni_server
            ).distinct(
                Certifikat.server,
                Certifikat.cesta,
                Certifikat.nazev,
                Certifikat.expirace
            ).order_by(Certifikat.expirace, Certifikat.cesta).all()
        else:
            certifikaty = []
            
        return render_template('index.html', 
                             certifikaty=certifikaty, 
                             servery=servery_nazvy, 
                             aktivni_server=aktivni_server)
    except Exception as e:
        return f"Došlo k chybě: {str(e)}", 500

@app.route('/pridat', methods=['GET', 'POST'])
def pridat_certifikat():
    if request.method == 'POST':
        # Převedeme formát dd.mm.yy na datetime
        try:
            expirace = datetime.strptime(request.form['expirace'], '%d.%m.%Y')
        except ValueError:
            flash('Neplatný formát data! Použijte formát dd.mm.yyyy')
            return redirect(url_for('pridat_certifikat'))

        novy_cert = Certifikat(
            server=request.form['server'],
            cesta=request.form['cesta'],
            nazev=request.form['nazev'],
            expirace=expirace,
            poznamka=request.form.get('poznamka', '')
        )
        db.session.add(novy_cert)
        db.session.commit()
        flash('Certifikát byl úspěšně přidán!')
        return redirect(url_for('index'))
    
    servery = Server.query.all()
    return render_template('formular.html', certifikat=None, servery=servery)

@app.route('/upravit/<int:id>', methods=['GET', 'POST'])
def upravit_certifikat(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        servery = Server.query.all()
        
        if request.method == 'POST':
            print("POST request přijat")
            print("Form data:", request.form)
            
            server = request.form['server']
            cesta = request.form['cesta']
            nazev = request.form['nazev']
            expirace_str = request.form['expirace']
            poznamka = request.form.get('poznamka', '')
            
            print(f"Data před uložením:")
            print(f"Server: {server}")
            print(f"Cesta: {cesta}")
            print(f"Název: {nazev}")
            print(f"Expirace: {expirace_str}")
            print(f"Poznámka: {poznamka}")
            
            try:
                expirace = datetime.strptime(expirace_str, '%d.%m.%Y')
                
                certifikat.server = server
                certifikat.cesta = cesta
                certifikat.nazev = nazev
                certifikat.expirace = expirace
                certifikat.poznamka = poznamka
                
                db.session.commit()
                print("Data úspěšně uložena")
                flash('Certifikát byl úspěšně upraven', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                print(f"Chyba při ukládání: {str(e)}")
                db.session.rollback()
                flash(f'Chyba při úpravě certifikátu: {str(e)}', 'error')
                return render_template('formular.html', certifikat=certifikat, servery=servery)
        
        return render_template('formular.html', certifikat=certifikat, servery=servery)
    except Exception as e:
        print(f"Obecná chyba: {str(e)}")
        flash(f'Chyba při načítání certifikátu: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/smazat/<int:id>')
def smazat_certifikat(id):
    certifikat = Certifikat.query.get_or_404(id)
    db.session.delete(certifikat)
    db.session.commit()
    flash('Certifikát byl smazán!')
    return redirect(url_for('index'))

@app.route('/smazat-vse')
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

@app.route('/import-excel', methods=['POST'])
def import_excel():
    try:
        if 'excel_file' not in request.files:
            return jsonify({'error': 'Nebyl vybrán žádný soubor'}), 400
        
        file = request.files['excel_file']
        if file.filename == '':
            return jsonify({'error': 'Nebyl vybrán žádný soubor'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Nepovolený typ souboru'}), 400
        
        # Uložíme soubor
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Načteme Excel
        df = pd.read_excel(filepath)
        
        app.logger.info(f"Import souboru: {filename}")
        app.logger.info(f"Původní sloupce: {df.columns.tolist()}")
        app.logger.info(f"Celkový počet řádků v Excelu: {len(df)}")
        
        # Vyplníme prázdné hodnoty v Server a Cesta hodnotami z předchozích řádků
        df['Server'] = df['Server'].fillna(method='ffill')
        df['Cesta'] = df['Cesta'].fillna(method='ffill')
        df['Název certifikátu'] = df['Název certifikátu'].fillna('Neznámý certifikát')
        
        # Vyčistíme data - odstraníme řádky kde je NaN v serveru
        df = df.dropna(subset=['Server'])
        app.logger.info(f"Počet řádků po odstranění prázdných serverů: {len(df)}")
        
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
        app.logger.info(f"Počet řádků po kontrole data: {len(df)}")
        
        # Zkontrolujeme názvy sloupců
        app.logger.info(f"Dostupné sloupce: {df.columns.tolist()}")
        
        # Vypíšeme prvních pár řádků pro kontrolu
        app.logger.info("Prvních 5 řádků:")
        app.logger.info(df.head().to_string())
        
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
        
        return jsonify({
            'success': True,
            'message': f'Import dokončen. Přidáno: {pridano}, Aktualizováno: {aktualizovano}, Beze změny: {beze_zmeny}'
        })
        
    except Exception as e:
        app.logger.error(f'Chyba při importu: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Chyba při importu: {str(e)}'
        }), 400

@app.route('/export-excel')
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
    today = datetime.now().date()
    expiry_date = cert.expirace
    days_left = (expiry_date - today).days
    
    if expiry_date < today or days_left <= 30:  # Prošlé nebo končí tento měsíc
        return 'expired'
    elif days_left <= 60:  # Končí příští měsíc
        return 'expiring-warning'
    else:
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

@app.route('/dashboard')
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

@app.route('/static/<path:filename>')
def static_files(filename):
    response = send_from_directory('static', filename)
    if filename.endswith('.css'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.route('/servery')
def sprava_serveru():
    servery = Server.query.all()
    
    # Spočítáme počty certifikátů pro každý server
    pocty = {}
    celkem_certifikatu = 0
    for server in servery:
        pocet = Certifikat.query.filter_by(server=server.nazev).count()
        pocty[server.nazev] = pocet
        celkem_certifikatu += pocet
    
    # Celkové statistiky
    statistiky = {
        'celkem_serveru': len(servery),
        'celkem_certifikatu': celkem_certifikatu
    }
    
    return render_template('servery.html', 
                         servery=servery, 
                         pocty=pocty, 
                         statistiky=statistiky)

@app.route('/pridat-server', methods=['POST'])
def pridat_server():
    novy_server = request.form.get('server')
    if novy_server:
        try:
            # Zkontrolujeme, zda server již neexistuje
            existujici = Server.query.filter_by(nazev=novy_server).first()
            if existujici:
                flash(f'Server {novy_server} již existuje!', 'error')
            else:
                # Vytvoříme nový server
                server = Server(nazev=novy_server)
                db.session.add(server)
                db.session.commit()
                flash(f'Server {novy_server} byl úspěšně přidán!')
        except Exception as e:
            db.session.rollback()
            flash(f'Chyba při přidávání serveru: {str(e)}', 'error')
    return redirect(url_for('sprava_serveru'))

@app.route('/smazat-server/<server>')
def smazat_server(server):
    try:
        # Najdeme server
        server_obj = Server.query.filter_by(nazev=server).first()
        if server_obj:
            # Smažeme všechny certifikáty pro daný server
            Certifikat.query.filter_by(server=server).delete()
            # Smažeme samotný server
            db.session.delete(server_obj)
            db.session.commit()
            flash(f'Server {server} a všechny jeho certifikáty byly smazány!')
        else:
            flash(f'Server {server} nebyl nalezen!', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Chyba při mazání serveru: {str(e)}', 'error')
    return redirect(url_for('sprava_serveru'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory('static',
                             'favicon.ico', 
                             mimetype='image/vnd.microsoft.icon')

@app.route('/get-certificates/<server>')
def get_certificates(server):
    try:
        certifikaty = Certifikat.query.filter_by(server=server)\
            .distinct(
                Certifikat.server,
                Certifikat.cesta,
                Certifikat.nazev,
                Certifikat.expirace
            )\
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

@app.route('/detail/<int:id>')
def detail_certifikatu(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        return render_template('detail_modal.html', certifikat=certifikat)
    except Exception as e:
        app.logger.error(f'Chyba při načítání detailu: {str(e)}')
        return f'Chyba při načítání detailu: {str(e)}', 500

@app.route('/reset-db')
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

@app.route('/smazat-db')
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

if __name__ == '__main__':
    with app.app_context():
        # Vytvoříme databázi pouze pokud neexistuje
        if not os.path.exists('certifikaty.db'):
            db.create_all()
            app.logger.info("Vytvořena nová databáze")
        else:
            app.logger.info("Použita existující databáze")
    
    # Zapneme debug mode
    app.run(debug=True, port=5000) 