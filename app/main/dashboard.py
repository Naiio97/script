from flask import Blueprint, render_template, flash, redirect, url_for, current_app
from app.models import Certifikat
from datetime import datetime

bp = Blueprint('dashboard', __name__)

@bp.route('/dashboard')
def index():
    try:
        today = datetime.now().date()
        
        ending_certs = Certifikat.query.filter(
            Certifikat.expirace.between(today, datetime(today.year, 12, 31).date())
        ).order_by(Certifikat.expirace).all()
        
        # Spočítáme statistiky
        stats = {
            'critical': sum(1 for cert in ending_certs if (cert.expirace - today).days <= 30),
            'warning': sum(1 for cert in ending_certs if 30 < (cert.expirace - today).days <= 60),
            'this_year': len(ending_certs)
        }
        
        # Statistiky podle serverů
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
        return redirect(url_for('main.index')) 