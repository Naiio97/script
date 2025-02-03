from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from models import db, Certifikat, Server
from datetime import datetime, timedelta
import pandas as pd
from openpyxl import Workbook
import os
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
# Přidáme debug výpisy
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'tajny_klic'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///certifikaty.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializace databáze
db.init_app(app)

@app.route('/')
def index():
    try:
        # Získáme všechny servery
        servery = Server.query.all()
        servery_nazvy = [server.nazev for server in servery]
        
        # Získáme vybraný server z URL parametru nebo první v seznamu
        aktivni_server = request.args.get('server', servery_nazvy[0] if servery_nazvy else None)
        
        # Získáme certifikáty pro vybraný server
        if aktivni_server:
            certifikaty = Certifikat.query.filter_by(server=aktivni_server)\
                .order_by(Certifikat.expirace).all()
        else:
            certifikaty = []
            
        return render_template('index.html', 
                             certifikaty=certifikaty, 
                             servery=servery_nazvy, 
                             aktivni_server=aktivni_server)
    except Exception as e:
        print(f"Chyba: {str(e)}")
        return f"Došlo k chybě: {str(e)}", 500

@app.route('/pridat', methods=['GET', 'POST'])
def pridat_certifikat():
    if request.method == 'POST':
        novy_cert = Certifikat(
            server=request.form['server'],
            cesta=request.form['cesta'],
            nazev=request.form['nazev'],
            expirace=datetime.strptime(request.form['expirace'], '%Y-%m-%d'),
            poznamka=request.form.get('poznamka', '')
        )
        db.session.add(novy_cert)
        db.session.commit()
        flash('Certifikát byl úspěšně přidán!')
        return redirect(url_for('index'))
    
    # Získáme seznam všech serverů pro select
    servery = Server.query.order_by(Server.nazev).all()
    return render_template('formular.html', servery=servery)

@app.route('/upravit/<int:id>', methods=['GET', 'POST'])
def upravit_certifikat(id):
    certifikat = Certifikat.query.get_or_404(id)
    if request.method == 'POST':
        certifikat.server = request.form['server']
        certifikat.cesta = request.form['cesta']
        certifikat.nazev = request.form['nazev']
        certifikat.expirace = datetime.strptime(request.form['expirace'], '%Y-%m-%d')
        certifikat.poznamka = request.form.get('poznamka', '')
        db.session.commit()
        flash('Certifikát byl úspěšně upraven!')
        return redirect(url_for('index'))
    return render_template('formular.html', certifikat=certifikat)

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

@app.route('/import-excel')
def import_excel():
    try:
        # Načtení Excel souboru
        df = pd.read_excel("./certy_uat.xlsx")
        
        # Debug výpis - podíváme se na názvy sloupců
        print("Názvy sloupců v Excelu:", df.columns.tolist())
        
        # Vyplnění prázdných hodnot
        df['Server'] = df['Server'].fillna(method='ffill')
        df['Cesta'] = df['Cesta'].fillna(method='ffill')
        
        # Filtrování řádků (přeskočíme "Neřešíme" atd. a NaN hodnoty)
        ignorovat = ["Neřešíme", "Neřešime", "Automaticky", "Automacticky", 
                    "?????", "Expirace", "Expirace ", ""]
        df = df[~df['Expirace'].astype(str).isin(ignorovat)]
        
        # Odstraníme řádky s NaN hodnotami v klíčových sloupcích
        nazev_sloupce = 'Název certifikátu'  # Upravený název sloupce
        df = df.dropna(subset=[nazev_sloupce, 'Expirace'])
        
        # Import každého řádku do databáze
        pocet = 0
        for _, radek in df.iterrows():
            try:
                # Převod data na správný formát
                datum_expirace = pd.to_datetime(radek['Expirace']).date()
                
                # Vytvoření nového záznamu
                cert = Certifikat(
                    server=str(radek['Server']),
                    cesta=str(radek['Cesta']),
                    nazev=str(radek[nazev_sloupce]),  # Použijeme správný název sloupce
                    expirace=datum_expirace,
                    poznamka=None
                )
                db.session.add(cert)
                pocet += 1
            except Exception as e:
                print(f"Chyba při importu řádku: {str(e)}")
                continue
        
        # Uložení všech změn
        db.session.commit()
        flash(f'Úspěšně importováno {pocet} certifikátů!')
        
    except Exception as e:
        flash(f'Chyba při importu: {str(e)}', 'error')
        db.session.rollback()
        print(f"Detailní chyba: {str(e)}")  # Pro lepší debugování
    
    return redirect(url_for('index'))

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

