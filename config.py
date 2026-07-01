import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    # In production, ALWAYS set a real SECRET_KEY environment variable.
    # This auto-generates a random one as a fallback so the app still runs
    # out of the box, but sessions will be invalidated every time the app
    # restarts unless you set SECRET_KEY yourself.
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'checkin.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Set FLASK_DEBUG=1 in your environment for local development only.
    # Never enable debug mode on a live/public deployment.
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    PORT = int(os.environ.get("PORT", 5000))
    HOST = os.environ.get("HOST", "0.0.0.0")
