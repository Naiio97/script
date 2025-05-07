from flask import Blueprint

bp = Blueprint('servers', __name__)

from . import routes 