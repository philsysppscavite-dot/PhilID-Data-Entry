# CheckPoint — QR ID Check-In/Check-Out System

A Flask web app for scanning ID QR codes and logging time-in/time-out visits,
with cascading Province → City/Municipality → Barangay dropdowns built from
the Philippine Standard Geographic Code (PSGC), a staff dashboard, and
multi-user account management.

## Features

- **Webcam QR scanning** in the browser (no extra hardware/software needed)
- **Auto check-in/check-out**: scanning a known ID toggles between time-in
  and time-out automatically
- **New ID registration**: unrecognized IDs prompt a quick form (first /
  middle / last name + cascading Province / City-Municipality / Barangay
  dropdowns) before logging the first time-in
- **Dashboard** with live stats and a filterable, searchable data table of
  every scan (by name/ID, province, city, type, date range)
- **Search / Lookup page**: find a resident by scanning their QR code *or*
  typing a name/ID keyword, and view their full profile plus complete visit
  history — without logging a new time-in/out (useful for verification or
  answering "when did this person last check in?")
- **Multi-user accounts**: admins can create, disable, or delete staff
  accounts from the Manage Users page
- **42,000+ barangay records** pre-loaded from your PSGC spreadsheet

## Project structure

```
qr-checkin-system/
├── app.py                 # Flask app factory
├── config.py               # Configuration
├── extensions.py           # db / login_manager instances
├── models.py                # User, GeoBarangay, Resident, CheckLog
├── setup_db.py              # One-time DB init + geo import + first admin
├── requirements.txt
├── blueprints/
│   ├── auth.py               # Login, logout, user management
│   ├── main.py                # Dashboard, scan page views
│   └── api.py                 # Dropdown data + scan/register/logs JSON API
├── templates/                  # Jinja2 templates
├── static/
│   ├── css/style.css
│   ├── js/                      # dashboard.js, scan.js, app.js
│   └── img/                      # philsys.png, psa.png logos
└── data/
    └── geocode.csv               # Flattened PSGC data (region/province/city/barangay/geocode), imported by setup_db.py
```

## Setup

**Windows quick start:** just double-click **`run.bat`**. It creates a
virtual environment, installs dependencies, runs first-time database setup
(including the barangay import and admin account creation) the first time
only, then starts the app and opens it in your browser. Run it again any
time to start the server — it skips setup on subsequent runs.

**Manual setup** (any OS):

1. **Install dependencies** (Python 3.10+ recommended):

   ```bash
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Initialize the database** — creates tables, imports the barangay data,
   and walks you through creating the first admin account:

   ```bash
   python setup_db.py
   ```

3. **Run the app**:

   ```bash
   python app.py
   ```

   Visit `http://localhost:5000` and sign in with the admin account you
   just created.

4. **Camera access**: browsers only allow webcam access over `https://` or
   on `localhost`. Testing locally on `localhost:5000` works out of the
   box. If you deploy this to a server, put it behind HTTPS (e.g. via
   Let's Encrypt / a reverse proxy) or the QR scanner won't be allowed to
   access the camera.

## How the QR scan flow works

The scanner reads whatever text is encoded in the QR code and treats it as
the resident's unique **ID number**:

- If that ID number is already registered, a new log entry is created and
  automatically alternates between `IN` and `OUT` based on the resident's
  last log.
- If it's not yet registered, a form pops up to capture the resident's name
  and address (province/city/barangay), then registers them and logs their
  first time-in.

If your ID's QR code encodes something more complex (e.g. a JSON blob or a
PhilSys-specific format) rather than a plain ID number, adjust the
`handleDecodedText` function in `static/js/scan.js` to parse it before
sending it to `/api/scan`.

## Forgot your password / locked out

Run **`reset_admin.bat`** (Windows) or `python reset_admin.py` (any OS) from
the project folder. It lets you list existing accounts, reset any account's
password, or create a brand-new admin account — no need to touch the
database by hand.

## Adding more staff/admin accounts

