"""COE SYNC 2026 - Template Page View Routes

Handles frontend routing for:
- GET /: Executive Dashboard (Hero, 4 KPI cards, Conflict Radar)
- GET /manage: Master Data Management (Rooms, Faculty, Sections, Subjects)
- GET /schedules: Interactive Weekly Timetable Grid
"""

from flask import Blueprint, render_template, session, redirect, url_for, current_app, request
from models import db, User, Room, Faculty, Section, Subject, Schedule, AuditLog
from routes.auth import login_required, require_roles, get_effective_role, get_effective_program

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
    """Render Executive Dashboard. Students and Faculty are strictly redirected to Schedules view."""
    from routes.auth import normalize_role
    norm_role = normalize_role(get_effective_role())
    if norm_role in ["STUDENT", "FACULTY"]:
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
    """Render Master Data CRUD Management console."""
    tab = request.args.get("tab")
    effective_role = get_effective_role()
    from routes.auth import normalize_role
    norm_role = normalize_role(effective_role)
    if norm_role == "STUDENT" and tab != "rooms":
        return redirect(url_for("views.schedules"))
    if norm_role == "DEAN" and tab == "subjects":
        return redirect(url_for("views.manage", tab="faculty"))

    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    effective_program = session.get("active_program") or (user.program if user else None)

    return render_template(
        "manage.html",
        active_page="manage",
        active_role=effective_role,
        effective_program=effective_program,
        current_username=session.get("username") or "chair_cpe",
        must_change_credentials=session.get("must_change_credentials", False),
    )


@views_bp.route("/settings")
@login_required
def settings():
    """Render NEXUS Settings console."""
    return render_template(
        "settings.html",
        active_page="settings",
        active_role=get_effective_role(),
        current_username=session.get("username") or "admin",
        must_change_credentials=session.get("must_change_credentials", False),
    )


@views_bp.route("/rooms")
@login_required
def rooms():
    return redirect("/manage?tab=rooms")


@views_bp.route("/faculty")
@login_required
def faculty():
    return redirect("/manage?tab=faculty")


@views_bp.route("/sections")
@login_required
def sections():
    return redirect("/manage?tab=sections")


@views_bp.route("/subjects")
@login_required
def subjects():
    return redirect("/manage?tab=subjects")


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
        effective_program=get_effective_program(),
        current_username=session.get("username") or "chair_cpe",
        must_change_credentials=session.get("must_change_credentials", False),
    )


@views_bp.route("/reports")
@login_required
def reports():
    from routes.auth import normalize_role
    effective_role = get_effective_role()
    if normalize_role(effective_role) in ("STUDENT", "FACULTY"):
        return redirect(url_for("views.schedules"))

    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    effective_program = get_effective_program()

    return render_template(
        "reports.html",
        active_page="reports",
        active_role=effective_role,
        effective_program=effective_program,
        current_username=session.get("username") or (user.username if user else "chair_cpe"),
        must_change_credentials=session.get("must_change_credentials", False),
    )


@views_bp.route("/settings")
@login_required
def settings_page():
    """Render NEXUS Settings & Governance Workspace."""
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    effective_role = get_effective_role()
    effective_program = session.get("active_program") or (user.program if user else "MEE")

    return render_template(
        "settings.html",
        active_page="settings",
        active_role=effective_role,
        user=user,
        effective_program=effective_program,
        current_username=session.get("username") or (user.username if user else "user"),
        must_change_credentials=session.get("must_change_credentials", False),
    )




