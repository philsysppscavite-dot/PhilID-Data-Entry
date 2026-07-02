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

    # Render's Postgres (and most managed Postgres hosts) silently closes
    # connections that sit idle for a while. Without these options,
    # SQLAlchemy can hand out one of those dead connections from its pool
    # and the first query on it fails with:
    #   sqlalchemy.exc.OperationalError: (psycopg2.OperationalError)
    #   SSL SYSCALL error: EOF detected
    # pool_pre_ping issues a cheap "is this connection still alive?" check
    # before every checkout and transparently reconnects if not.
    # pool_recycle proactively replaces connections older than 5 minutes so
    # they never get old enough for the host to kill them out from under us.
    # This is a no-op on SQLite (it has no such server-side idle timeout).
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Set FLASK_DEBUG=1 in your environment for local development only.
    # Never enable debug mode on a live/public deployment.
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    PORT = int(os.environ.get("PORT", 5000))
    HOST = os.environ.get("HOST", "0.0.0.0")

    # Delivery proof-of-delivery photos are stored here (served as static files).
    # This is used automatically as a FALLBACK whenever Google Drive storage
    # (below) isn't configured, or if an upload to Drive fails.
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "delivery")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8 MB per upload (photo)
    ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

    # ---- Google Drive photo storage (recommended for production) ----
    # Local disk storage doesn't survive a redeploy on most cloud hosts
    # (Render/Railway/Heroku-style platforms wipe the filesystem on every
    # deploy). Uploading proof-of-delivery photos to a Google Drive folder
    # instead keeps them safe and viewable from anywhere.
    #
    # Set these two env vars to enable it (see .env.example and the
    # "Google Drive photo storage" section of the README for setup steps):
    #   GOOGLE_DRIVE_FOLDER_ID           - the target Drive folder's ID
    #   GOOGLE_SERVICE_ACCOUNT_JSON_B64  - base64-encoded service account key
    #
    # If either is missing, the app automatically falls back to local disk
    # storage above, so everything still works out of the box.
    GOOGLE_DRIVE_FOLDER_ID = os.environ.get(
        "GOOGLE_DRIVE_FOLDER_ID", "18pKt_-d9igumU2E72tS5VupEYSg0tukF"
    )
    GOOGLE_SERVICE_ACCOUNT_JSON_B64 = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "")

    # ---- GPS verification for ID delivery (checkout / resolve flow) ----
    # Checks the rider's phone GPS against the resident's address/barangay
    # via the Google Maps Geocoding API. Set GOOGLE_MAPS_API_KEY to enable;
    # leave blank to skip the check (GPS is still recorded either way).
    GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

    # How close (in meters) the rider's GPS must be to count as a match.
    # Exact street address match uses the tighter radius; falling back to
    # just the barangay centroid (since barangays can be large) uses the
    # wider one.
    DELIVERY_GPS_ADDRESS_RADIUS_M = int(os.environ.get("DELIVERY_GPS_ADDRESS_RADIUS_M", 300))
    DELIVERY_GPS_BARANGAY_RADIUS_M = int(os.environ.get("DELIVERY_GPS_BARANGAY_RADIUS_M", 4000))

    # What happens when a rider's GPS doesn't match the resident's address
    # or barangay on a "delivered" resolution:
    #   False (default) -- allow it, just flag the record for review
    #   True             -- block the submission; rider must retry or mark
    #                        the delivery "returned" instead
    DELIVERY_GPS_HARD_BLOCK = os.environ.get("DELIVERY_GPS_HARD_BLOCK", "false").lower() in ("1", "true", "yes")
