"""Seed DEMO data for free sample testing — FAKE employees only.

Usage (on the sample host, after installing requirements):
    python seed_demo.py

Creates 5 demo users so a reviewer can test every role immediately:
    HRADMIN   / Demo@123  (HR Admin)
    MGR001    / Demo@123  (Manager)
    EMP001    / Demo@123  (Employee)
    EMP002    / Demo@123  (Employee, visa expiring soon — tests the alert)
    EMP003    / Demo@123  (Employee)

WARNING: Demo seed only. Never run this on a production database and
never use these passwords with real employee data.
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app, db  # noqa: E402
from app.models import User, LeaveBalance  # noqa: E402
import config as app_config  # noqa: E402

DEMO_PASSWORD = "Demo@123"

DEMO_USERS = [
    # id, name, department, designation, role, reporting_manager, visa_days
    ("HRADMIN", "Demo HR Admin", "Human Resources", "HR Manager", "admin", None, 300),
    ("MGR001", "Demo Manager", "Production", "Production Manager", "manager", "HRADMIN", 300),
    ("EMP001", "Demo Employee One", "Production", "Welder", "employee", "MGR001", 300),
    ("EMP002", "Demo Employee Two", "Production", "Metal Grinder", "employee", "MGR001", 10),
    ("EMP003", "Demo Employee Three", "Sales", "Sales Executive", "employee", "MGR001", 300),
]


def main():
    app = create_app()
    with app.app_context():
        created = 0
        for uid, name, dept, desig, role, mgr, visa_days in DEMO_USERS:
            if User.query.get(uid):
                continue
            u = User(
                id=uid, name=name, department=dept, designation=desig,
                role=role, reporting_manager=mgr,
                joining_date=date.today() - timedelta(days=365),
                employment_status="active", nationality="Demo",
                visa_expiry_date=date.today() + timedelta(days=visa_days),
                passport_expiry_date=date.today() + timedelta(days=visa_days + 90),
                email="", mobile="",
            )
            u.set_password(DEMO_PASSWORD)
            u.must_change_password = False  # demo convenience only
            db.session.add(u)
            db.session.flush()
            for lt, cfg in app_config.LEAVE_TYPES.items():
                db.session.add(LeaveBalance(
                    user_id=uid, leave_type=lt,
                    entitled=cfg["entitled"], used=0.0))
            created += 1
        db.session.commit()
        print(f"Demo seed done: {created} demo user(s) created.")
        print("Login at / with HRADMIN / Demo@123 (admin), MGR001 (manager), EMP001 (employee).")


if __name__ == "__main__":
    main()
