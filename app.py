import os
from functools import wraps
from datetime import date, datetime, time, timedelta

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_connection
from reports import calculate_attendance

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates")
)
app.secret_key = "change-this-to-a-random-secret"


def login_required(role=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if "employee_id" not in session:
                return redirect(url_for("login"))

            if role and session.get("role") != role:
                return "Access Denied: You are not authorized.", 403

            return func(*args, **kwargs)

        return wrapper

    return decorator


@app.route("/")
@login_required("manager")
def home():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM employees ORDER BY employee_id")
        employees = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return render_template("index.html", employees=employees)


@app.route("/attendance")
@login_required("manager")
def attendance():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM employees ORDER BY employee_name")
        employees = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return render_template("attendence.html", employees=employees)


@app.route("/add_employee", methods=["POST"])
@login_required("manager")
def add_employee():
    employee_code = request.form["employee_code"].strip()
    employee_name = request.form["employee_name"].strip()
    department = request.form["department"].strip()
    username = request.form["username"].strip()
    password = request.form["password"]

    if not all([
        employee_code, employee_name, department, username, password
    ]):
        return "All fields are required!", 400

    if len(password) < 8:
        return "Password must contain at least 8 characters.", 400

    password_hash = generate_password_hash(password)

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO employees
            (
                employee_code, employee_name, department,
                username, password_hash, role
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                employee_code, employee_name, department,
                username, password_hash, "employee"
            )
        )

        connection.commit()

        return """
                <h2>Employee account created successfully!</h2>
                <a href="/">Back to Home</a>
            """

    except Exception as error:
        if connection:
            connection.rollback()

        print("Employee registration error:", error)

        return """
                <h2>Could not create employee account.</h2>
                <p>Employee code or username may already exist.</p>
                <a href="/">Back to Home</a>
            """, 400

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/mark_attendance", methods=["POST"])
@login_required("manager")
def mark_attendance():
    employee_id = request.form["employee_id"]
    attendance_date = request.form["attendance_date"]
    status = request.form["status"]

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO attendance
            (employee_id, attendance_date, status)
            VALUES (%s, %s, %s)
            """,
            (employee_id, attendance_date, status)
        )

        connection.commit()

        return """
                <h2>Attendance marked successfully!</h2>
                <a href="/attendance">Mark More Attendance</a><br>
                <a href="/">Back to Employees</a>
            """

    except Exception as error:
        if connection:
            connection.rollback()

        print("Attendance error:", error)

        return """
                <h2>Could not mark attendance.</h2>
                <p>Attendance for this employee and date may already exist.</p>
                <a href="/attendance">Try Again</a>
            """, 400

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/attendance_records")
@login_required("manager")
def attendance_records():
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                e.employee_code,
                e.employee_name,
                e.department,
                a.attendance_date,
                a.check_in,
                a.check_out,
                a.status
            FROM attendance a
            JOIN employees e ON a.employee_id = e.employee_id
            ORDER BY a.attendance_date DESC, e.employee_name
            """
        )
        records = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    return render_template("attendance_records.html", records=records)


@app.route("/attendance_report")
@login_required("manager")
def attendance_report():
    selected_month = request.args.get("month", datetime.now().strftime("%Y-%m"))

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT
                e.employee_id,
                e.employee_name,
                e.department,
                a.status,
                a.attendance_date
            FROM employees e
            LEFT JOIN attendance a
                ON e.employee_id = a.employee_id
                AND DATE_FORMAT(a.attendance_date, '%Y-%m') = %s
            ORDER BY e.department, e.employee_name
            """,
            (selected_month,)
        )
        records = cursor.fetchall()
    finally:
        cursor.close()
        connection.close()

    report = {}

    for record in records:
        employee_id = record["employee_id"]

        if employee_id not in report:
            report[employee_id] = {
                "employee_name": record["employee_name"],
                "department": record["department"],
                "present": 0,
                "absent": 0,
                "leave": 0,
                "holiday": 0,
                "late": 0,
                "incomplete": 0,
                "percentage": 0.0
            }

        status = record["status"]

        if status:
            key = status.lower()
            if key in report[employee_id]:
                report[employee_id][key] += 1

    departments = {}

    for employee in report.values():
        eligible_days = employee["present"] + employee["absent"]

        employee["percentage"] = (
            round(employee["present"] / eligible_days * 100, 2)
            if eligible_days else 0.0
        )

        department = employee["department"]

        if department not in departments:
            departments[department] = {
                "present": 0,
                "absent": 0,
                "leave": 0,
                "holiday": 0,
                "employees": 0
            }

        departments[department]["employees"] += 1

        for status in ["present", "absent", "leave", "holiday"]:
            departments[department][status] += employee[status]

    return render_template(
        "attendance_report.html",
        report=report.values(),
        departments=departments,
        selected_month=selected_month
    )
@app.route("/employee_dashboard")
@login_required("employee")
def employee_dashboard():
    employee_id = session["employee_id"]
    today = date.today()

    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(
            """
            SELECT employee_name
            FROM employees
            WHERE employee_id = %s
            """,
            (employee_id,)
        )
        employee = cursor.fetchone()

        cursor.execute(
            """
            SELECT check_in, check_out, status
            FROM attendance
            WHERE employee_id = %s AND attendance_date = %s
            """,
            (employee_id, today)
        )
        record = cursor.fetchone()

    finally:
        cursor.close()
        connection.close()

    if not employee:
        session.clear()
        return redirect(url_for("login"))

    check_in = record["check_in"] if record else None
    check_out = record["check_out"] if record else None
    status = record["status"] if record else None
    working_hours = None

    if isinstance(check_in, timedelta):
        check_in = (datetime.min + check_in).time()
    if isinstance(check_out, timedelta):
        check_out = (datetime.min + check_out).time()

    if check_in and check_out:
        start = datetime.combine(today, check_in)
        end = datetime.combine(today, check_out)
        seconds = int((end - start).total_seconds())

        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        working_hours = f"{hours} hours {minutes} minutes"

    return render_template(
        "employee_dashboard.html",
        employee_name=employee["employee_name"],
        attendance_date=today,
        check_in=check_in,
        check_out=check_out,
        working_hours=working_hours,
        status=status
    )


@app.route("/check_in", methods=["POST"])
@login_required("employee")
def check_in():
    employee_id = session["employee_id"]
    now = datetime.now()
    today = now.date()
    current_time = now.time().replace(microsecond=0)

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT attendance_id, check_in, check_out
            FROM attendance
            WHERE employee_id = %s AND attendance_date = %s
            """,
            (employee_id, today)
        )
        record = cursor.fetchone()

        status = "Present" if current_time <= time(9, 15) else "Late"

        if record:
            if record[1] is not None:
                flash("You have already checked in today.")
            else:
                cursor.execute(
                    """
                    UPDATE attendance
                    SET check_in = %s, status = %s
                    WHERE attendance_id = %s
                    """,
                    (current_time, status, record[0])
                )
                connection.commit()
                flash("Check-in recorded successfully.")
        else:
            cursor.execute(
                """
                INSERT INTO attendance
                (employee_id, attendance_date, check_in, status)
                VALUES (%s, %s, %s, %s)
                """,
                (employee_id, today, current_time, status)
            )
            connection.commit()
            flash("Check-in recorded successfully.")

    except Exception as error:
        connection.rollback()
        print("Check-in error:", repr(error))
        flash(f"Check-in error: {error}")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("employee_dashboard"))


