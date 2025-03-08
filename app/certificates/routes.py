from flask import Blueprint, request, jsonify, current_app, flash, redirect, url_for, render_template, send_from_directory
from app.models import Certifikat, Server
from app import db
from app.utils import allowed_file, is_valid_date
from datetime import datetime
import pandas as pd
import os
from werkzeug.utils import secure_filename
from openpyxl import Workbook
from app import get_expiry_class  # Přidejte tento import na začátek souboru

bp = Blueprint('certificates', __name__)

@bp.route('/pridat', methods=['GET', 'POST'])
def pridat_certifikat():
    if request.method == 'POST':
        try:
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
            flash('Certifikát byl úspěšně přidán!')
            return redirect(url_for('main.index'))
        except Exception as e:
            current_app.logger.error(f'Chyba při přidávání certifikátu: {str(e)}')
            flash(f'Chyba při přidávání certifikátu: {str(e)}')
            return redirect(url_for('certificates.pridat_certifikat'))
    
    servery = Server.query.all()
    return render_template('formular.html', certifikat=None, servery=servery)

@bp.route('/get-edit-form/<int:id>')
def get_edit_form(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        servery = Server.query.all()
        return render_template('edit_modal.html', certifikat=certifikat, servery=servery)
    except Exception as e:
        current_app.logger.error(f'Chyba při načítání editačního formuláře: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/upravit/<int:id>', methods=['POST'])
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
            current_app.logger.info(f'Certifikát {certifikat.nazev} byl úspěšně upraven')
            
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
        current_app.logger.error(f'Chyba při úpravě certifikátu: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Chyba při úpravě certifikátu: {str(e)}'
        }), 500

@bp.route('/smazat/<int:id>')
def smazat_certifikat(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        current_app.logger.info(f'Mazání certifikátu: {certifikat.nazev} ze serveru {certifikat.server}')
        db.session.delete(certifikat)
        db.session.commit()
        flash('Certifikát byl smazán!')
    except Exception as e:
        current_app.logger.error(f'Chyba při mazání certifikátu: {str(e)}')
        flash(f'Chyba při mazání certifikátu: {str(e)}')
    return redirect(url_for('main.index'))

@bp.route('/import-excel', methods=['POST'])
def import_excel():
    try:
        current_app.logger.info('Začátek importu z Excelu')
        if 'excel_file' not in request.files:
            current_app.logger.warning('Nebyl vybrán žádný soubor')
            return jsonify({'error': 'Nebyl vybrán žádný soubor'}), 400
        
        file = request.files['excel_file']
        if file.filename == '':
            current_app.logger.warning('Prázdný název souboru')
            return jsonify({'error': 'Nebyl vybrán žádný soubor'}), 400
        
        if not allowed_file(file.filename):
            current_app.logger.warning(f'Nepovolený typ souboru: {file.filename}')
            return jsonify({'error': 'Nepovolený typ souboru'}), 400
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        df = pd.read_excel(filepath)
        
        # Zpracování dat z Excelu
        df['Server'] = df['Server'].fillna(method='ffill')
        df['Cesta'] = df['Cesta'].fillna(method='ffill')
        df['Název certifikátu'] = df['Název certifikátu'].fillna('Neznámý certifikát')
        
        df = df.dropna(subset=['Server'])
        df = df[df['Expirace'].apply(is_valid_date)]
        
        # Import serverů
        unique_servers = df['Server'].unique()
        for server_name in unique_servers:
            if pd.isna(server_name):
                continue
            if not Server.query.filter_by(nazev=server_name).first():
                new_server = Server(nazev=server_name)
                db.session.add(new_server)
        db.session.commit()
        
        # Import certifikátů
        pridano = aktualizovano = beze_zmeny = 0
        
        for _, row in df.iterrows():
            expirace = datetime.strptime(row['Expirace'], '%d.%m.%Y').date() if isinstance(row['Expirace'], str) else row['Expirace'].date()
            
            existing = Certifikat.query.filter_by(
                server=row['Server'],
                cesta=row['Cesta'],
                nazev=row['Název certifikátu']
            ).first()
            
            if existing:
                if existing.expirace != expirace:
                    existing.expirace = expirace
                    aktualizovano += 1
                else:
                    beze_zmeny += 1
            else:
                new_cert = Certifikat(
                    server=row['Server'],
                    cesta=row['Cesta'],
                    nazev=row['Název certifikátu'],
                    expirace=expirace
                )
                db.session.add(new_cert)
                pridano += 1
                
        db.session.commit()
        os.remove(filepath)
        
        return jsonify({
            'success': True,
            'message': f'Import dokončen. Přidáno: {pridano}, Aktualizováno: {aktualizovano}'
        })
        
    except Exception as e:
        current_app.logger.error(f'Chyba při importu: {str(e)}', exc_info=True)
        return jsonify({
            'success': False,
            'message': f'Chyba při importu: {str(e)}'
        }), 400

@bp.route('/export-excel')
def export_excel():
    try:
        certifikaty = Certifikat.query.order_by(Certifikat.expirace).all()
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Certifikáty"
        
        headers = ['Server', 'Cesta', 'Název certifikátu', 'Expirace', 'Poznámka']
        ws.append(headers)
        
        for cert in certifikaty:
            ws.append([
                cert.server,
                cert.cesta,
                cert.nazev,
                cert.expirace.strftime('%d.%m.%Y'),
                cert.poznamka or ''
            ])
        
        for column in ws.columns:
            max_length = max(len(str(cell.value)) for cell in column)
            ws.column_dimensions[column[0].column_letter].width = max_length + 2
        
        filename = f'certifikaty_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        filepath = os.path.join(current_app.root_path, 'static', filename)
        wb.save(filepath)
        
        flash('Excel soubor byl úspěšně vytvořen!')
        return redirect(url_for('static', filename=filename))
        
    except Exception as e:
        flash(f'Chyba při exportu do Excelu: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@bp.route('/smazat-vse')
def smazat_vse():
    try:
        Certifikat.query.delete()
        db.session.commit()
        flash('Všechny certifikáty byly smazány!')
    except Exception as e:
        flash(f'Chyba při mazání: {str(e)}', 'error')
        db.session.rollback()
    return redirect(url_for('main.index'))

@bp.route('/detail/<int:id>')
def detail_certifikatu(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        return render_template('detail_modal.html', certifikat=certifikat)
    except Exception as e:
        current_app.logger.error(f'Chyba při načítání detailu: {str(e)}')
        return f'Chyba při načítání detailu: {str(e)}', 500

@bp.route('/get-certificates/<server>')
def get_certificates(server):
    try:
        certifikaty = Certifikat.query.filter_by(server=server)\
            .order_by(Certifikat.expirace, Certifikat.cesta).all()
        
        certs_data = [{
            'id': cert.id,
            'server': cert.server,
            'cesta': cert.cesta,
            'nazev': cert.nazev,
            'expirace': cert.expirace.strftime('%d.%m.%Y'),
            'expiry_class': get_expiry_class(cert)
        } for cert in certifikaty]
        
        return jsonify(certs_data)
    except Exception as e:
        current_app.logger.error(f'Chyba při načítání certifikátů: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/evidence_certifikatu/send-report', methods=['POST'])
def trigger_report():
    try:
        from app.tasks import send_monthly_certificate_report
        send_monthly_certificate_report()
        return jsonify({
            'success': True,
            'message': 'Report byl úspěšně odeslán'
        })
    except Exception as e:
        current_app.logger.error(f"Chyba při odesílání reportu: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Chyba při odesílání reportu: {str(e)}'
        }), 500

# ... další routy pro práci s certifikáty ... 