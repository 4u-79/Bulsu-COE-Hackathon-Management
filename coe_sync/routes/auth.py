"""COE SYNC 2026 - Authentication, RBAC & Role Impersonator Routes

Endpoints:
- POST /api/auth/login: Authenticate credentials and initialize session
- POST /api/auth/logout: Terminate current session
- POST /api/auth/impersonate: Swap active viewing role for live demonstration
- GET /api/auth/me: Retrieve active user and session profile
"""

from functools import wraps
from flask import (
    Blueprint,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    render_template,
    current_app,
)
from models import db, User, Faculty, Section, AuditLog

auth_bp = Blueprint("auth", __name__)
auth_views = Blueprint("auth_views", __name__)


@auth_views.route("/login")
def login_page():
    """Render the dedicated Login Gateway."""
    if "user_id" in session:
        try:
            return redirect(url_for("views.dashboard"))
        except Exception:
            return redirect("/")
    show_demo = current_app.config.get("SHOW_DEMO_CREDENTIALS", True)
    return render_template("login.html", show_demo_credentials=show_demo)


def normalize_role(r: str) -> str:
    """Normalize NEXUS 2.0 and legacy role names to standard role identifier."""
    up = str(r or "").strip().upper()
    if up in ("CHAIR", "PROG_CHA"):
        return "CHAIR"
    if up in ("FACULTY", "FCLTY_DEPT"):
        return "FACULTY"
    if up in ("STUDENT", "STDN_MYR"):
        return "STUDENT"
    return up


def get_effective_role() -> str:
    """Return the currently active impersonated or authenticated role."""
    return normalize_role(session.get("active_role") or session.get("role") or "")


def get_effective_program() -> str:
    """Return the currently active program scope (e.g., MEE, CE, CPE, or None for Admin)."""
    if "active_program" in session:
        return session.get("active_program")
    if "program" in session:
        return session.get("program")
    user_id = session.get("user_id")
    if user_id:
        user = db.session.get(User, user_id)
        if user and user.program:
            return user.program
    return None


def get_effective_reference_id():
    """Return the currently active reference ID (Faculty.id or Section.id)."""
    if "active_reference_id" in session:
        return session.get("active_reference_id")
    return session.get("reference_id")