# Přidáme funkci pro určení třídy podle data expirace
def get_expiry_class(cert):
    today = datetime.now().date()
    expiry = cert.expirace
    days_left = (expiry - today).days
    
    if days_left <= 30:
        return 'expiring-critical'
    elif days_left <= 60:
        return 'expiring-warning'
    elif expiry.year == today.year:
        return 'expiring-info'
    return ''

# Přidáme funkci pro kontrolu certifikátů
def check_certificates():
    with app.app_context():
        try:
            today = datetime.now().date()
            expiring_certs = Certifikat.query.filter(
                Certifikat.expirace <= today + timedelta(days=60)
            ).all()
            
            if expiring_certs:
                # Zde můžete implementovat notifikace (email, Slack, atd.)
                print(f"Nalezeno {len(expiring_certs)} certifikátů končících v příštích 60 dnech:")
                for cert in expiring_certs:
                    print(f"- {cert.server}: {cert.nazev} končí {cert.expirace.strftime('%d.%m.%Y')}")
        except Exception as e:
            print(f"Chyba při kontrole certifikátů: {str(e)}")

# Nastavení plánovače
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_certificates, trigger="interval", seconds=30)  # kontrola každých 30 sekund
scheduler.start()

# Zastavení plánovače při ukončení aplikace
atexit.register(lambda: scheduler.shutdown())

# Přidáme filtr pro šablony
app.jinja_env.filters['get_expiry_class'] = get_expiry_class

@app.route('/dashboard')
def dashboard():
    try:
        today = datetime.now().date()
        
        # Statistiky pouze pro končící certifikáty
        stats = {
            'critical': Certifikat.query.filter(  # Končí tento měsíc
                Certifikat.expirace.between(today, today + timedelta(days=30))
            ).count(),
            'warning': Certifikat.query.filter(   # Končí do dvou měsíců
                Certifikat.expirace.between(today + timedelta(days=31), today + timedelta(days=60))
            ).count(),
            'this_year': Certifikat.query.filter( # Končí tento rok
                Certifikat.expirace.between(today, datetime(today.year, 12, 31).date())
            ).count()
        }
        
        # Seznam certifikátů končících tento rok (již seřazený podle expirace)
        ending_certs = Certifikat.query.filter(
            Certifikat.expirace.between(today, datetime(today.year, 12, 31).date())
        ).order_by(Certifikat.expirace).all()
        
        # Počet končících certifikátů podle serverů (seřazený podle počtu certifikátů)
        server_stats = db.session.query(
            Certifikat.server, 
            db.func.count(Certifikat.id).label('count')
        ).filter(
            Certifikat.expirace.between(today, datetime(today.year, 12, 31).date())
        ).group_by(Certifikat.server)\
        .order_by(db.text('count DESC')).all()  # Seřazení podle počtu sestupně
        
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
        response.mimetype = 'text/css'
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

if __name__ == '__main__':
    with app.app_context():
        try:
            # Vytvoření všech tabulek
            db.create_all()
            print("Databáze byla úspěšně vytvořena")
        except Exception as e:
            print(f"Chyba při vytváření databáze: {str(e)}")
    
    app.run(debug=True, port=5002) 