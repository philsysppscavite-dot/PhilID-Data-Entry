"""
Recover access if you forgot the admin password, or need to create another
admin account without going through the app's Manage Users page.

Run:
    python reset_admin.py
"""
import getpass

from app import create_app
from extensions import db
from models import User


def list_users():
    users = User.query.order_by(User.created_at).all()
    if not users:
        print("\nNo user accounts exist yet.")
        return users

    print("\nExisting accounts:")
    for u in users:
        status = "active" if u.is_active_user else "disabled"
        print(f"  - {u.username}  ({u.role}, {status})")
    return users


def reset_password():
    users = list_users()
    if not users:
        return

    username = input("\nUsername to reset: ").strip()
    user = User.query.filter_by(username=username).first()
    if not user:
        print(f"No account found with username '{username}'.")
        return

    password = getpass.getpass("New password: ")
    confirm = getpass.getpass("Confirm new password: ")
    if password != confirm:
        print("Passwords did not match. Nothing was changed.")
        return
    if len(password) < 6:
        print("Password should be at least 6 characters. Nothing was changed.")
        return

    user.set_password(password)
    user.is_active_user = True
    db.session.commit()
    print(f"Password updated for '{username}'. The account is also now active/enabled.")


def create_admin():
    print("\nCreate a new admin account:")
    username = input("Username: ").strip()
    full_name = input("Full name: ").strip()

    if User.query.filter_by(username=username).first():
        print(f"A user named '{username}' already exists. Use option 2 to reset its password instead.")
        return

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords did not match. Nothing was created.")
        return
    if len(password) < 6:
        print("Password should be at least 6 characters. Nothing was created.")
        return

    user = User(username=username, full_name=full_name, role="admin")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f"Admin account '{username}' created.")


def main():
    app = create_app()
    with app.app_context():
        print("=" * 44)
        print("  CheckPoint - Account Recovery")
        print("=" * 44)
        print("1. List existing accounts")
        print("2. Reset a password")
        print("3. Create a new admin account")
        choice = input("\nChoose an option (1-3): ").strip()

        if choice == "1":
            list_users()
        elif choice == "2":
            reset_password()
        elif choice == "3":
            create_admin()
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