def login_required(f):
    """
    Session Guard Decorator.
    Redirects unauthenticated users to the Login Gateway for page routes,
    or returns HTTP 401 for REST API routes.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Unauthorized: Authentication required."}), 401
            try:
                return redirect(url_for("auth_views.login_page"))
            except Exception:
                try:
                    return redirect(url_for("views.login_page"))
                except Exception:
                    return redirect("/login")
        return f(*args, **kwargs)

    return decorated_function




def require_roles(*roles):
    """
    Role-Based Access Control decorator.
    Enforces that the active session holds one of the specified roles (supporting aliases).
    Fails closed:
      - HTTP 401 Unauthorized if unauthenticated.
      - HTTP 403 Forbidden if active role lacks required permissions.
    """
    target_roles = {normalize_role(r) for r in roles} | {str(r).upper() for r in roles}

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                return (
                    jsonify({"error": "Unauthorized: Authentication required."}),
                    401,
                )
            current_role = get_effective_role()
            norm_current = normalize_role(current_role)
            if not current_role or (current_role not in target_roles and norm_current not in target_roles):
                return (
                    jsonify({"error": "Unauthorized: Insufficient permissions"}),
                    403,
                )
            return f(*args, **kwargs)

        return decorated_function

    return decorator


@auth_bp.route("/login", methods=["POST"])
def login():
    """
    POST /api/auth/login
    Inputs: { "username": "...", "password": "..." } or form data.
    """
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data:
        return jsonify({"error": "No login data provided"}), 400

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()

    if not username or not password:
        return (
            jsonify({"error": "Username and password are required."}),
            400,
        )

    try:
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            return (
                jsonify({"error": "Invalid username or password"}),
                401,
            )

        # Initialize session
        norm_role = normalize_role(user.role)
        session.clear()
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = norm_role
        session["active_role"] = norm_role
        session["program"] = user.program
        session["active_program"] = user.program
        session["reference_id"] = user.reference_id
        session["active_reference_id"] = user.reference_id
        session["must_change_credentials"] = user.must_change_credentials
        session.permanent = True

        # Record login audit safely
        try:
            audit = AuditLog(
                user_id=user.id,
                action="USER_LOGIN",
                details=f"User #{user.id} ({user.username}, {user.role}, {user.program or 'ALL'}) logged in.",
            )
            db.session.add(audit)
            db.session.commit()
        except Exception as audit_err:
            db.session.rollback()
            print(f"[AUTH AUDIT WARNING] Could not record login audit: {audit_err}", flush=True)

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Login successful",
                    "redirect": "/schedules" if normalize_role(user.role) in ["STUDENT", "FACULTY"] else "/dashboard",
                    "role": norm_role,
                    "user": user.to_dict(),
                    "user_role": norm_role,
                    "user_program": user.program,
                    "program": user.program,
                    "active_program": user.program,
                    "must_change_credentials": user.must_change_credentials,
                    "active_role": norm_role,
                    "active_reference_id": user.reference_id,
                }
            ),
            200,
        )
    except Exception as err:
        print(f"[AUTH ERROR] Failed during login execution: {str(err)}", flush=True)
        return jsonify({"error": f"Internal authentication error: {str(err)}"}), 500


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """POST /api/auth/logout - Terminate active session."""
    user_id = session.get("user_id")
    if user_id:
        audit = AuditLog(
            user_id=user_id,
            action="USER_LOGOUT",
            details=f"User #{user_id} logged out.",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    session.clear()
    return (
        jsonify({"status": "success", "message": "Logged out successfully."}),
        200,
    )


@auth_bp.route("/demo-credentials", methods=["GET"])
def get_demo_credentials():
    """
    GET /api/auth/demo-credentials
    Dynamically returns current demo account credentials directly from database.
    Reflects any credential updates made via Profile / Settings immediately.
    """
    show_creds = current_app.config.get("SHOW_DEMO_CREDENTIALS", True)

    dean = User.query.filter_by(role="DEAN").first()
    chair = User.query.filter_by(role="CHAIR").first()
    admin = User.query.filter_by(role="ADMIN").first()
    faculty = User.query.filter_by(role="FACULTY").first()
    student = User.query.filter_by(role="STUDENT").first()

    all_users = User.query.filter(User.username.in_([
        "dean", "admin", "chair_mee", "chair_ce", "chair_cpe", "chair_ee", "chair_ece",
        "chair_ie", "chair_mfge", "chair_me", "tullao", "bugayong", "roque",
        "student_mee1a", "mayor_mee1a", "student_ce1a"
    ])).all()

    accounts_list = [u.to_dict() for u in all_users]

    return (
        jsonify(
            {
                "status": "success",
                "show_demo_credentials": show_creds,
                "dean": {
                    "username": dean.username if dean else "dean",
                    "password": (
                        dean.demo_password if dean and dean.demo_password else "nexus2026"
                    ),
                    "role": "College Dean (DEAN)",
                    "program": "ALL",
                },
                "chair": {
                    "username": chair.username if chair else "chair_mee",
                    "password": (
                        chair.demo_password if chair and chair.demo_password else "nexus2026"
                    ),
                    "role": "Program Chair (CHAIR)",
                    "program": chair.program if chair else "MEE",
                },
                "admin": {
                    "username": admin.username if admin else "admin",
                    "password": (
                        admin.demo_password if admin and admin.demo_password else "nexus2026"
                    ),
                    "role": "Administrator (ADMIN)",
                    "program": "ALL",
                },
                "faculty": {
                    "username": faculty.username if faculty else "tullao",
                    "password": (
                        faculty.demo_password
                        if faculty and faculty.demo_password
                        else "nexus2026"
                    ),
                    "role": "Faculty (FACULTY)",
                    "program": faculty.program if faculty else "MEE",
                },
                "student": {
                    "username": student.username if student else "student_mee1a",
                    "password": (
                        student.demo_password
                        if student and student.demo_password
                        else "nexus2026"
                    ),
                    "role": "Student (STUDENT)",
                    "program": student.program if student else "MEE",
                },
                "accounts": accounts_list,
            }
        ),
        200,
    )


@auth_bp.route("/update-credentials", methods=["POST"])
@auth_bp.route("/change-credentials", methods=["POST"])
@login_required
def change_credentials():
    """
    POST /api/auth/update-credentials or /api/auth/change-credentials
    Allows Program Chair or any authenticated user to change their username and/or password.
    Writes new password hash to DB, commits, updates session, and invalidates old credentials immediately.
    """
    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_username = (data.get("new_username") or "").strip()
    new_password = data.get("new_password", "")

    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User account not found."}), 404

    # Verify current password
    if not current_password or not user.check_password(current_password):
        return jsonify({"error": "Current password is incorrect."}), 400

    changes = []

    # Update username if specified and changed
    if new_username and new_username != user.username:
        if len(new_username) < 3:
            return jsonify({"error": "Username must be at least 3 characters long."}), 400

        existing = User.query.filter(User.username == new_username, User.id != user.id).first()
        if existing:
            return jsonify({"error": f"Username '{new_username}' is already taken."}), 409

        old_username = user.username
        user.username = new_username
        session["username"] = new_username
        changes.append(f"username changed from '{old_username}' to '{new_username}'")

    # Update password if specified
    if new_password:
        if len(new_password) < 6:
            return jsonify({"error": "New password must be at least 6 characters long."}), 400
        user.set_password(new_password)
        user.demo_password = new_password
        changes.append("password updated")

    if not changes:
        return jsonify({"error": "Please provide a new username or new password to update."}), 400

    user.must_change_credentials = False
    session["must_change_credentials"] = False

    audit = AuditLog(
        user_id=user.id,
        action="CREDENTIALS_CHANGED",
        details=f"User #{user.id} updated credentials: {', '.join(changes)}.",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": "Credentials updated successfully.",
                "user": user.to_dict(),
            }
        ),
        200,
    )


@auth_bp.route("/impersonate", methods=["POST"])
def impersonate():
    """
    POST /api/auth/impersonate
    Pitch bar endpoint allowing rapid role switching between CHAIR, FACULTY, and STUDENT.
    Restricted to authenticated Program Chair and Admin users.
    """
    # Enforce role restriction: genuine Students and Faculty cannot impersonate
    auth_role = normalize_role(session.get("role"))
    if auth_role not in ["CHAIR", "ADMIN", "DEAN"]:
        return (
            jsonify(
                {
                    "error": "Access denied: Role impersonation is strictly reserved for Program Chair and Administrator accounts."
                }
            ),
            403,
        )

    data = request.get_json(silent=True) or {}
    raw_role = str(data.get("role", "")).strip().upper()
    target_program = data.get("program")
    reference_id = data.get("reference_id")

    target_role = normalize_role(raw_role)
    allowed_roles = {"DEAN", "ADMIN", "CHAIR", "PROG_CHA", "FACULTY", "FCLTY_DEPT", "STUDENT", "STDN_MYR"}
    if target_role not in allowed_roles and raw_role not in allowed_roles:
        return (
            jsonify(
                {
                    "error": f"Invalid role: '{raw_role}'. Must be one of {sorted(list(allowed_roles))}."
                }
            ),
            400,
        )

    # Scoping assignments for role impersonation
    if target_role in ("DEAN", "ADMIN"):
        target_program = None
        reference_id = None
    elif target_role == "CHAIR":
        target_program = (target_program or "MEE").strip().upper()
        reference_id = None
    elif target_role == "FACULTY":
        if reference_id is None:
            tullao = Faculty.query.filter(Faculty.name.ilike("%TULLAO%")).first()
            if tullao:
                reference_id = tullao.id
                target_program = tullao.program
            else:
                fac = Faculty.query.first()
                reference_id = fac.id if fac else None
                target_program = fac.program if fac else "MEE"
        else:
            reference_id = int(reference_id)
            fac_rec = db.session.get(Faculty, reference_id)
            if fac_rec:
                target_program = fac_rec.program
    elif target_role == "STUDENT":
        if reference_id is None:
            mee1a = Section.query.filter(Section.name.ilike("%MEE%1A%")).first()
            if mee1a:
                reference_id = mee1a.id
                target_program = "MEE"
            else:
                sec = Section.query.first()
                reference_id = sec.id if sec else None
                target_program = sec.program if sec else "MEE"
        else:
            reference_id = int(reference_id)
            sec_rec = db.session.get(Section, reference_id)
            if sec_rec:
                target_program = sec_rec.program

    # Ensure a valid session user exists when switching role in live presentation
    if "user_id" not in session:
        default_user = User.query.filter_by(role=target_role).first()
        if not default_user:
            default_user = User.query.first()
        if default_user:
            session["user_id"] = default_user.id
            session["username"] = default_user.username
            session["role"] = default_user.role
            session["must_change_credentials"] = default_user.must_change_credentials

    session["active_role"] = target_role
    session["active_reference_id"] = reference_id
    session["active_program"] = target_program

    return (
        jsonify(
            {
                "status": "success",
                "active_role": target_role,
                "active_reference_id": reference_id,
                "active_program": target_program,
                "message": f"Session role successfully set to {target_role} ({target_program or 'ALL'}).",
            }
        ),
        200,
    )


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    """GET /api/auth/me - Retrieve current session context."""
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None

    return (
        jsonify(
            {
                "status": "success",
                "logged_in": bool(user_id),
                "user_id": user_id,
                "username": session.get("username"),
                "native_role": session.get("role"),
                "native_reference_id": session.get("reference_id"),
                "active_role": get_effective_role(),
                "active_reference_id": get_effective_reference_id(),
                "user_role": get_effective_role(),
                "user_program": get_effective_program(),
                "active_program": get_effective_program(),
                "program": session.get("program"),
                "must_change_credentials": bool(user.must_change_credentials if user else session.get("must_change_credentials")),
                "user": user.to_dict() if user else None,
            }
        ),
        200,
    )
