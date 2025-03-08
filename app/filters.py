from datetime import datetime

def days_until_expiry(expiry_date):
    """Vrátí počet dní do expirace."""
    if not expiry_date:
        return None
    today = datetime.now().date()
    return (expiry_date - today).days 