"""COE SYNC 2026 - Template Page View Routes

Handles frontend routing for:
- GET /: Executive Dashboard (Hero, 4 KPI cards, Conflict Radar)
- GET /manage: Master Data Management (Rooms, Faculty, Sections, Subjects)
- GET /schedules: Interactive Weekly Timetable Grid
"""

from flask import Blueprint, render_template, session, redirect, url_for, current_app
from models import Room, Faculty, Section, Subject, Schedule, AuditLog
from routes.auth import login_required, require_roles, get_effective_role

views_bp = Blueprint("views", __name__)


@views_bp.route("/login")
def login_page():
    """Fallback alias for Login Gateway."""
    if session.get("user_id"):
        return redirect(url_for("views.dashboard"))
    show_demo = current_app.config.get("SHOW_DEMO_CREDENTIALS", True)
    return render_template("login.html", show_demo_credentials=show_demo)


@views_bp.route("/logout")
def logout():
    """Logout action redirecting to login gateway."""
    session.clear()
    try:
        return redirect(url_for("auth_views.login_page"))
    except Exception:
        return redirect("/login")


@views_bp.route("/")
@views_bp.route("/dashboard")
@login_required
def dashboard():
    """Render Executive Dashboard. Students are strictly redirected to Schedules view."""
    if get_effective_role() == "STUDENT":
        return redirect(url_for("views.schedules"))

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        active_role=get_effective_role(),
        current_username=session.get("username") or "chair_cpe",
        must_change_credentials=session.get("must_change_credentials", False),
    )


@views_bp.route("/manage")
@login_required
def manage():
    """Render Master Data CRUD Management console. Inaccessible to students."""
    if get_effective_role() == "STUDENT":
        return redirect(url_for("views.schedules"))

    return render_template(
        "manage.html",
        active_page="manage",
        active_role=get_effective_role(),
        current_username=session.get("username") or "chair_cpe",
        must_change_credentials=session.get("must_change_credentials", False),
    )


@views_bp.route("/schedules")
@login_required
def schedules():
    """Render Weekly Timetable Schedules view (sole primary landing view for Students)."""
    return render_template(
        "schedules.html",
        active_page="schedules",
        active_role=get_effective_role(),
        current_username=session.get("username") or "chair_cpe",
        must_change_credentials=session.get("must_change_credentials", False),
    )


@views_bp.route("/schedules/create")
@login_required
@require_roles("CHAIR", "ADMIN")
def create_schedule():
    """Render Create Schedule view (Manual and Smart Generate modes)."""
    return render_template(
        "create_schedule.html",
        active_page="create_schedule",
        active_role=get_effective_role(),
        current_username=session.get("username") or "chair_cpe",
        must_change_credentials=session.get("must_change_credentials", False),
    )


@views_bp.route("/reports")
@login_required
def reports():
    """Render Institutional Analytics & Workload Reports view. Inaccessible to students."""
    if get_effective_role() == "STUDENT":
        return redirect(url_for("views.schedules"))

    return render_template(
        "reports.html",
        active_page="reports",
        active_role=get_effective_role(),
        current_username=session.get("username") or "chair_cpe",
        must_change_credentials=session.get("must_change_credentials", False),
    )




