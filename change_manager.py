from werkzeug.security import generate_password_hash
from database import get_connection
import getpass

current_username = input("Current manager username: ").strip()
new_username = input("New manager username: ").strip()
new_password = input("New manager password (minimum 8 characters): ")

if not new_username or len(new_password) < 8:
    print("Username cannot be empty and password must be at least 8 characters.")
else:
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT employee_id FROM employees WHERE username = %s AND role = %s",
            (current_username, "manager")
        )
        manager = cursor.fetchone()

        if not manager:
            print("Manager account not found.")
        else:
            password_hash = generate_password_hash(new_password)

            cursor.execute(
                """
                UPDATE employees
                SET username = %s, password_hash = %s
                WHERE employee_id = %s
                """,
                (new_username, password_hash, manager[0])
            )

            connection.commit()
            print("Manager username and password updated successfully.")

    except Exception as error:
        connection.rollback()
        print("Update failed:", error)

    finally:
        cursor.close()
        connection.close()
