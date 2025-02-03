from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nazev = db.Column(db.String(100), unique=True, nullable=False)
    certifikaty = db.relationship('Certifikat', backref='server_obj', lazy=True)

class Certifikat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server = db.Column(db.String(100), db.ForeignKey('server.nazev'), nullable=False)
    cesta = db.Column(db.String(200), nullable=False)
    nazev = db.Column(db.String(100), nullable=False)
    expirace = db.Column(db.Date, nullable=False)
    poznamka = db.Column(db.Text)
    vytvoreno = db.Column(db.DateTime, default=datetime.utcnow) 