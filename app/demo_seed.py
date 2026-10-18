"""Demo users for FREE SAMPLE deployments only (fake data).

Active only when the environment variable ESS_SEED_DEMO=1 is set (the
Render free sample sets it in render.yaml). On app startup, if the demo
admin does not exist yet, the 5 fake demo users are created. This makes
the sample testable on hosts without shell access (e.g. Render free,
where the filesystem is ephemeral and Shell needs a paid plan).

NEVER enable ESS_SEED_DEMO on a production deployment or with real data.
"""
from datetime import date, timedelta

DEMO_PASSWORD = "Demo@123"

DEMO_USERS = [
    # id, name, department, designation, role, reporting_manager, visa_days
    ("HRADMIN", "Demo HR Admin", "Human Resources", "HR Manager", "admin", None, 300),
    ("MGR001", "Demo Manager", "Production", "Production Manager", "manager", "HRADMIN", 300),
    ("EMP001", "Demo Employee One", "Production", "Welder", "employee", "MGR001", 300),
    ("EMP002", "Demo Employee Two", "Production", "Metal Grinder", "employee", "MGR001", 10),
    ("EMP003", "Demo Employee Three", "Sales", "Sales Executive", "employee", "MGR001", 300),
]


def ensure_demo_users():
    """Create the demo users if missing. Safe to call on every startup."""
    from app import db
    from app.models import User, LeaveBalance
    import config as app_config

    if db.session.get(User, "HRADMIN") is not None:
        return 0
    created = 0
    for uid, name, dept, desig, role, mgr, visa_days in DEMO_USERS:
        if db.session.get(User, uid) is not None:
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
                user_id=uid, leave_type=lt, entitled=cfg["entitled"], used=0.0))
        created += 1
    db.session.commit()
    return created
