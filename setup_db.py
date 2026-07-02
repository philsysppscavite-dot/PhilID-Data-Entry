"""
Run this once after installing dependencies:

    python setup_db.py

It will:
  1. Create all database tables.
  2. Import the barangay/city/province reference data from data/geocode.csv
     (skipped automatically if already imported).
  3. Prompt you to create the first admin account (skipped if a user already
     exists).
"""
import csv
import getpass
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from extensions import db
from models import GeoBarangay, User

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
CSV_PATH = os.path.join(BASE_DIR, "data", "geocode.csv")


def import_geo_data():
    if GeoBarangay.query.first():
        print("Geo data already imported, skipping.")
        return

    if not os.path.exists(CSV_PATH):
        print(f"WARNING: {CSV_PATH} not found. Skipping geo data import.")
        return

    print("Importing barangay/city/province data, this may take a minute...")
    batch = []
    seen_geocodes = set()
    skipped = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            geocode = (row.get("geocode") or "").strip()
            if not geocode or geocode in seen_geocodes:
                skipped += 1
                continue
            seen_geocodes.add(geocode)
            batch.append(
                GeoBarangay(
                    region=row["region"],
                    province=row["province"],
                    city_municipality=row["city_municipality"],
                    barangay=row["barangay"],
                    geocode=geocode,
                )
            )
            if len(batch) >= 2000:
                db.session.bulk_save_objects(batch)
                db.session.commit()
                batch = []
        if batch:
            db.session.bulk_save_objects(batch)
            db.session.commit()

    total = GeoBarangay.query.count()
    print(f"Imported {total} barangay records.")
    if skipped:
        print(f"Skipped {skipped} duplicate/blank geocode row(s) in the source CSV.")


def create_first_admin():
    if User.query.first():
        print("A user account already exists, skipping admin creation.")
        return

    # Non-interactive path: useful for cloud deploys run from a one-off
    # command/shell where there's no interactive stdin.
    env_username = os.environ.get("ADMIN_USERNAME")
    env_password = os.environ.get("ADMIN_PASSWORD")
    env_full_name = os.environ.get("ADMIN_FULL_NAME", "Administrator")

    if env_username and env_password:
        user = User(username=env_username, full_name=env_full_name, role="admin")
        user.set_password(env_password)
        db.session.add(user)
        db.session.commit()
        print(f"Admin account '{env_username}' created from ADMIN_USERNAME/ADMIN_PASSWORD env vars.")
        return

    if not sys.stdin.isatty():
        print(
            "\nNo user accounts found, and no interactive terminal is available "
            "to create one here.\nSet ADMIN_USERNAME and ADMIN_PASSWORD environment "
            "variables and re-run this script,\nor run 'python reset_admin.py' from "
            "an interactive shell/console instead."
        )
        return

    print("\nNo user accounts found. Let's create the first admin account.")
    username = input("Admin username: ").strip()
    full_name = input("Full name: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords did not match. Run this script again to retry.")
        return

    user = User(username=username, full_name=full_name, role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f"Admin account '{username}' created. You can now log in.")


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        import_geo_data()
        create_first_admin()


if __name__ == "__main__":
    main()
