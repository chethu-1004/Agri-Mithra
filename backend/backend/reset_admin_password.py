import sys
from getpass import getpass

from agrinetra.auth.password import hash_password
from agrinetra.database.connection import SessionLocal
from agrinetra.database.models import AdminUser


def main() -> int:
    email = input("Admin email: ").strip().lower()
    if not email:
        print("Admin email is required.")
        return 2

    password = getpass("New password (10+ characters): ")
    confirmation = getpass("Confirm new password: ")
    if password != confirmation:
        print("Passwords do not match.")
        return 2

    try:
        password_hash = hash_password(password)
    except ValueError as error:
        print(error)
        return 2

    with SessionLocal() as db:
        admin = db.query(AdminUser).filter(AdminUser.email == email).first()
        if admin is None:
            print("No admin account found for that email.")
            return 1
        admin.password_hash = password_hash
        db.commit()

    print("Admin password updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
