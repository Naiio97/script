from flask import Blueprint

bp = Blueprint('main', __name__, url_prefix='/evidence_certifikatu')

from . import routes 