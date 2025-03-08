from datetime import datetime, timedelta
import pandas as pd

def allowed_file(filename, allowed_extensions={'xlsx', 'xls'}):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

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

def get_expiry_class(cert):
    """Vrací CSS třídu podle data expirace certifikátu"""
    if not cert.expirace:
        return ''
        
    today = datetime.now().date()
    expiry = cert.expirace.date() if isinstance(cert.expirace, datetime) else cert.expirace
    
    # Získáme první den následujícího měsíce
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    
    # Získáme první den přespříštího měsíce
    if next_month.month == 12:
        after_next_month = next_month.replace(year=next_month.year + 1, month=1, day=1)
    else:
        after_next_month = next_month.replace(month=next_month.month + 1, day=1)
    
    # Konec roku
    year_end = today.replace(month=12, day=31)
    
    if expiry < next_month:
        return 'cert-expired'  # Červená - končí tento měsíc
    elif expiry < after_next_month:
        return 'cert-warning'  # Oranžová - končí příští měsíc
    elif expiry <= year_end:
        return 'cert-ending-year'  # Modrá - končí tento rok
    
    return '' 