from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from app.models import Certifikat
from datetime import datetime, date, timedelta
import calendar

def check_certificates():
    """Kontrola certifikátů s blížící se expirací"""
    with current_app.app_context():
        try:
            today = datetime.now().date()
            expiring_certs = Certifikat.query.filter(
                Certifikat.expirace <= today + timedelta(days=60)
            ).all()
            
            current_app.logger.info(f"Kontrola certifikátů: nalezeno {len(expiring_certs)} končících certifikátů")
        except Exception as e:
            current_app.logger.error(f"Chyba při kontrole certifikátů: {str(e)}")

def send_monthly_certificate_report():
    """Odešle měsíční report o končících certifikátech"""
    with current_app.app_context():
        today = date.today()
        _, last_day = calendar.monthrange(today.year, today.month)
        month_end = date(today.year, today.month, last_day)
        
        try:
            ending_certs = Certifikat.query.filter(
                Certifikat.expirace.between(today, month_end)
            ).order_by(Certifikat.expirace).all()
            
            if ending_certs:
                current_app.logger.info(f"Měsíční report: {len(ending_certs)} certifikátů končí tento měsíc")
                # Zde můžete implementovat odesílání e-mailu
            else:
                current_app.logger.info("Měsíční report: Žádné certifikáty tento měsíc nekončí")
                
        except Exception as e:
            current_app.logger.error(f"Chyba při generování měsíčního reportu: {str(e)}")

def init_scheduler(app):
    """Inicializace plánovače úloh"""
    scheduler = BackgroundScheduler()
    
    # Kontrola certifikátů každý den v 8:00
    scheduler.add_job(
        check_certificates,
        'cron',
        hour=8,
        minute=0
    )
    
    # Měsíční report první den v měsíci v 8:00
    scheduler.add_job(
        send_monthly_certificate_report,
        'cron',
        day=1,
        hour=8,
        minute=0
    )
    
    scheduler.start()
    app.logger.info("Plánovač úloh byl inicializován")
    return scheduler 