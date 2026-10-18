"""Al-Ameen Industries LLC - Employee Self-Service (ESS) Portal."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG = {
    # !!! MUST be overridden in production via environment variable !!!
    "SECRET_KEY": os.environ.get("ESS_SECRET_KEY", "dev-only-change-me-immediately"),
    "SQLALCHEMY_DATABASE_URI": os.environ.get(
        "ESS_DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "ess.db")
    ),
    "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    # Secure cookie flags - SESSION_COOKIE_SECURE requires HTTPS in production.
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SAMESITE": "Lax",
    "SESSION_COOKIE_SECURE": os.environ.get("ESS_COOKIE_SECURE", "0") == "1",
    "REMEMBER_COOKIE_HTTPONLY": True,
    "REMEMBER_COOKIE_DURATION": 28800,  # 8 hours
    "PERMANENT_SESSION_LIFETIME": 28800,
    # Password policy
    "PASSWORD_MIN_LENGTH": 8,
    # Account lockout
    "MAX_FAILED_ATTEMPTS": 5,
    "LOCKOUT_MINUTES": 15,
}

COMPANY_NAME = "Al-Ameen Industries LLC"
TRADE_NAME = "800 Retail - Retail Solutions"

LEAVE_TYPES = {
    "annual": {"label": "Annual Leave", "entitled": 30},
    "sick": {"label": "Sick Leave", "entitled": 15},
    "emergency": {"label": "Emergency Leave", "entitled": 5},
    "unpaid": {"label": "Unpaid Leave", "entitled": 0},
}

GRIEVANCE_CATEGORIES = [
    "Workplace Conduct",
    "Salary & Benefits",
    "Working Hours & Leave",
    "Health & Safety",
    "Harassment / Discrimination",
    "Facilities & Accommodation",
    "Other",
]

EVAL_CRITERIA = [
    "Job Knowledge & Skills",
    "Quality of Work",
    "Productivity & Efficiency",
    "Teamwork & Collaboration",
    "Attendance & Punctuality",
    "Communication Skills",
    "Initiative & Problem Solving",
    "Safety & Policy Compliance",
]

EVAL_COMMENT_OPTIONS = [
    "Exceeds Expectations",
    "Meets Expectations",
    "Needs Improvement",
    "Unsatisfactory",
    "Not Applicable",
]
