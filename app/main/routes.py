from flask import Blueprint, render_template, current_app, jsonify
from app.models import Certifikat, Server
from datetime import datetime

bp = Blueprint('main', __name__)

@bp.route('/')
@bp.route('/evidence_certifikatu')
@bp.route('/evidence_certifikatu/')
def index():
    try:
        # Načteme všechny servery
        servery = Server.query.all()
        servery_nazvy = [server.nazev for server in servery]
        
        # Načteme aktivní server z prvního serveru v seznamu
        aktivni_server = servery_nazvy[0] if servery_nazvy else None
        
        # Načteme certifikáty pro aktivní server
        if aktivni_server:
            certifikaty = Certifikat.query.filter_by(server=aktivni_server)\
                .order_by(Certifikat.expirace, Certifikat.cesta).all()
        else:
            certifikaty = []
        
        return render_template('index.html',
                             certifikaty=certifikaty,
                             servery=servery_nazvy,
                             aktivni_server=aktivni_server)
                             
    except Exception as e:
        current_app.logger.error(f'Chyba při načítání hlavní stránky: {str(e)}')
        return f"Došlo k chybě: {str(e)}", 500 

@bp.route('/detail/<int:id>')
def detail(id):
    try:
        certifikat = Certifikat.query.get_or_404(id)
        today = datetime.now().date()  # Přidáme dnešní datum
        return render_template('detail_modal.html', 
                              certifikat=certifikat,
                              today=today)  # Předáme today do šablony
    except Exception as e:
        current_app.logger.error(f'Chyba při načítání detailu: {str(e)}')
        return jsonify({'error': str(e)}), 500 