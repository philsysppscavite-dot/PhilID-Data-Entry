"""
Entry point for production WSGI servers.

Local Windows production run:
    waitress-serve --port=8080 wsgi:app

Linux/Mac production run:
    gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
"""
from app import app  # noqa: F401
