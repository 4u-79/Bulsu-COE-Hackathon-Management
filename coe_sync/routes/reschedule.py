"""COE SYNC 2026 - 2-Tier Student Reschedule Request Pipeline

Endpoints:
- POST /api/reschedule/request: Student submits a proposed reschedule (STUDENT)
- GET /api/reschedule/requests: Scoped list of requests by role (STUDENT, FACULTY, CHAIR, ADMIN)
- POST /api/reschedule/<int:id>/faculty-review: Faculty endorsement or rejection (FACULTY)
- POST /api/reschedule/<int:id>/chair-decision: Program Chair final decision & atomic update (CHAIR, ADMIN)
"""

from flask import Blueprint, request, jsonify, session
from models import db, Schedule, Section, Faculty, RescheduleRequest, AuditLog
from services.conflict_detector import validate_schedule_slot, parse_time, find_alternatives
from routes.auth import require_roles, get_effective_role, get_effective_reference_id

reschedule_bp = Blueprint("reschedule", __name__)


@reschedule_bp.route("/reschedule/request", methods=["POST"])
@require_roles("STUDENT")
def submit_reschedule_request():
    """
    POST /api/reschedule/request
    Student creates a reschedule proposal for a class in their section.
    Payload: {
        "schedule_id": int,
        "proposed_day": "MON".."SAT",
        "proposed_start_time": "HH:MM",
        "proposed_end_time": "HH:MM",
        "reason": "..."
    }
    """
    payload = request.get_json(silent=True) or {}
    schedule_id = payload.get("schedule_id")
    proposed_day = (payload.get("proposed_day") or "").strip().upper()
    proposed_start_str = (payload.get("proposed_start_time") or "").strip()
    proposed_end_str = (payload.get("proposed_end_time") or "").strip()
    reason = (payload.get("reason") or "").strip()

    if not all([schedule_id, proposed_day, proposed_start_str, proposed_end_str, reason]):
        return (
            jsonify({"error": "Missing required fields: schedule_id, proposed_day, proposed_start_time, proposed_end_time, reason."}),
            400,
        )

    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": f"Schedule #{schedule_id} not found."}), 404

    # Validate student section ownership (fails closed if unassigned or mismatched)
    effective_sec_id = get_effective_reference_id()
    if not effective_sec_id or schedule.section_id != effective_sec_id:
        return (
            jsonify({"error": "Unauthorized: You can only request reschedule for classes in your section."}),
            403,
        )

    # Validate time formatting
    proposed_start = parse_time(proposed_start_str)
    proposed_end = parse_time(proposed_end_str)
    if not proposed_start or not proposed_end:
        return jsonify({"error": "Invalid time format. Use HH:MM or HH:MM:SS."}), 400

    if proposed_start >= proposed_end:
        return jsonify({"error": "Proposed start time must precede proposed end time."}), 400

    valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT"}
    if proposed_day not in valid_days:
        return jsonify({"error": f"Invalid proposed day. Must be one of: {sorted(valid_days)}."}), 400

    # Pre-flight conflict check to warn if the proposed slot is already an impossible collision
    candidate_payload = {
        "subject_id": schedule.subject_id,
        "section_id": schedule.section_id,
        "faculty_id": schedule.faculty_id,
        "room_id": schedule.room_id,
        "day_of_week": proposed_day,
        "start_time": proposed_start_str,
        "end_time": proposed_end_str,
    }
    val = validate_schedule_slot(candidate_payload, exclude_schedule_id=schedule.id)
    if not val["valid"]:
        suggestions = find_alternatives(candidate_payload, exclude_schedule_id=schedule.id)
        return (
            jsonify(
                {
                    "error": "The proposed slot causes scheduling collisions.",
                    "conflicts": val["conflicts"],
                    "suggestions": suggestions,
                }
            ),
            409,
        )

    # Create Reschedule Request
    req = RescheduleRequest(
        schedule_id=schedule.id,
        student_section_id=schedule.section_id,
        proposed_day=proposed_day,
        proposed_start_time=proposed_start,
        proposed_end_time=proposed_end,
        reason=reason,
        status="PENDING_FACULTY",
    )
    db.session.add(req)

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="RESCHEDULE_REQUESTED",
        details=(
            f"Section #{schedule.section_id} requested reschedule for {schedule.subject.code} "
            f"to {proposed_day} {proposed_start_str}-{proposed_end_str}. Reason: {reason}"
        ),
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": "Reschedule request successfully submitted for Faculty review.",
                "data": req.to_dict(),
            }
        ),
        201,
    )


@reschedule_bp.route("/reschedule/requests", methods=["GET"])
def get_reschedule_requests():
    """
    GET /api/reschedule/requests
    Returns scoped reschedule requests based on the effective user role:
      - STUDENT: Requests submitted by their section
      - FACULTY: Requests on classes taught by this instructor
      - CHAIR / ADMIN: Requests awaiting final decision (PENDING_CHAIR) or all
    """
    effective_role = get_effective_role()
    effective_ref_id = get_effective_reference_id()

    query = RescheduleRequest.query

    status_filter = request.args.get("status")
    if status_filter:
        query = query.filter(RescheduleRequest.status == status_filter.strip().upper())

    if effective_role == "STUDENT":
        if effective_ref_id:
            query = query.filter(RescheduleRequest.student_section_id == effective_ref_id)
    elif effective_role == "FACULTY":
        # Scoped to schedules where faculty_id == instructor reference ID
        query = query.join(Schedule, RescheduleRequest.schedule_id == Schedule.id)
        if effective_ref_id:
            query = query.filter(Schedule.faculty_id == effective_ref_id)
    elif effective_role in {"CHAIR", "ADMIN"}:
        # Allowed to view all or filtered by status
        pass

    requests_list = query.order_by(RescheduleRequest.created_at.desc()).all()

    return (
        jsonify(
            {
                "status": "success",
                "count": len(requests_list),
                "data": [r.to_dict() for r in requests_list],
            }
        ),
        200,
    )


