"""HRMS blueprint (v2): Employee Central, Recruitment Tracker, Onboarding."""
from datetime import date, datetime, timedelta
import calendar as calmod

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from app import db
from app.models import (User, LeaveBalance, LeaveRequest, AttendanceRecord,
                        Candidate, OnboardingCase, OnboardingTask,
                        ONBOARDING_CHECKLIST_ITEMS)
from app.audit import record, audit_model_changes, snapshot
from app.views import manager_required  # noqa: F401

hrms_bp = Blueprint("hrms", __name__, url_prefix="/hrms")


def admin_required(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user.is_admin:
            abort(403)
        return fn(*a, **kw)
    return wrapper


EMPLOYEE_FIELDS = ["name", "department", "designation", "reporting_manager",
                   "joining_date", "employment_status", "nationality",
                   "visa_expiry_date", "passport_expiry_date",
                   "email", "mobile", "basic_salary", "monthly_salary"]

EMPLOYMENT_STATUSES = ["active", "probation", "resigned", "terminated", "retired"]


def parse_date(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def get_upcoming_expiries(days=30, limit=50):
    """Employees whose visa or passport expires within `days` (and not already expired long ago)."""
    today = date.today()
    cutoff = today + timedelta(days=days)
    out = []
    users = User.query.filter(User.is_active.is_(True)).all()
    for u in users:
        for doc, d in (("visa", u.visa_expiry_date), ("passport", u.passport_expiry_date)):
            if d and today - timedelta(days=30) <= d <= cutoff:
                out.append({"user": u, "doc": doc, "date": d,
                            "days_left": (d - today).days})
    out.sort(key=lambda r: r["days_left"])
    return out[:limit]


# ---------------- Employee Central ----------------
@hrms_bp.route("/employees")
@login_required
@admin_required
def employees():
    q = (request.args.get("q") or "").strip()
    dept = (request.args.get("dept") or "").strip()
    status = (request.args.get("status") or "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.id.ilike(like), User.name.ilike(like),
                                 User.designation.ilike(like)))
    if dept:
        query = query.filter_by(department=dept)
    if status:
        query = query.filter_by(employment_status=status)
    rows = query.order_by(User.name).limit(300).all()
    departments = sorted({u.department for u in User.query.all() if u.department})
    return render_template("hr_employees.html", rows=rows, q=q, dept=dept,
                           status=status, departments=departments,
                           statuses=EMPLOYMENT_STATUSES)


@hrms_bp.route("/employees/new", methods=["GET", "POST"])
@login_required
@admin_required
def employee_new():
    error = None
    if request.method == "POST":
        uid = (request.form.get("employee_id") or "").strip()
        name = (request.form.get("name") or "").strip()
        if not uid or not name:
            error = "Employee ID and name are required."
        elif User.query.get(uid):
            error = f"Employee ID {uid} already exists."
        else:
            user = User(id=uid, name=name,
                        department=(request.form.get("department") or "").strip() or None,
                        designation=(request.form.get("designation") or "").strip() or None,
                        reporting_manager=(request.form.get("reporting_manager") or "").strip() or None,
                        joining_date=parse_date(request.form.get("joining_date")),
                        employment_status=request.form.get("employment_status") or "active",
                        nationality=(request.form.get("nationality") or "").strip() or None,
                        visa_expiry_date=parse_date(request.form.get("visa_expiry_date")),
                        passport_expiry_date=parse_date(request.form.get("passport_expiry_date")),
                        email=(request.form.get("email") or "").strip() or None,
                        mobile=(request.form.get("mobile") or "").strip() or None,
                        basic_salary=float(request.form.get("basic_salary") or 0),
                        monthly_salary=float(request.form.get("monthly_salary") or 0))
            # Initial password must be set by HR separately (never a guessable default).
            temp_pw = "Change" + datetime.utcnow().strftime("%H%M%S") + "1A!"
            user.set_password(temp_pw)
            user.must_change_password = True
            db.session.add(user)
            record("employee_created", f"Employee {uid} ({name}) created",
                   entity="employee", entity_id=uid)
            for f in EMPLOYEE_FIELDS:
                record("employee_created", f"{f} set to '{getattr(user, f)}'",
                       entity="employee", entity_id=uid, field_name=f,
                       old_value="", new_value=getattr(user, f))
            db.session.commit()
            flash(f"Employee {uid} created. Temporary password: {temp_pw} "
                  "- share it securely; the employee must change it on login.", "success")
            return redirect(url_for("hrms.employee_detail", uid=uid))
    managers = User.query.filter(User.role.in_(("manager", "admin")),
                                 User.is_active.is_(True)).order_by(User.name).all()
    return render_template("hr_employee_form.html", user=None, error=error,
                           statuses=EMPLOYMENT_STATUSES, managers=managers)


@hrms_bp.route("/employees/<uid>")
@login_required
@admin_required
def employee_detail(uid):
    user = User.query.get_or_404(uid)
    balances = LeaveBalance.query.filter_by(user_id=uid).all()
    leaves = LeaveRequest.query.filter_by(user_id=uid)\
        .order_by(LeaveRequest.created_at.desc()).limit(10).all()
    month_start = date.today().replace(day=1)
    att = AttendanceRecord.query.filter(
        AttendanceRecord.user_id == uid,
        AttendanceRecord.date >= month_start).all()
    present = sum(1 for r in att if r.status in ("present", "late"))
    from app.models import AuditLog
    logs = AuditLog.query.filter_by(entity="employee", entity_id=uid)\
        .order_by(AuditLog.created_at.desc()).limit(30).all()
    manager = User.query.get(user.reporting_manager) if user.reporting_manager else None
    return render_template("hr_employee_detail.html", user=user, balances=balances,
                           leaves=leaves, present_days=present, logs=logs, manager=manager)


@hrms_bp.route("/employees/<uid>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def employee_edit(uid):
    user = User.query.get_or_404(uid)
    error = None
    if request.method == "POST":
        before = snapshot(user, EMPLOYEE_FIELDS)
        user.name = (request.form.get("name") or "").strip() or user.name
        user.department = (request.form.get("department") or "").strip() or None
        user.designation = (request.form.get("designation") or "").strip() or None
        user.reporting_manager = (request.form.get("reporting_manager") or "").strip() or None
        user.joining_date = parse_date(request.form.get("joining_date"))
        status = request.form.get("employment_status") or "active"
        user.employment_status = status if status in EMPLOYMENT_STATUSES else "active"
        user.is_active = status in ("active", "probation")
        user.nationality = (request.form.get("nationality") or "").strip() or None
        user.visa_expiry_date = parse_date(request.form.get("visa_expiry_date"))
        user.passport_expiry_date = parse_date(request.form.get("passport_expiry_date"))
        user.email = (request.form.get("email") or "").strip() or None
        user.mobile = (request.form.get("mobile") or "").strip() or None
        try:
            user.basic_salary = float(request.form.get("basic_salary") or 0)
            user.monthly_salary = float(request.form.get("monthly_salary") or 0)
        except ValueError:
            error = "Salary must be a number."
        if not error:
            audit_model_changes(user, before, EMPLOYEE_FIELDS, entity="employee")
            db.session.commit()
            flash("Employee record updated.", "success")
            return redirect(url_for("hrms.employee_detail", uid=uid))
    managers = User.query.filter(User.role.in_(("manager", "admin")),
                                 User.is_active.is_(True)).order_by(User.name).all()
    return render_template("hr_employee_form.html", user=user, error=error,
                           statuses=EMPLOYMENT_STATUSES, managers=managers)


# ---------------- Recruitment Tracker ----------------
@hrms_bp.route("/recruitment", methods=["GET", "POST"])
@login_required
@admin_required
def recruitment():
    stage = (request.args.get("stage") or "").strip()
    q = Candidate.query
    if stage:
        q = q.filter_by(stage=stage)
    rows = q.order_by(Candidate.created_at.desc()).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        position = (request.form.get("position") or "").strip()
        if not name or not position:
            flash("Candidate name and position are required.", "error")
        else:
            c = Candidate(name=name, position=position,
                          phone=(request.form.get("phone") or "").strip() or None,
                          email=(request.form.get("email") or "").strip() or None,
                          source=(request.form.get("source") or "").strip() or None,
                          stage="Applied",
                          notes=(request.form.get("notes") or "").strip() or None,
                          created_by=current_user.id)
            db.session.add(c)
            db.session.flush()
            record("candidate_created", f"Candidate {c.id}: {name} for {position}",
                   entity="candidate", entity_id=c.id)
            db.session.commit()
            flash(f"Candidate {name} added.", "success")
            return redirect(url_for("hrms.recruitment"))
    return render_template("hr_recruitment.html", rows=rows, stage=stage,
                           stages=Candidate.STAGES)


@hrms_bp.route("/recruitment/<int:cid>", methods=["GET", "POST"])
@login_required
@admin_required
def candidate_detail(cid):
    c = Candidate.query.get_or_404(cid)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "stage":
            new_stage = request.form.get("stage", "")
            if new_stage in Candidate.STAGES and new_stage != c.stage:
                old = c.stage
                c.stage = new_stage
                record("candidate_stage", f"#{c.id} stage {old} -> {new_stage}",
                       entity="candidate", entity_id=c.id, field_name="stage",
                       old_value=old, new_value=new_stage)
                db.session.commit()
                flash(f"Stage moved to {new_stage}.", "success")
        elif action == "notes":
            c.notes = (request.form.get("notes") or "").strip() or None
            record("candidate_notes", f"#{c.id} notes updated",
                   entity="candidate", entity_id=c.id)
            db.session.commit()
            flash("Notes saved.", "success")
        return redirect(url_for("hrms.candidate_detail", cid=cid))
    from app.models import AuditLog
    logs = AuditLog.query.filter_by(entity="candidate", entity_id=str(cid))\
        .order_by(AuditLog.created_at.desc()).limit(30).all()
    return render_template("hr_candidate_detail.html", c=c, stages=Candidate.STAGES, logs=logs)


# ---------------- Onboarding Checklist ----------------
@hrms_bp.route("/onboarding", methods=["GET", "POST"])
@login_required
@admin_required
def onboarding():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Joiner name is required.", "error")
        else:
            case = OnboardingCase(name=name,
                                  joining_date=parse_date(request.form.get("joining_date")),
                                  employee_id=(request.form.get("employee_id") or "").strip() or None,
                                  notes=(request.form.get("notes") or "").strip() or None,
                                  created_by=current_user.id)
            db.session.add(case)
            db.session.flush()
            for label in ONBOARDING_CHECKLIST_ITEMS:
                db.session.add(OnboardingTask(case_id=case.id, label=label))
            record("onboarding_case_created", f"#{case.id}: {name}",
                   entity="onboarding", entity_id=case.id)
            db.session.commit()
            flash(f"Onboarding case for {name} created.", "success")
            return redirect(url_for("hrms.onboarding_case", oid=case.id))
    cases = OnboardingCase.query.order_by(OnboardingCase.created_at.desc()).all()
    return render_template("hr_onboarding.html", cases=cases)


@hrms_bp.route("/onboarding/<int:oid>", methods=["GET", "POST"])
@login_required
@admin_required
def onboarding_case(oid):
    case = OnboardingCase.query.get_or_404(oid)
    if request.method == "POST":
        tid = request.form.get("task_id")
        t = OnboardingTask.query.get_or_404(int(tid))
        if t.case_id != case.id:
            abort(403)
        t.is_done = not t.is_done
        t.done_at = datetime.utcnow() if t.is_done else None
        record("onboarding_task",
               f"#{case.id} '{t.label}' marked {'done' if t.is_done else 'pending'}",
               entity="onboarding", entity_id=case.id, field_name=t.label,
               old_value="pending" if t.is_done else "done",
               new_value="done" if t.is_done else "pending")
        db.session.commit()
        flash(f"'{t.label}' marked {'done' if t.is_done else 'pending'}.", "success")
        return redirect(url_for("hrms.onboarding_case", oid=oid))
    return render_template("hr_onboarding_case.html", case=case)
