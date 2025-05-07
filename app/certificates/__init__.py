from flask import Blueprint

bp = Blueprint('certificates', __name__)

from . import routes 