@app.route("/check_out", methods=["POST"])
@login_required("employee")
def check_out():
    employee_id = session["employee_id"]
    now = datetime.now()
    today = now.date()
    current_time = now.time().replace(microsecond=0)

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT attendance_id, check_in, check_out
            FROM attendance
            WHERE employee_id = %s AND attendance_date = %s
            """,
            (employee_id, today)
        )
        record = cursor.fetchone()

        if not record or record[1] is None:
            flash("Please check in before checking out.")

        elif record[2] is not None:
            flash("You have already checked out today.")

        else:
            check_in_value = record[1]

            if isinstance(check_in_value, timedelta):
                check_in_value = (
                        datetime.min + check_in_value
                ).time()

            start = datetime.combine(today, check_in_value)
            end = datetime.combine(today, current_time)
            seconds = (end - start).total_seconds()

            if seconds < 0:
                flash("Check-out time cannot be earlier than check-in.")
            else:
                status = "Present" if seconds >= 8 * 3600 else "Incomplete"

                cursor.execute(
                    """
                    UPDATE attendance
                    SET check_out = %s, status = %s
                    WHERE attendance_id = %s
                    """,
                    (current_time, status, record[0])
                )
                connection.commit()
                flash("Check-out recorded successfully.")

    except Exception as error:

        connection.rollback()
        print("Check-out error:", repr(error))
        flash(f"Check-out error: {error}")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("employee_dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        connection = None
        cursor = None
        user = None

        try:
            connection = get_connection()
            cursor = connection.cursor(dictionary=True)

            cursor.execute(
                """
                SELECT employee_id, username, password_hash, role
                FROM employees
                WHERE username = %s
                """,
                (username,)
            )
            user = cursor.fetchone()

        except Exception as error:
            print("Login database error:", error)
            flash("Unable to log in right now. Please try again.")

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

        if user and user["password_hash"] and check_password_hash(
                user["password_hash"], password
        ):
            session.clear()
            session["employee_id"] = user["employee_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "manager":
                return redirect(url_for("home"))

            return redirect(url_for("employee_dashboard"))

        if user is None:
            flash("Invalid username or password.")
        elif user and not user["password_hash"]:
            flash("This account does not have login credentials yet.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/delete_employee/<int:employee_id>", methods=["POST"])
@login_required("manager")
def delete_employee(employee_id):
    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(
            "SELECT role FROM employees WHERE employee_id = %s",
            (employee_id,)
        )
        employee = cursor.fetchone()

        if not employee:
            flash("Employee not found.", "error")
            return redirect(url_for("home"))

        if employee[0] == "manager":
            flash("Manager accounts cannot be deleted here.", "error")
            return redirect(url_for("home"))

        cursor.execute(
            "DELETE FROM attendance WHERE employee_id = %s",
            (employee_id,)
        )
        cursor.execute(
            "DELETE FROM employees WHERE employee_id = %s",
            (employee_id,)
        )

        connection.commit()
        flash("Employee deleted successfully.", "success")

    except Exception as error:
        connection.rollback()
        flash(f"Delete failed: {error}", "error")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("home"))

if __name__ == "__main__":
    print(app.url_map)
    app.run(debug=True)
