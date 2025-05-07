from app import create_app, db
from app.models import Certifikat, Server
from flask import redirect, url_for

app = create_app()

@app.route('/')
def root():
    return redirect('/evidence_certifikatu')

@app.route('/evidence_certifikatu/')
def remove_slash():
    return redirect('/evidence_certifikatu')

# Vytvoření databáze
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)