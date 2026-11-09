from getpass import getpass
from sqlalchemy.exc import IntegrityError

from agrinetra.database.connection import SessionLocal
from agrinetra.database.models import AdminUser
from agrinetra.auth.password import hash_password


def create_admin():
    print("\n========== AGRI MITRA ADMIN SETUP ==========\n")

    name = input("Enter admin name: ").strip()
    email = input("Enter admin email: ").strip().lower()
    password = getpass("Enter admin password (minimum 12 characters): ")
    confirm_password = getpass("Confirm admin password: ")

    if not name:
        print("ERROR: Admin name cannot be empty.")
        return

    if not email or "@" not in email:
        print("ERROR: Enter a valid email address.")
        return

    if len(password) < 12:
        print("ERROR: Password must contain at least 12 characters.")
        return

    if password != confirm_password:
        print("ERROR: Passwords do not match.")
        return

    db = SessionLocal()

    try:
        existing_admin = (
            db.query(AdminUser)
            .filter(AdminUser.email == email)
            .first()
        )

        if existing_admin:
            print(f"An admin account already exists for {email}.")
            print("No account was created.")
            return

        admin = AdminUser(
            name=name,
            email=email,
            password_hash=hash_password(password),
            role="ADMIN",
            status="ACTIVE",
        )

        db.add(admin)
        db.commit()

        print("\nSUCCESS: Admin account created!")
        print(f"Name: {admin.name}")
        print(f"Email: {admin.email}")
        print(f"Role: {admin.role}")
        print(f"Status: {admin.status}")
        print("\nYou can now try logging in through the Agri Mitra admin login.")

    except IntegrityError:
        db.rollback()
        print("ERROR: An account with this email may already exist.")

    except Exception as exc:
        db.rollback()
        print(f"ERROR: Could not create admin account: {exc}")

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
