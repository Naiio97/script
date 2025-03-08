from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config
from logging.handlers import RotatingFileHandler
import logging
import os
from datetime import datetime
from app.utils import get_expiry_class
from app.filters import days_until_expiry

db = SQLAlchemy()

def create_app():
    app = Flask(__name__,
                static_url_path='',  # Změníme na prázdný string
                static_folder='../static')  # Cesta k static složce relativně k app složce
    app.config.from_object(Config)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # Inicializace databáze
    db.init_app(app)
    
    # Registrace filteru
    app.jinja_env.filters['get_expiry_class'] = get_expiry_class
    app.jinja_env.filters['days_until_expiry'] = days_until_expiry
    
    # Registrace blueprintů
    from app.main.routes import bp as main_bp
    app.register_blueprint(main_bp, url_prefix='/evidence_certifikatu')
    
    from app.certificates.routes import bp as certificates_bp
    app.register_blueprint(certificates_bp, url_prefix='/evidence_certifikatu')
    
    from app.servers.routes import bp as servers_bp
    app.register_blueprint(servers_bp, url_prefix='/evidence_certifikatu')
    
    from app.main.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/evidence_certifikatu')
    
    return app

def setup_logging(app):
    if not os.path.exists('logs'):
        os.makedirs('logs')
        
    file_handler = RotatingFileHandler(
        'logs/app.log',
        maxBytes=10*1024*1024,
        backupCount=10,
        encoding='utf-8'
    )
    
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s (in %(pathname)s:%(lineno)d)'
    )
    file_handler.setFormatter(formatter)
    
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Aplikace spuštěna')