@reschedule_bp.route("/reschedule/<int:request_id>/faculty-review", methods=["POST"])
@require_roles("FACULTY", "CHAIR", "ADMIN")
def faculty_review_reschedule(request_id: int):
    """
    POST /api/reschedule/<id>/faculty-review
    Faculty reviews a student proposal.
    Payload: { "approved": true/false, "feedback": "..." }
    """
    req_obj = db.session.get(RescheduleRequest, request_id)
    if not req_obj:
        return jsonify({"error": f"Reschedule request #{request_id} not found."}), 404

    if req_obj.status != "PENDING_FACULTY":
        return (
            jsonify({"error": f"Request #{request_id} is not awaiting faculty review (current status: {req_obj.status})."}),
            400,
        )

    # Enforce faculty assignment verification (fails closed if unassigned or mismatched)
    effective_role = get_effective_role()
    effective_ref_id = get_effective_reference_id()
    if effective_role == "FACULTY":
        if not effective_ref_id or not req_obj.schedule or req_obj.schedule.faculty_id != effective_ref_id:
            return jsonify({"error": "Unauthorized: You are not the assigned instructor for this class."}), 403

    payload = request.get_json(silent=True) or {}
    approved = bool(payload.get("approved"))
    feedback = (payload.get("feedback") or "").strip()

    req_obj.faculty_feedback = feedback
    if approved:
        req_obj.status = "PENDING_CHAIR"
        action_msg = "endorsed proposal. Forwarded to Program Chair for final approval."
    else:
        req_obj.status = "REJECTED"
        action_msg = f"rejected proposal. Feedback: {feedback or 'No feedback provided'}"

    audit = AuditLog(
        user_id=session.get("user_id"),
        action=f"RESCHEDULE_FACULTY_{'APPROVED' if approved else 'REJECTED'}",
        details=f"Faculty {action_msg} on RescheduleRequest #{req_obj.id}.",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Faculty {action_msg}",
                "data": req_obj.to_dict(),
            }
        ),
        200,
    )


@reschedule_bp.route("/reschedule/<int:request_id>/chair-decision", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def chair_decision_reschedule(request_id: int):
    """
    POST /api/reschedule/<id>/chair-decision
    Program Chair / Admin makes the final authorization.
    If approved:
      1. Validates that zero hard conflicts exist at the moment of approval.
      2. Atomically mutates the Schedule's day and start/end time.
      3. Sets status to APPROVED.
    """
    req_obj = db.session.get(RescheduleRequest, request_id)
    if not req_obj:
        return jsonify({"error": f"Reschedule request #{request_id} not found."}), 404

    if req_obj.status not in {"PENDING_CHAIR", "PENDING_FACULTY"}:
        return (
            jsonify({"error": f"Request #{request_id} is already finalized (status: {req_obj.status})."}),
            400,
        )

    payload = request.get_json(silent=True) or {}
    approved = bool(payload.get("approved"))
    feedback = (payload.get("feedback") or "").strip()

    req_obj.chair_feedback = feedback

    if not approved:
        req_obj.status = "REJECTED"
        audit = AuditLog(
            user_id=session.get("user_id"),
            action="RESCHEDULE_CHAIR_REJECTED",
            details=f"Chair rejected RescheduleRequest #{req_obj.id}. Feedback: {feedback or 'None'}",
        )
        db.session.add(audit)
        db.session.commit()
        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Reschedule request rejected by Program Chair.",
                    "data": req_obj.to_dict(),
                }
            ),
            200,
        )

    # Validating current slot conflicts before applying atomic timetable mutation
    sched = req_obj.schedule
    if not sched:
        return jsonify({"error": "Associated schedule record no longer exists."}), 404

    candidate_payload = {
        "subject_id": sched.subject_id,
        "section_id": sched.section_id,
        "faculty_id": sched.faculty_id,
        "room_id": sched.room_id,
        "day_of_week": req_obj.proposed_day,
        "start_time": req_obj.proposed_start_time.strftime("%H:%M"),
        "end_time": req_obj.proposed_end_time.strftime("%H:%M"),
    }
    val = validate_schedule_slot(candidate_payload, exclude_schedule_id=sched.id)
    if not val["valid"]:
        suggestions = find_alternatives(candidate_payload, exclude_schedule_id=sched.id)
        return (
            jsonify(
                {
                    "error": "Cannot approve: Proposed slot now conflicts with active schedules.",
                    "conflicts": val["conflicts"],
                    "suggestions": suggestions,
                }
            ),
            409,
        )

    # Atomic Schedule Mutation with transaction rollback guarantee
    try:
        sched.day_of_week = req_obj.proposed_day
        sched.start_time = req_obj.proposed_start_time
        sched.end_time = req_obj.proposed_end_time
        req_obj.status = "APPROVED"

        audit = AuditLog(
            user_id=session.get("user_id"),
            action="RESCHEDULE_CHAIR_APPROVED",
            details=(
                f"Chair approved RescheduleRequest #{req_obj.id}. Schedule #{sched.id} moved to "
                f"{req_obj.proposed_day} {req_obj.proposed_start_time}-{req_obj.proposed_end_time}."
            ),
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": f"Failed to commit timetable update atomically: {str(e)}",
                }
            ),
            500,
        )

    return (
        jsonify(
            {
                "status": "success",
                "message": "Reschedule request approved. Class timetable automatically updated.",
                "data": req_obj.to_dict(),
                "updated_schedule": sched.to_dict(),
            }
        ),
        200,
    )
