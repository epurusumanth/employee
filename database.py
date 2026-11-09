
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="sumanth@123",
        database="employee_attendance"
    )

if __name__ == "__main__":
    try:
        connection = get_connection()
        print("MySQL connected successfully!")
        connection.close()
    except mysql.connector.Error as error:
        print("Connection failed:", error)
