
def calculate_attendance(records):
    report = {}

    for record in records:
        employee_id = record["employee_id"]
        name = record["employee_name"]

        if employee_id not in report:
            report[employee_id] = {
                "employee_name": name,
                "present": 0,
                "absent": 0,
                "leave": 0,
                "holiday": 0
            }

        status = record["status"]

        if status == "Present":
            report[employee_id]["present"] += 1
        elif status == "Absent":
            report[employee_id]["absent"] += 1
        elif status == "Leave":
            report[employee_id]["leave"] += 1
        elif status == "Holiday":
            report[employee_id]["holiday"] += 1

    for employee in report.values():
        eligible_days = employee["present"] + employee["absent"]

        if eligible_days > 0:
            employee["percentage"] = round(
                employee["present"] / eligible_days * 100, 2
            )
        else:
            employee["percentage"] = 0.0

    return report
