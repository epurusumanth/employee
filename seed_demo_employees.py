import random
from datetime import date, time, timedelta

from werkzeug.security import generate_password_hash
from database import get_connection

EMPLOYEE_COUNT = 500
DEMO_PASSWORD = "Demo@12345"
RANDOM_SEED = 20261026

FIRST_NAMES = [
    "Aarav", "Aadhya", "Abhinav", "Aditya", "Aishwarya", "Akash", "Akshara",
    "Amar", "Ananya", "Anil", "Anjali", "Arjun", "Bhavana", "Charan",
    "Deepak", "Divya", "Gowtham", "Harika", "Harish", "Ishita", "Karthik",
    "Keerthi", "Kiran", "Lakshmi", "Madhav", "Manasa", "Meghana", "Naveen",
    "Nikhil", "Pooja", "Pranav", "Priya", "Rahul", "Rakesh", "Sahana",
    "Sai", "Sanjana", "Sandeep", "Sanjay", "Shreya", "Siddharth", "Sneha",
    "Sowmya", "Srinivas", "Teja", "Varun", "Venkatesh", "Vishal", "Yamini",
    "Abhiram", "Anusha", "Bharath", "Chandana", "Dinesh", "Jahnavi", "Manoj",
    "Nandini", "Pavan", "Praveen", "Rohit", "Sravani", "Tarun", "Uday",
]
LAST_NAMES = [
    "Reddy", "Kumar", "Rao", "Sharma", "Naidu", "Varma", "Patel", "Singh",
    "Gupta", "Chowdary", "Prasad", "Murthy", "Shetty", "Joshi", "Das",
    "Verma", "Yadav", "Mishra", "Pillai", "Nair", "Babu", "Goud",
]
DEPARTMENTS = [
    "IT", "Human Resources", "Finance", "Sales", "Marketing",
    "Operations", "Engineering", "Customer Support", "Administration",
    "Quality Assurance",
]


def working_dates(start_date, end_date):
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def choose_attendance(rng):
    roll = rng.random()
    if roll < 0.02:
        return "Holiday"
    if roll < 0.05:
        return "Leave"
    if roll < 0.12:
        return "Absent"
    return "Present"


def make_times(status, rng):
    if status != "Present":
        return None, None

    # Late/incomplete shifts are represented by their times because many
    # MySQL projects define status as ENUM('Present','Absent','Leave','Holiday').
    if rng.random() < 0.18:
        check_in_minutes = rng.randint(9 * 60 + 16, 10 * 60 + 15)
    else:
        check_in_minutes = rng.randint(8 * 60 + 40, 9 * 60 + 15)

    if rng.random() < 0.10:
        duration_minutes = rng.randint(5 * 60 + 30, 7 * 60 + 45)
    else:
        duration_minutes = rng.randint(8 * 60, 9 * 60 + 30)

    check_out_minutes = min(check_in_minutes + duration_minutes, 23 * 60 + 59)
    check_in = time(check_in_minutes // 60, check_in_minutes % 60, rng.randint(0, 59))
    check_out = time(check_out_minutes // 60, check_out_minutes % 60, rng.randint(0, 59))
    return check_in, check_out


def main():
    rng = random.Random(RANDOM_SEED)
    connection = get_connection()
    cursor = connection.cursor()

    inserted_employees = 0
    reused_employees = 0
    inserted_attendance = 0
    skipped_attendance = 0

    try:
        cursor.execute("SHOW COLUMNS FROM attendance LIKE 'status'")
        if not cursor.fetchone():
            raise RuntimeError("Could not find attendance.status column.")

        password_hash = generate_password_hash(DEMO_PASSWORD)
        demo_employees = []

        for index in range(1, EMPLOYEE_COUNT + 1):
            employee_code = f"DEMO{index:04d}"
            username = f"demoemp{index:04d}"

            cursor.execute(
                "SELECT employee_id, employee_code, username FROM employees "
                "WHERE employee_code = %s OR username = %s",
                (employee_code, username),
            )
            existing = cursor.fetchone()

            if existing:
                cursor.execute(
                    "SELECT employee_id FROM employees "
                    "WHERE employee_code = %s AND username = %s AND role = %s",
                    (employee_code, username, "employee"),
                )
                exact = cursor.fetchone()
                if not exact:
                    raise RuntimeError(
                        f"Code/username collision for {employee_code}/{username}. "
                        "No changes were committed."
                    )
                demo_employees.append((exact[0], employee_code))
                reused_employees += 1
                continue

            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            employee_name = f"{first} {last} {index:03d}"
            department = DEPARTMENTS[(index - 1) % len(DEPARTMENTS)]

            cursor.execute(
                """
                INSERT INTO employees
                    (employee_code, employee_name, department,
                     username, password_hash, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    employee_code, employee_name, department,
                    username, password_hash, "employee",
                ),
            )
            demo_employees.append((cursor.lastrowid, employee_code))
            inserted_employees += 1

        today = date.today()
        end_date = today - timedelta(days=1)
        start_date = end_date - timedelta(days=90)
        dates = list(working_dates(start_date, end_date))

        for employee_id, employee_code in demo_employees:
            employee_rng = random.Random(f"{RANDOM_SEED}-{employee_code}")
            for attendance_day in dates:
                cursor.execute(
                    """
                    SELECT attendance_id FROM attendance
                    WHERE employee_id = %s AND attendance_date = %s
                    """,
                    (employee_id, attendance_day),
                )
                if cursor.fetchone():
                    skipped_attendance += 1
                    continue

                status = choose_attendance(employee_rng)
                check_in, check_out = make_times(status, employee_rng)

                cursor.execute(
                    """
                    INSERT INTO attendance
                        (employee_id, attendance_date, check_in, check_out, status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (employee_id, attendance_day, check_in, check_out, status),
                )
                inserted_attendance += 1

        connection.commit()
        print("\nDemo data seed completed successfully.")
        print(f"New employees inserted: {inserted_employees}")
        print(f"Existing demo employees reused: {reused_employees}")
        print(f"New attendance rows inserted: {inserted_attendance}")
        print(f"Existing attendance rows skipped: {skipped_attendance}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Demo username range: demoemp0001 to demoemp{EMPLOYEE_COUNT:04d}")
        print(f"Demo password for generated accounts: {DEMO_PASSWORD}")
        print("Existing manager account was not modified.")

    except Exception as error:
        connection.rollback()
        print("\nSeed failed. Database changes from this run were rolled back.")
        print("Error:", error)
        print("Check database.py and the employees/attendance table columns.")
    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    main()
