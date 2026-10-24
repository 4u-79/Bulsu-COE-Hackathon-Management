"""COE SYNC 2026 - Program Chair Availability & Governance Routes

Endpoints:
- POST /api/chair/status: Toggle Program Chair active vs. out of office status (CHAIR, ADMIN)
- GET /api/chair/status: Retrieve Program Chair active status (hidden from STUDENT with 403)
"""

from flask import Blueprint, request, jsonify, session
from models import db, User, AuditLog
from routes.auth import login_required, require_roles, get_effective_role

chair_bp = Blueprint("chair", __name__)


@chair_bp.route("/status", methods=["GET"])
@login_required
def get_chair_status():
    """
    GET /api/chair/status
    Retrieves the current Program Chair active/availability status.
    Strict Role Isolation:
      - CHAIR, ADMIN, FACULTY: Returns status and chair name.
      - STUDENT: Returns 403 Forbidden with is_active: null.
    """
    effective_role = get_effective_role()
    if effective_role == "STUDENT":
        return (
            jsonify(
                {
                    "status": "error",
                    "error": "Access restricted: Program Chair status is hidden from students.",
                    "is_active": None,
                }
            ),
            403,
        )

    chair_user = User.query.filter_by(role="CHAIR").first()
    is_active = chair_user.is_active_status if chair_user else True
    chair_name = "Engr. Roberto Ramirez (Program Chair)"
    if chair_user and chair_user.username != "chair":
        chair_name = f"{chair_user.username.capitalize()} (Program Chair)"

    return (
        jsonify(
            {
                "status": "success",
                "chair_name": chair_name,
                "is_active": is_active,
            }
        ),
        200,
    )


@chair_bp.route("/status", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def update_chair_status():
    """
    POST /api/chair/status
    Toggles Program Chair Active vs. Inactive / Out of Office status.
    Payload: { "is_active": true/false }
    """
    payload = request.get_json(silent=True) or {}
    if "is_active" not in payload:
        return (
            jsonify(
                {
                    "status": "error",
                    "error": "Missing required boolean field 'is_active'.",
                }
            ),
            400,
        )

    is_active = bool(payload.get("is_active"))

    # Update chair users
    chair_users = User.query.filter_by(role="CHAIR").all()
    for u in chair_users:
        u.is_active_status = is_active

    # Also update current user if CHAIR
    current_user_id = session.get("user_id")
    if current_user_id:
        current_user = db.session.get(User, current_user_id)
        if current_user and current_user.role == "CHAIR":
            current_user.is_active_status = is_active

    status_str = "ACTIVE" if is_active else "INACTIVE / OUT OF OFFICE"
    audit = AuditLog(
        user_id=current_user_id,
        action="CHAIR_STATUS_UPDATED",
        details=f"Program Chair availability status set to {status_str}.",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Program Chair status successfully updated to {status_str}.",
                "is_active": is_active,
            }
        ),
        200,
    )
