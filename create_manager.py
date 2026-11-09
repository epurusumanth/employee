from werkzeug.security import generate_password_hash
from database import get_connection

username = input("Enter manager username: ")
password = input("Enter manager password: ")

password_hash = generate_password_hash(password)

connection = get_connection()
cursor = connection.cursor()

try:
    cursor.execute(
        """
        INSERT INTO employees
        (employee_code, employee_name, department,
         username, password_hash, role)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (
            "MGR001",
            "System Manager",
            "Management",
            username,
            password_hash,
            "manager"
        )
    )

    connection.commit()
    print("Manager account created successfully!")

except Exception as e:
    connection.rollback()
    print("Error:", e)

finally:
    cursor.close()
    connection.close()