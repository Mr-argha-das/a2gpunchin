import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import connect_database
from app.models import (
    Attendance,
    AuditLog,
    Branch,
    Department,
    Employee,
    Holiday,
    Leave,
    Notification,
    Shift,
    Subscription,
    SupportTicket,
    User,
)


KEEP_EMAILS = {"superadmin@example.com", "companyadmin@example.com"}


def is_company_admin(user: User) -> bool:
    return any(getattr(role, "slug", "") == "company-admin-demo" or getattr(role, "name", "") == "Company Admin" for role in user.roles)


def removable_users():
    users = []
    for user in User.objects():
        if user.email in KEEP_EMAILS or user.is_super_admin or is_company_admin(user):
            continue
        users.append(user)
    return users


def main():
    parser = argparse.ArgumentParser(description="Remove app data but keep admin/company-admin login users.")
    parser.add_argument("--apply", action="store_true", help="Actually delete records. Without this, only prints counts.")
    args = parser.parse_args()

    connect_database()
    model_groups = [
        ("attendance", Attendance.objects),
        ("employees", Employee.objects),
        ("branches", Branch.objects),
        ("departments", Department.objects),
        ("shifts", Shift.objects),
        ("leaves", Leave.objects),
        ("holidays", Holiday.objects),
        ("notifications", Notification.objects),
        ("audit_logs", AuditLog.objects),
        ("support_tickets", SupportTicket.objects),
        ("subscriptions", Subscription.objects),
    ]
    users_to_delete = removable_users()

    print("Will keep users:")
    for user in User.objects().order_by("email"):
        if user not in users_to_delete:
            print(f"  - {user.email}")

    print("\nRecords to delete:")
    for name, query in model_groups:
        print(f"  - {name}: {query.count()}")
    print(f"  - users_except_admins: {len(users_to_delete)}")

    if not args.apply:
        print("\nDry run only. Run with --apply to delete.")
        return

    for _, query in model_groups:
        query.delete()
    for user in users_to_delete:
        user.delete()

    print("\nCleanup complete.")
    print(f"Remaining users: {User.objects.count()}")


if __name__ == "__main__":
    main()
