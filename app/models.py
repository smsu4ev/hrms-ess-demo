"""Database models for the HRMS + ESS portal (v2)."""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    # Username of the ESS is the Employee ID
    id = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(80))
    designation = db.Column(db.String(80))
    reporting_manager = db.Column(db.String(20), db.ForeignKey("users.id"))
    joining_date = db.Column(db.Date)
    employment_status = db.Column(db.String(20), default="active", nullable=False)
    # active | probation | resigned | terminated | retired
    nationality = db.Column(db.String(60))
    visa_expiry_date = db.Column(db.Date)
    passport_expiry_date = db.Column(db.Date)
    emirates_id_expiry_date = db.Column(db.Date)  # v2.1 UAE compliance
    email = db.Column(db.String(120))
    mobile = db.Column(db.String(30))
    iban = db.Column(db.String(60))      # v2.1 WPS payroll export
    bank_name = db.Column(db.String(80))  # v2.1 WPS payroll export
    basic_salary = db.Column(db.Float, default=0.0)
    monthly_salary = db.Column(db.Float, default=0.0)
    password_hash = db.Column(db.String(255), nullable=False)
    must_change_password = db.Column(db.Boolean, default=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    role = db.Column(db.String(20), default="employee", nullable=False)  # employee|manager|admin
    failed_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_manager(self):
        return self.role in ("manager", "admin")

    @property
    def is_admin(self):
        return self.role == "admin"


class LeaveBalance(db.Model):
    __tablename__ = "leave_balances"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey("users.id"), nullable=False, index=True)
    leave_type = db.Column(db.String(20), nullable=False)
    entitled = db.Column(db.Float, default=0.0, nullable=False)
    used = db.Column(db.Float, default=0.0, nullable=False)
    __table_args__ = (db.UniqueConstraint("user_id", "leave_type"),)


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey("users.id"), nullable=False, index=True)
    leave_type = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending|approved|rejected|cancelled
    approver_id = db.Column(db.String(20), db.ForeignKey("users.id"))
    approver_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime)


class AttendanceRecord(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    check_in = db.Column(db.String(5))   # HH:MM
    check_out = db.Column(db.String(5))  # HH:MM
    status = db.Column(db.String(20), default="present")  # present|absent|late|leave|holiday|weekoff
    __table_args__ = (db.UniqueConstraint("user_id", "date"),)


class RegularisationRequest(db.Model):
    """Employee request to correct attendance in/out times (ESS + manager approval)."""
    __tablename__ = "regularisation_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    corrected_in = db.Column(db.String(5))
    corrected_out = db.Column(db.String(5))
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)  # pending|approved|rejected
    approver_id = db.Column(db.String(20), db.ForeignKey("users.id"))
    approver_comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime)


class Grievance(db.Model):
    __tablename__ = "grievances"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey("users.id"), nullable=False, index=True)
    category = db.Column(db.String(60), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(20), default="submitted", nullable=False)  # submitted|under_review|in_progress|resolved|closed
    resolution = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Evaluation(db.Model):
    __tablename__ = "evaluations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(20), db.ForeignKey("users.id"), nullable=False, index=True)
    period = db.Column(db.String(40), nullable=False)  # e.g. "2026 H2"
    evaluator_id = db.Column(db.String(20), db.ForeignKey("users.id"), nullable=False)
    scores_json = db.Column(db.Text, nullable=False)  # JSON: [{criterion, rating, comment}, ...]
    overall = db.Column(db.Float)
    remarks = db.Column(db.Text)
    acknowledged = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Candidate(db.Model):
    """Recruitment tracker: a candidate in the hiring pipeline."""
    __tablename__ = "candidates"
    STAGES = ["Applied", "Screening", "Interview", "Offer", "Joined", "Rejected"]
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30))
    email = db.Column(db.String(120))
    source = db.Column(db.String(80))
    stage = db.Column(db.String(20), default="Applied", nullable=False)
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(20), db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class OnboardingCase(db.Model):
    """Onboarding checklist case for a new joiner."""
    __tablename__ = "onboarding_cases"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    joining_date = db.Column(db.Date)
    employee_id = db.Column(db.String(20))  # linked employee once created
    notes = db.Column(db.Text)
    created_by = db.Column(db.String(20), db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def progress(self):
        items = list(self.tasks)
        if not items:
            return 0
        done = sum(1 for t in items if t.is_done)
        return round(done * 100 / len(items))


class OnboardingTask(db.Model):
    __tablename__ = "onboarding_tasks"
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey("onboarding_cases.id"), nullable=False, index=True)
    label = db.Column(db.String(200), nullable=False)
    is_done = db.Column(db.Boolean, default=False, nullable=False)
    done_at = db.Column(db.DateTime)
    case = db.relationship("OnboardingCase", backref=db.backref("tasks", lazy="dynamic",
                                                                order_by="OnboardingTask.id"))


ONBOARDING_CHECKLIST_ITEMS = [
    "Offer letter issued",
    "Employment contract signed",
    "Emirates ID copy collected",
    "Visa / work permit processed",
    "Bank account details collected",
    "IT / ERP access created",
    "Workstation / tools assigned",
    "HR induction completed",
]


class AuditLog(db.Model):
    """Advanced audit trail: every recorded action, with per-field old/new values."""
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.String(20))
    action = db.Column(db.String(80), nullable=False)
    detail = db.Column(db.Text)
    # v2 advanced fields
    entity = db.Column(db.String(40), index=True)       # e.g. "employee", "candidate", "leave"
    entity_id = db.Column(db.String(40), index=True)   # e.g. employee ID, candidate id
    field_name = db.Column(db.String(60))              # changed field, for per-field entries
    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    ip = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
