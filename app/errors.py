from flask import render_template, request
from app import db

def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        app.logger.error(f'Stránka nenalezena: {request.url}')
        return f"Stránka nenalezena: {request.url}", 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Interní chyba serveru: {str(error)}', exc_info=True)
        db.session.rollback()
        return "Interní chyba serveru", 500

    @app.errorhandler(413)
    def too_large(error):
        app.logger.error('Nahrávaný soubor je příliš velký')
        return 'Soubor je příliš velký', 413 