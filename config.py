import os

class Config:
    APPLICATION_ROOT = '/evidence_certifikatu'
    DEBUG = True
    SECRET_KEY = 'tajny_klic'  # v produkci by měl být bezpečnější
    SQLALCHEMY_DATABASE_URI = 'sqlite:///certifikaty.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Konfigurace pro upload souborů
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    
    # Email konfigurace
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Vytvoření potřebných složek
    @staticmethod
    def init_app(app):
        # Vytvoříme složku pro uploady
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER']) 