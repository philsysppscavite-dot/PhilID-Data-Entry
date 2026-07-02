"""
Uploads proof-of-delivery photos to a Google Drive folder so they survive
redeploys on hosts with ephemeral disks (Render, Railway, Heroku-style
platforms), and can be viewed/backed up straight from Drive.

Enabled automatically when GOOGLE_DRIVE_FOLDER_ID and
GOOGLE_SERVICE_ACCOUNT_JSON_B64 are set (see .env.example / README). If
either is missing, or the upload fails for any reason, callers should fall
back to local disk storage — this module never raises for "not configured",
it just reports is_configured() == False.
"""
import base64
import io
import json

_service = None
_service_build_attempted = False


def is_configured(app_config):
    return bool(app_config.get("GOOGLE_DRIVE_FOLDER_ID")) and bool(
        app_config.get("GOOGLE_SERVICE_ACCOUNT_JSON_B64")
    )


def _get_service(app_config):
    """Builds (and caches) the Drive API client from the base64-encoded
    service account JSON in config. Returns None if unavailable."""
    global _service, _service_build_attempted
    if _service is not None:
        return _service
    if _service_build_attempted:
        return None
    _service_build_attempted = True

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        raw = base64.b64decode(app_config["GOOGLE_SERVICE_ACCOUNT_JSON_B64"])
        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        _service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return _service
    except Exception:
        # Missing/invalid credentials, library not installed, network issue, etc.
        # Callers fall back to local storage in this case.
        _service = None
        return None


def upload_photo(app_config, file_storage, filename):
    """Uploads a Flask FileStorage object to the configured Drive folder.

    Returns the new file's Drive ID on success, or None on any failure
    (caller should fall back to local disk storage).
    """
    if not is_configured(app_config):
        return None

    service = _get_service(app_config)
    if service is None:
        return None

    try:
        from googleapiclient.http import MediaIoBaseUpload

        file_storage.stream.seek(0)
        data = file_storage.read()
        media = MediaIoBaseUpload(
            io.BytesIO(data), mimetype=file_storage.mimetype or "image/jpeg", resumable=False
        )
        metadata = {
            "name": filename,
            "parents": [app_config["GOOGLE_DRIVE_FOLDER_ID"]],
        }
        created = service.files().create(body=metadata, media_body=media, fields="id").execute()
        file_id = created.get("id")
        if not file_id:
            return None

        # Make the file viewable via a direct link (the folder itself should
        # already be shared with anyone who needs to view it; this just makes
        # sure the individual file link resolves without a sign-in prompt).
        try:
            service.permissions().create(
                fileId=file_id, body={"role": "reader", "type": "anyone"}
            ).execute()
        except Exception:
            pass  # Non-fatal: file still exists, might just need manual sharing.

        return file_id
    except Exception:
        return None


def delete_photo(app_config, file_id):
    """Best-effort delete of a Drive file. Failures are silently ignored."""
    if not file_id:
        return
    service = _get_service(app_config)
    if service is None:
        return
    try:
        service.files().delete(fileId=file_id).execute()
    except Exception:
        pass


def view_url(file_id):
    return f"https://drive.google.com/uc?export=view&id={file_id}"


def thumbnail_url(file_id, size=400):
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w{size}"
