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

## Notes

- The SQLite database lives in `instance/checkin.db` and is git-ignored by
  default, so re-running `setup_db.py` on a fresh clone will rebuild it.
- For production use, set a real `SECRET_KEY` environment variable instead
  of the default in `config.py`, and consider switching
  `SQLALCHEMY_DATABASE_URI` to Postgres/MySQL if you expect concurrent
  writes at scale.
