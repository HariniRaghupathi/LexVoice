
import sqlite3
from pathlib import Path
from getpass import getpass
from werkzeug.security import generate_password_hash

DATABASE_PATH = Path(__file__).resolve().parent / "lexvoice.db"


def create_admin():
    print("\n================================")
    print("     LEXVOICE ADMIN SETUP")
    print("================================")

    username = input("Enter admin username: ").strip()

    if not username:
        print("Username cannot be empty.")
        return

    password = getpass("Enter admin password: ")
    confirm_password = getpass("Confirm admin password: ")

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    hashed_password = generate_password_hash(password)

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute("""
            INSERT INTO admins (username, password)
            VALUES (?, ?)
        """, (username, hashed_password))

        connection.commit()

        print("\nAdmin account created successfully!")
        print("You can now log in through the Admin Login page.")

    except sqlite3.IntegrityError:
        print("\nThis admin username already exists.")

    except sqlite3.Error as error:
        print("\nDatabase error:", error)

    finally:
        connection.close()


if __name__ == "__main__":
    create_admin()