Once logged in as an admin, go to **Manage Users** in the sidebar to create,
disable, or delete accounts. Staff accounts can scan IDs and view the
dashboard; admin accounts can additionally manage users.

## Pushing this to GitHub

Your repo: `https://github.com/philsysppscavite-dot/PhilID-Data-Entry.git`

From inside the `qr-checkin-system` folder:

```bash
git init
git add .
git commit -m "Initial commit: QR check-in/out system with search"
git branch -M main
git remote add origin https://github.com/philsysppscavite-dot/PhilID-Data-Entry.git
git push -u origin main
```

If the repo on GitHub already has a README, license, or other files in it,
`push` will be rejected because histories don't match. Either:

- Pull first and merge:
  ```bash
  git pull origin main --allow-unrelated-histories
  git push -u origin main
  ```
- Or, if the remote repo is empty or you don't need what's there, force-push
  (this **overwrites** whatever is currently on GitHub):
  ```bash
  git push -u origin main --force
  ```

## Uploading manually to GitHub (drag-and-drop, no git)

If you use GitHub's web uploader instead of `git push`, **do not drag in
these folders** — `git push` skips them automatically via `.gitignore`, but
the web uploader doesn't know about that file:

- `venv/` (your local Python environment — huge, and machine-specific)
- `instance/` (your local database — contains real check-in data, and
  regenerates itself on each machine)
- `__pycache__/` (compiled Python cache)
- `.env` (your secrets, if you created one — never upload this)

Everything else (`app.py`, `blueprints/`, `templates/`, `static/`, `data/`,
`requirements.txt`, `run.bat`, etc.) is safe and needed.

## Going live

The Flask dev server (`python app.py` / `run.bat`) is fine for testing but
isn't meant for real traffic. Before you go live, do this:

1. **Set a real SECRET_KEY.** Copy `.env.example` to `.env` and fill in a
   generated key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Paste the output as `SECRET_KEY=...` in `.env`. Without this, sessions
   reset every time the server restarts (everyone gets logged out).

2. **Make sure `FLASK_DEBUG` is `0` or unset.** Debug mode exposes a code
   execution console to anyone who can trigger an error page — never enable
   it on a public deployment.

3. **Use a production WSGI server, not the dev server:**
   - **Windows / local network:** run `serve_production.bat` (uses
     [Waitress](https://docs.pylonsproject.org/projects/waitress/)).
     By default it listens on port 8080 — pass a different port as an
     argument, e.g. `serve_production.bat 8000`.
   - **Linux / a cloud host (Render, Railway, a VPS, etc.):**
     ```bash
     gunicorn -w 4 -b 0.0.0.0:$PORT wsgi:app
     ```
     A `Procfile` is already included for platforms that use one
     (Render, Railway, Heroku-style hosts).

4. **HTTPS is required for the QR camera to work from any device other
   than the server itself.** Browsers block camera access on plain HTTP
   except on `localhost`. Options:
   - Deploy to a host that provides HTTPS automatically (Render, Railway,
     Fly.io, etc. all do this out of the box).
   - Or put the app behind a reverse proxy (nginx/Caddy) with a free
     Let's Encrypt certificate if you're self-hosting on your own server.

5. **First-time setup on the live server.** After deploying, run once
   (via your host's shell/console, or SSH):
   ```bash
   python setup_db.py
   ```
   If the host doesn't give you an interactive terminal, set
   `ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables first (see
   `.env.example`) and the script will create the admin account
   automatically instead of prompting.

6. **Database at scale.** SQLite (the default) is fine for a single
   checkpoint station or light multi-user use. If you expect many staff
   scanning simultaneously at high volume, set `DATABASE_URL` in `.env` to
   a Postgres/MySQL connection string instead — no code changes needed,
   Flask-SQLAlchemy handles either.

## Notes

- The SQLite database lives in `instance/checkin.db` and is git-ignored by
  default, so re-running `setup_db.py` on a fresh clone will rebuild it.
