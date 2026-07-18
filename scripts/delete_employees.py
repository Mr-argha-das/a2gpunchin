import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import connect_database
from app.models import Attendance, Employee, Leave, User


def main():
    connect_database()
    employee_emails = [employee.email for employee in Employee.objects() if employee.email]
    attendance_count = Attendance.objects.count()
    leave_count = Leave.objects.count()
    employee_count = Employee.objects.count()
    employee_user_count = User.objects(email__in=employee_emails, is_super_admin=False).count() if employee_emails else 0

    Attendance.objects.delete()
    Leave.objects.delete()
    Employee.objects.delete()
    if employee_emails:
        User.objects(email__in=employee_emails, is_super_admin=False).delete()

    print(f"Deleted employees: {employee_count}")
    print(f"Deleted attendance records: {attendance_count}")
    print(f"Deleted leave records: {leave_count}")
    print(f"Deleted employee login users: {employee_user_count}")
    print(f"Remaining users: {User.objects.count()}")


if __name__ == "__main__":
    main()
