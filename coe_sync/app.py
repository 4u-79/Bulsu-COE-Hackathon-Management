import os
import sys
from pathlib import Path
from flask import Flask, jsonify, render_template, request, session
from flask_cors import CORS
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config import config_by_name
from models import (
    db,
    User,
    Faculty,
    Section,
    Subject,
    Room,
    FacultyAvailability,
    Schedule,
    AuditLog,
    Conflict,
    RescheduleRequest,
)
from routes.auth import (
    auth_bp,
    auth_views,
    login_required,
    require_roles,
    normalize_role,
)
from routes.schedules import schedules_bp
from routes.analytics import analytics_bp
from routes.master_data import master_data_bp
from routes.views import views_bp
from routes.chair import chair_bp
from routes.reschedule import reschedule_bp


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Enforce foreign key constraints on SQLite connections for parity
    with production MySQL/MariaDB engines.
    """
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


def create_app(config_name=None):
    """
    Application factory pattern initializing Flask, configurations,
    CORS, SQLAlchemy, Session management, Blueprints, and CLI commands.
    """
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # Load configuration
    selected_config = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(selected_config)

    # Configure session security and secrets
    app.secret_key = app.config.get(
        "SECRET_KEY", "coe-sync-2026-default-secret-key-bulsu-cpe"
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    # Ensure instance directory exists for SQLite storage
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except Exception:
        pass

    # Initialize extensions
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        supports_credentials=True,
    )
    db.init_app(app)

    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass

    # -------------------------------------------------------------
    # Register Modular Blueprints
    # -------------------------------------------------------------
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(auth_views)
    app.register_blueprint(schedules_bp, url_prefix="/api")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(chair_bp, url_prefix="/api/chair")
    app.register_blueprint(reschedule_bp, url_prefix="/api")
    app.register_blueprint(master_data_bp)
    app.register_blueprint(views_bp)

    # -------------------------------------------------------------
    # Global Error Handlers (JSON responses for REST API)
    # -------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(error):
        msg = (
            getattr(error, "description", None)
            or "Bad Request: Invalid payload or parameters."
        )
        return jsonify({"status": "error", "error": msg}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        msg = (
            getattr(error, "description", None)
            or "Unauthorized: Authentication required."
        )
        return jsonify({"status": "error", "error": msg}), 401

    @app.errorhandler(403)
    def forbidden(error):
        msg = (
            getattr(error, "description", None)
            or "Unauthorized: Insufficient permissions."
        )
        return jsonify({"status": "error", "error": msg}), 403

    @app.errorhandler(404)
    def not_found(error):
        msg = (
            getattr(error, "description", None)
            or "The requested resource was not found."
        )
        return jsonify({"status": "error", "error": msg}), 404

    @app.errorhandler(409)
    def conflict(error):
        msg = (
            getattr(error, "description", None)
            or "Resource conflict or constraint violation."
        )
        return jsonify({"status": "error", "error": msg}), 409

    @app.errorhandler(500)
    def server_error(error):
        return (
            jsonify(
                {
                    "status": "error",
                    "error": "Internal Server Error. Please inspect application logs.",
                }
            ),
            500,
        )

    # -------------------------------------------------------------
    # CLI Commands
    # -------------------------------------------------------------
    @app.cli.command("seed-db")
    def seed_db_command():
        """CLI command to reset and seed the database with mock data."""
        from seed_data import seed_database

        seed_database(app)
        print("[COE SYNC 2026] seed-db command completed successfully.")

    @app.cli.command("init-db")
    def init_db_command():
        """CLI command to initialize database schema without mock data."""
        with app.app_context():
            db.create_all()
            print("[COE SYNC 2026] Database tables created.")

    # -------------------------------------------------------------
    # Legacy / Sandbox Console Route (Phase 1 & 2 Testing)
    # -------------------------------------------------------------
    @app.route("/console")
    def console():
        """Render the COE SYNC 2026 legacy test console."""
        return render_template("index.html")

    # -------------------------------------------------------------
    # Health Check & Baseline Entity REST API Routes
    # -------------------------------------------------------------
    @app.route("/api/health", methods=["GET"])
    def health_check():
        """
        Health check route required by Phase 1 & Phase 2 specifications.
        Returns: {"status": "ok", "app": "COE SYNC 2026"}
        """
        return jsonify({"status": "ok", "app": "COE SYNC 2026"}), 200

    @app.route("/api/stats", methods=["GET"])
    def get_stats():
        """Return system-wide statistics for the dashboard."""
        try:
            stats = {
                "users_count": User.query.count(),
                "faculty_count": Faculty.query.count(),
                "sections_count": Section.query.count(),
                "rooms_count": Room.query.count(),
                "subjects_count": Subject.query.count(),
                "schedules_count": Schedule.query.count(),
                "audit_logs_count": AuditLog.query.count(),
            }
            return jsonify({"status": "success", "data": stats}), 200
        except Exception as e:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": str(e),
                        "hint": "Run 'python seed_data.py' or 'flask seed-db' to initialize database.",
                    }
                ),
                500,
            )

    @app.route("/api/users", methods=["GET"])
    def list_users():
        """List all users without password hashes."""
        users = User.query.order_by(User.id.asc()).all()
        return (
            jsonify(
                {
                    "status": "success",
                    "count": len(users),
                    "data": [u.to_dict() for u in users],
                }
            ),
            200,
        )

    @app.route("/api/faculty", methods=["GET"])
    @app.route("/api/master/faculty", methods=["GET"])
    def list_faculty():
        """List all faculty members and their unit workloads with optional filtering."""
        query = Faculty.query
        search = request.args.get("search", "").strip()
        program = request.args.get("program", "").strip()
        overloaded = request.args.get("overloaded")

        effective_role = normalize_role(session.get("active_role") or session.get("role"))
        effective_prog = session.get("active_program") or session.get("program")
        if effective_role == "CHAIR" and effective_prog:
            program = effective_prog

        if search:
            query = query.filter(
                (Faculty.name.ilike(f"%{search}%")) | (Faculty.email.ilike(f"%{search}%"))
            )
        if program and program.upper() != "ALL":
            prog_clean = program.strip().upper()
            if prog_clean == "GEN":
                query = query.filter(Faculty.program == "GEN")
            else:
                query = query.filter(Faculty.program.in_([prog_clean, "GEN"]))
        if overloaded is not None:
            if str(overloaded).lower() in ("true", "1", "yes"):
                query = query.filter(Faculty.current_units > Faculty.max_units)
            elif str(overloaded).lower() in ("false", "0", "no"):
                query = query.filter(Faculty.current_units <= Faculty.max_units)

        faculty = query.order_by(Faculty.id.asc()).all()
        return (
            jsonify(
                {
                    "status": "success",
                    "count": len(faculty),
                    "data": [f.to_dict() for f in faculty],
                }
            ),
            200,
        )

    @app.route("/api/sections", methods=["GET"])
    @app.route("/api/master/sections", methods=["GET"])
    def list_sections():
        """List academic cohort sections with optional filtering."""
        query = Section.query
        search = request.args.get("search", "").strip()
        program = request.args.get("program", "").strip()
        year_level = request.args.get("year_level", type=int)
        faculty_id = request.args.get("faculty_id", type=int)

        effective_role = normalize_role(session.get("active_role") or session.get("role"))
        effective_prog = session.get("active_program") or session.get("program")
        if effective_role == "CHAIR" and effective_prog:
            program = effective_prog
        elif effective_role == "STUDENT":
            effective_ref_id = session.get("active_reference_id") or session.get("reference_id")
            if effective_ref_id:
                query = query.filter(Section.id == effective_ref_id)

        if not faculty_id and effective_role == "FACULTY":
            faculty_id = session.get("active_reference_id") or session.get("reference_id")

        if faculty_id:
            sec_ids = [row[0] for row in db.session.query(Schedule.section_id).filter(Schedule.faculty_id == faculty_id).distinct().all()]
            query = query.filter(Section.id.in_(sec_ids))

        if search:
            query = query.filter(
                db.or_(
                    Section.name.ilike(f"%{search}%"),
                    Section.class_mayor.ilike(f"%{search}%"),
                )
            )
        if program and program.upper() != "ALL":
            prog_clean = program.strip().upper()
            query = query.filter(Section.program == prog_clean)
        if year_level:
            query = query.filter(Section.year_level == year_level)

        sections = query.order_by(
            Section.year_level.asc(), Section.name.asc()
        ).all()
        return (
            jsonify(
                {
                    "status": "success",
                    "count": len(sections),
                    "data": [s.to_dict() for s in sections],
                }
            ),
            200,
        )

    @app.route("/api/subjects", methods=["GET"])
    @app.route("/api/master/subjects", methods=["GET"])
    def list_subjects():
        """List course subjects with optional filtering."""
        query = Subject.query
        search = request.args.get("search", "").strip()
        program = request.args.get("program", "").strip()
        year_level = request.args.get("year_level", type=int)
        semester = request.args.get("semester", type=int)
        subject_type = request.args.get("type", "").strip().upper()
        classification = request.args.get("classification", "").strip().upper()
        units = request.args.get("units", type=int)
        faculty_id = request.args.get("faculty_id", type=int)
        curriculum = str(request.args.get("curriculum", "")).lower() == "true"

        effective_role = normalize_role(session.get("active_role") or session.get("role"))
        effective_prog = session.get("active_program") or session.get("program")
        if effective_role == "CHAIR" and effective_prog and not curriculum:
            program = effective_prog

        if not faculty_id and effective_role == "FACULTY" and not curriculum:
            faculty_id = session.get("active_reference_id") or session.get("reference_id")

        if faculty_id and not curriculum:
            sub_ids = [row[0] for row in db.session.query(Schedule.subject_id).filter(Schedule.faculty_id == faculty_id).distinct().all()]
            query = query.filter(Subject.id.in_(sub_ids))

        if search:
            query = query.filter(
                (Subject.code.ilike(f"%{search}%")) | (Subject.title.ilike(f"%{search}%"))
            )
        if program and program.upper() != "ALL":
            prog_clean = program.strip().upper()
            if prog_clean == "GEN":
                query = query.filter(Subject.program == "GEN")
            else:
                query = query.filter(Subject.program.in_([prog_clean, "GEN"]))
        if semester:
            query = query.filter(Subject.semester == semester)
        if subject_type in ("LECTURE", "LAB"):
            query = query.filter(Subject.subject_type == subject_type)
        if units:
            query = query.filter(Subject.units == units)

        subjects = query.order_by(Subject.code.asc()).all()
        if year_level:
            subjects = [s for s in subjects if s.computed_year_level == year_level]
        if classification in ("MAJOR", "MINOR"):
            subjects = [s for s in subjects if s.classification == classification]

        return (
            jsonify(
                {
                    "status": "success",
                    "count": len(subjects),
                    "data": [s.to_dict() for s in subjects],
                }
            ),
            200,
        )

    @app.route("/api/rooms", methods=["GET"])
    @app.route("/api/master/rooms", methods=["GET"])
    def list_rooms():
        """List physical rooms and laboratories with optional filtering."""
        query = Room.query
        search = request.args.get("search", "").strip()
        room_type = request.args.get("type", "").strip().upper()
        building = request.args.get("building", "").strip()
        available = request.args.get("available")

        if search:
            query = query.filter(Room.room_code.ilike(f"%{search}%"))
        if room_type in ("LECTURE", "LAB"):
            query = query.filter(Room.room_type == room_type)
        if building and building.upper() != "ALL":
            query = query.filter(Room.building.ilike(f"%{building}%"))
        if available is not None:
            if str(available).lower() in ("true", "1", "yes"):
                query = query.filter(Room.is_available.is_(True))
            elif str(available).lower() in ("false", "0", "no"):
                query = query.filter(Room.is_available.is_(False))

        rooms = query.order_by(Room.room_code.asc()).all()
        return (
            jsonify(
                {
                    "status": "success",
                    "count": len(rooms),
                    "data": [r.to_dict() for r in rooms],
                }
            ),
            200,
        )

    @app.route("/api/availabilities", methods=["GET"])
    @login_required
    @require_roles("CHAIR", "ADMIN", "FACULTY")
    def list_availabilities():
        """List faculty availability constraints."""
        availabilities = FacultyAvailability.query.all()
        result = []
        for a in availabilities:
            d = a.to_dict()
            d["faculty_name"] = a.faculty.name if a.faculty else None
            result.append(d)
        return (
            jsonify(
                {
                    "status": "success",
                    "count": len(result),
                    "data": result,
                }
            ),
            200,
        )

    @app.route("/api/audit-logs", methods=["GET"])
    @login_required
    @require_roles("CHAIR", "ADMIN")
    def list_audit_logs():
        """List chronological audit logs."""
        logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
        return (
            jsonify(
                {
                    "status": "success",
                    "count": len(logs),
                    "data": [l.to_dict() for l in logs],
                }
            ),
            200,
        )

    @app.route("/api/seed", methods=["POST"])
    @login_required
    @require_roles("ADMIN")
    def trigger_seed():
        """API endpoint to wipe and re-seed mock data."""
        from seed_data import seed_database

        result = seed_database(app)
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Database wiped and re-seeded successfully.",
                    "details": result,
                }
            ),
            200,
        )

    return app


# Application instance for WSGI servers / flask run
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[COE SYNC 2026] Starting server on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
