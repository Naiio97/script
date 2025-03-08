from flask import Blueprint, request, jsonify, current_app, flash, redirect, url_for, render_template
from app.models import Server, Certifikat
from app import db
from datetime import datetime

bp = Blueprint('servers', __name__)

@bp.route('/servery')
def seznam_serveru():
    try:
        servery_s_pocty = db.session.query(
            Server,
            db.func.count(Certifikat.id).label('pocet_certifikatu')
        ).outerjoin(
            Certifikat,
            Server.nazev == Certifikat.server
        ).group_by(Server.id).all()
        
        servery_data = [{
            'id': server.id,
            'nazev': server.nazev,
            'popis': server.popis,
            'vytvoreno': server.vytvoreno,
            'pocet_certifikatu': pocet
        } for server, pocet in servery_s_pocty]
        
        return render_template('servery.html', servery=servery_data)
    except Exception as e:
        current_app.logger.error(f'Chyba při načítání seznamu serverů: {str(e)}')
        flash(f'Chyba při načítání seznamu serverů: {str(e)}', 'error')
        return redirect(url_for('main.index'))

@bp.route('/servery/pridat', methods=['GET', 'POST'])
def pridat_server():
    if request.method == 'POST':
        nazev = request.form['nazev']
        popis = request.form.get('popis', '')
        
        try:
            existujici = Server.query.filter_by(nazev=nazev).first()
            if existujici:
                return jsonify({
                    'success': False,
                    'message': f'Server {nazev} již existuje!'
                })
            
            server = Server(nazev=nazev, popis=popis)
            db.session.add(server)
            db.session.commit()
            flash(f'Server {nazev} byl úspěšně přidán!', 'success')
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Chyba při přidávání serveru: {str(e)}')
            return jsonify({
                'success': False,
                'message': f'Chyba při přidávání serveru: {str(e)}'
            })
    
    return render_template('server_edit_modal.html', server=None)

@bp.route('/servery/detail/<int:id>')
def detail_serveru(id):
    try:
        server = Server.query.get_or_404(id)
        pocet_certifikatu = Certifikat.query.filter_by(server=server.nazev).count()
        return render_template('server_detail_modal.html', 
                             server=server,
                             pocet_certifikatu=pocet_certifikatu)
    except Exception as e:
        current_app.logger.error(f'Chyba při načítání detailu serveru: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/servery/upravit/<int:id>', methods=['GET', 'POST'])
def upravit_server(id):
    try:
        server = Server.query.get_or_404(id)
        
        if request.method == 'POST':
            server.nazev = request.form['nazev']
            server.popis = request.form.get('popis', '')
            db.session.commit()
            current_app.logger.info(f'Server {server.nazev} byl úspěšně upraven')
            return jsonify({
                'success': True,
                'message': 'Server byl úspěšně upraven'
            })
        
        return render_template('server_edit_modal.html', server=server)
    except Exception as e:
        current_app.logger.error(f'Chyba při úpravě serveru: {str(e)}')
        return jsonify({
            'success': False,
            'message': f'Chyba při úpravě serveru: {str(e)}'
        }), 500

@bp.route('/servery/smazat/<int:id>')
def smazat_server(id):
    try:
        server = Server.query.get_or_404(id)
        nazev = server.nazev
        
        # Nejdřív smažeme všechny certifikáty serveru
        Certifikat.query.filter_by(server=server.nazev).delete()
        
        # Pak smažeme server
        db.session.delete(server)
        db.session.commit()
        
        flash(f'Server {nazev} byl úspěšně smazán', 'success')
        return redirect(url_for('servers.seznam_serveru'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Chyba při mazání serveru: {str(e)}')
        flash(f'Chyba při mazání serveru: {str(e)}', 'error')
        return redirect(url_for('servers.seznam_serveru'))

# Přidáme alias pro zpětnou kompatibilitu
@bp.route('/servery/index')
def index():
    return seznam_serveru()

# Přidáme alias pro kořenovou cestu blueprintu
@bp.route('/')
def root_index():
    return seznam_serveru()

# ... další routy pro práci se servery ... 