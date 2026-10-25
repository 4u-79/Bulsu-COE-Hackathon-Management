"""COE SYNC 2026 - 2-Tier Student Reschedule Request Pipeline

Endpoints:
- POST /api/reschedule/request: Student submits a proposed reschedule (STUDENT)
- GET /api/reschedule/requests: Scoped list of requests by role (STUDENT, FACULTY, CHAIR, ADMIN)
- POST /api/reschedule/<int:id>/faculty-review: Faculty endorsement or rejection (FACULTY)
- POST /api/reschedule/<int:id>/chair-decision: Program Chair final decision & atomic update (CHAIR, ADMIN)
"""

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session
from models import db, Schedule, Section, Faculty, Room, RescheduleRequest, InterDepartmentRequest, AuditLog
from services.conflict_detector import validate_schedule_slot, parse_time, find_alternatives
from routes.auth import require_roles, get_effective_role, get_effective_reference_id, get_effective_program, login_required, normalize_role

reschedule_bp = Blueprint("reschedule", __name__)


def purge_expired_reschedule_requests() -> int:
    """
    1-Week (7-Day) Auto-Deletion Rule for stale pending reschedule requests.
    Automatically purges pending proposals older than 7 days from creation.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        deleted = (
            RescheduleRequest.query.filter(
                RescheduleRequest.status.in_(["PENDING", "PENDING_FACULTY", "PENDING_CHAIR"]),
                RescheduleRequest.created_at < cutoff,
            ).delete(synchronize_session=False)
        )
        db.session.commit()
        return deleted
    except Exception as err:
        db.session.rollback()
        print(f"[RESCHEDULE PURGE WARNING] Error purging expired requests: {err}", flush=True)
        return 0


@reschedule_bp.route("/reschedule/purge", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def purge_requests_endpoint():
    """Manual trigger to purge expired reschedule requests (> 7 days)."""
    count = purge_expired_reschedule_requests()
    return jsonify({
        "status": "success",
        "purged_count": count,
        "message": f"Successfully purged {count} expired reschedule requests (> 7 days old)."
    }), 200


@reschedule_bp.route("/reschedule/request", methods=["POST"])
@require_roles("STUDENT", "FACULTY", "CHAIR", "ADMIN")
def submit_reschedule_request():
    """
    POST /api/reschedule/request
    Student creates a reschedule proposal for a class in their section.
    Payload: {
        "schedule_id": int,
        "proposed_day": "MON".."SAT",
        "proposed_start_time": "HH:MM",
        "proposed_end_time": "HH:MM",
        "proposed_room_id": int (optional),
        "reason": "..."
    }
    """
    purge_expired_reschedule_requests()

    payload = request.get_json(silent=True) or {}
    schedule_id = payload.get("schedule_id")
    proposed_day = (payload.get("proposed_day") or "").strip().upper()
    proposed_start_str = (payload.get("proposed_start_time") or "").strip()
    proposed_end_str = (payload.get("proposed_end_time") or "").strip()
    proposed_room_id = payload.get("proposed_room_id")
    reason = (payload.get("reason") or "").strip()

    if not all([schedule_id, proposed_day, proposed_start_str, proposed_end_str, reason]):
        return (
            jsonify({"error": "Missing required fields: schedule_id, proposed_day, proposed_start_time, proposed_end_time, reason."}),
            400,
        )

    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": f"Schedule #{schedule_id} not found."}), 404

    effective_role = normalize_role(get_effective_role())
    effective_ref_id = get_effective_reference_id()

    # Validate section/ownership based on role
    if effective_role == "STUDENT":
        if not effective_ref_id or schedule.section_id != effective_ref_id:
            auth_role = normalize_role(session.get("role"))
            if auth_role not in ["CHAIR", "ADMIN"]:
                return (
                    jsonify({"error": "Unauthorized: You can only request reschedule for classes in your section."}),
                    403,
                )
    elif effective_role == "FACULTY":
        if not effective_ref_id or schedule.faculty_id != effective_ref_id:
            auth_role = normalize_role(session.get("role"))
            if auth_role not in ["CHAIR", "ADMIN"]:
                return (
                    jsonify({"error": "Unauthorized: You can only request reschedule for your assigned classes."}),
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

    # Parse room if given
    parsed_room_id = schedule.room_id
    if proposed_room_id:
        try:
            parsed_room_id = int(proposed_room_id)
        except (ValueError, TypeError):
            parsed_room_id = schedule.room_id

    # Pre-flight conflict check to warn if the proposed slot is already an impossible collision
    candidate_payload = {
        "subject_id": schedule.subject_id,
        "section_id": schedule.section_id,
        "faculty_id": schedule.faculty_id,
        "room_id": parsed_room_id,
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
        proposed_room_id=parsed_room_id if proposed_room_id else None,
        requested_by_role=effective_role,
        requested_by_name=session.get("username"),
        reason=reason,
        status="PENDING_FACULTY" if effective_role == "STUDENT" else "PENDING_CHAIR",
    )
    db.session.add(req)

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="RESCHEDULE_REQUESTED",
        details=(
            f"User {session.get('username')} ({effective_role}) requested reschedule for {schedule.subject.code} "
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
    purge_expired_reschedule_requests()

    effective_role = normalize_role(get_effective_role())
    effective_ref_id = get_effective_reference_id()

    query = RescheduleRequest.query

    status_filter = request.args.get("status")
    if status_filter:
        query = query.filter(RescheduleRequest.status == status_filter.strip().upper())

    query = (
        query.outerjoin(Schedule, RescheduleRequest.schedule_id == Schedule.id)
        .outerjoin(Section, RescheduleRequest.student_section_id == Section.id)
        .outerjoin(Room, RescheduleRequest.proposed_room_id == Room.id)
    )

    if effective_role == "STUDENT":
        current_username = session.get("username")
        if effective_ref_id and current_username:
            query = query.filter(
                db.or_(
                    RescheduleRequest.student_section_id == effective_ref_id,
                    RescheduleRequest.requested_by_name == current_username,
                )
            )
        elif effective_ref_id:
            query = query.filter(RescheduleRequest.student_section_id == effective_ref_id)
        elif current_username:
            query = query.filter(RescheduleRequest.requested_by_name == current_username)
    elif effective_role == "FACULTY":
        fac = db.session.get(Faculty, effective_ref_id) if effective_ref_id else None
        fac_prog = fac.program if fac else get_effective_program()
        cur_user = session.get("username")
        conditions = []
        if effective_ref_id:
            conditions.append(Schedule.faculty_id == effective_ref_id)
        if fac_prog:
            # Standalone room booking requests or department section proposals
            conditions.append(
                db.and_(
                    RescheduleRequest.schedule_id.is_(None),
                    db.or_(
                        Section.program == fac_prog,
                        Room.department == fac_prog,
                    ),
                )
            )
        if cur_user:
            conditions.append(RescheduleRequest.requested_by_name == cur_user)
        if conditions:
            query = query.filter(db.or_(*conditions))
    elif effective_role == "CHAIR":
        eff_prog = get_effective_program()
        if eff_prog and eff_prog != "ALL":
            query = query.filter(
                db.or_(
                    Section.program == eff_prog,
                    Room.department == eff_prog,
                    Schedule.faculty.has(program=eff_prog),
                    RescheduleRequest.requested_by_name == session.get("username"),
                )
            )
    elif effective_role in {"ADMIN", "DEAN"}:
        # Collegiate-wide visibility across all departments
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
    purge_expired_reschedule_requests()

    req_obj = db.session.get(RescheduleRequest, request_id)
    if not req_obj:
        return jsonify({"error": f"Reschedule request #{request_id} not found."}), 404

    if req_obj.status not in {"PENDING", "PENDING_FACULTY"}:
        return (
            jsonify({"error": f"Request #{request_id} is not awaiting faculty review (current status: {req_obj.status})."}),
            400,
        )

    # Enforce faculty assignment verification (fails closed if unassigned or mismatched)
    effective_role = normalize_role(get_effective_role())
    effective_ref_id = get_effective_reference_id()
    if effective_role == "FACULTY":
        if req_obj.schedule:
            if not effective_ref_id or req_obj.schedule.faculty_id != effective_ref_id:
                return jsonify({"error": "Unauthorized: You are not the assigned instructor for this class."}), 403
        else:
            fac = db.session.get(Faculty, effective_ref_id) if effective_ref_id else None
            fac_prog = fac.program if fac else get_effective_program()
            sec_prog = req_obj.section.program if req_obj.section else None
            room_dept = req_obj.proposed_room.department if req_obj.proposed_room else None
            if fac_prog and sec_prog and fac_prog != sec_prog and (not room_dept or fac_prog != room_dept):
                return jsonify({"error": "Unauthorized: This room reservation request is outside your department."}), 403

    payload = request.get_json(silent=True) or {}
    if request.path.endswith("/approve"):
        approved = True
    elif request.path.endswith("/reject"):
        approved = False
    else:
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
      2. Atomically mutates the Schedule's day, start/end time, and optional room.
      3. Sets status to APPROVED.
    """
    purge_expired_reschedule_requests()

    req_obj = db.session.get(RescheduleRequest, request_id)
    if not req_obj:
        return jsonify({"error": f"Reschedule request #{request_id} not found."}), 404

    if req_obj.status not in {"PENDING", "PENDING_CHAIR", "PENDING_FACULTY"}:
        return (
            jsonify({"error": f"Request #{request_id} is already finalized (status: {req_obj.status})."}),
            400,
        )

    payload = request.get_json(silent=True) or {}
    action_val = str(payload.get("action") or "").upper()
    if request.path.endswith("/approve") or action_val == "APPROVE":
        approved = True
    elif request.path.endswith("/reject") or action_val in ("REJECT", "DECLINE"):
        approved = False
    else:
        approved = bool(payload.get("approved"))
    feedback = (payload.get("feedback") or payload.get("remarks") or "").strip()

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
        # Handle standalone room booking request (schedule_id is None)
        if req_obj.proposed_room_id:
            target_rm = db.session.get(Room, req_obj.proposed_room_id)
            if target_rm:
                target_rm.booked_by_label = (
                    f"Requested by: {req_obj.requested_by_name or 'Faculty/Student'} "
                    f"(Approved by {session.get('username') or 'Program Chair'})"
                )
            req_obj.status = "APPROVED"
            audit = AuditLog(
                user_id=session.get("user_id"),
                action="ROOM_BOOKING_APPROVED",
                details=f"Chair approved room reservation #{req_obj.id} for {target_rm.room_code if target_rm else 'room'}.",
            )
            db.session.add(audit)
            db.session.commit()
            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"Room reservation for {target_rm.room_code if target_rm else 'room'} approved.",
                        "data": req_obj.to_dict(),
                    }
                ),
                200,
            )
        return jsonify({"error": "Associated schedule record no longer exists."}), 404

    target_room_id = req_obj.proposed_room_id or sched.room_id
    candidate_payload = {
        "subject_id": sched.subject_id,
        "section_id": sched.section_id,
        "faculty_id": sched.faculty_id,
        "room_id": target_room_id,
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
        if req_obj.proposed_room_id:
            sched.room_id = req_obj.proposed_room_id
            target_rm = db.session.get(Room, req_obj.proposed_room_id)
            if target_rm:
                target_rm.booked_by_label = f"Requested by: {req_obj.requested_by_name or 'Faculty/Student'} (Approved by {session.get('username') or 'Chair'})"
        elif sched.room:
            sched.room.booked_by_label = f"Requested by: {req_obj.requested_by_name or 'Faculty/Student'} (Approved by {session.get('username') or 'Chair'})"
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


@reschedule_bp.route("/reschedule/<int:request_id>/approve", methods=["POST"])
@require_roles("FACULTY", "CHAIR", "ADMIN")
def approve_reschedule_alias(request_id: int):
    """Direct approval endpoint router."""
    effective_role = normalize_role(get_effective_role())
    if effective_role == "FACULTY":
        return faculty_review_reschedule(request_id)
    return chair_decision_reschedule(request_id)


@reschedule_bp.route("/reschedule/<int:request_id>/reject", methods=["POST"])
@require_roles("FACULTY", "CHAIR", "ADMIN")
def reject_reschedule_alias(request_id: int):
    """Direct rejection endpoint router."""
    effective_role = normalize_role(get_effective_role())
    if effective_role == "FACULTY":
        return faculty_review_reschedule(request_id)
    return chair_decision_reschedule(request_id)


# -----------------------------------------------------------------
# NEXUS 2.0 Inter-Department Requests & Approvals
# -----------------------------------------------------------------
@reschedule_bp.route("/interdept/requests", methods=["GET"])
def get_interdept_requests():
    """List inter-department room and conflict requests."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    try:
        InterDepartmentRequest.query.filter(
            InterDepartmentRequest.status == "PENDING_APPROVAL",
            InterDepartmentRequest.created_at < cutoff,
        ).update({"status": "EXPIRED"}, synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()

    effective_role = get_effective_role()
    effective_prog = get_effective_program()

    query = InterDepartmentRequest.query
    if effective_role == "CHAIR" and effective_prog and effective_prog != "ALL":
        query = query.filter(
            db.or_(
                InterDepartmentRequest.target_department == effective_prog,
                InterDepartmentRequest.source_department == effective_prog,
                InterDepartmentRequest.target_department == "ADMIN",
            )
        )

    reqs = query.order_by(InterDepartmentRequest.created_at.desc()).all()
    return jsonify({
        "status": "success",
        "count": len(reqs),
        "data": [r.to_dict() for r in reqs]
    }), 200


@reschedule_bp.route("/interdept/<int:req_id>/action", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def act_on_interdept_request(req_id: int):
    """
    Approve or decline an inter-department room request.
    If approved:
      - Automatically applies recommended alternative slot/room to resolve conflict.
      - Sets Room.booked_by_label.
    """
    req_obj = db.session.get(InterDepartmentRequest, req_id)
    if not req_obj:
        return jsonify({"error": f"InterDepartmentRequest #{req_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    action = str(data.get("action", "APPROVE")).strip().upper()
    feedback = (data.get("feedback") or "").strip()
    apply_alt = data.get("apply_alternative", True)

    req_obj.chair_feedback = feedback

    if action in ("DECLINE", "REJECT"):
        req_obj.status = "DECLINED"
        audit = AuditLog(
            user_id=session.get("user_id"),
            action="INTERDEPT_REQUEST_DECLINED",
            details=f"Chair declined InterDepartmentRequest #{req_id}. Reason: {feedback or 'None'}",
        )
        db.session.add(audit)
        db.session.commit()
        return jsonify({
            "status": "success",
            "message": "Inter-department request declined.",
            "data": req_obj.to_dict()
        }), 200

    # APPROVE
    req_obj.status = "APPROVED"
    if apply_alt and req_obj.schedule and req_obj.alternative_recommendations:
        import json
        try:
            alts = json.loads(req_obj.alternative_recommendations)
            if alts and isinstance(alts, list) and len(alts) > 0:
                first_alt = alts[0]
                if "day_of_week" in first_alt:
                    req_obj.schedule.day_of_week = first_alt["day_of_week"]
                if "start_time" in first_alt:
                    req_obj.schedule.start_time = parse_time(first_alt["start_time"])
                if "end_time" in first_alt:
                    req_obj.schedule.end_time = parse_time(first_alt["end_time"])
                if "room_id" in first_alt:
                    req_obj.schedule.room_id = first_alt["room_id"]
        except Exception as e:
            print(f"[INTERDEPT ALT WARNING] Could not apply alternative: {e}", flush=True)

    if req_obj.room:
        req_obj.room.booked_by_label = f"Allocated to {req_obj.source_department} (Approved by {session.get('username') or 'Chair'})"

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="INTERDEPT_REQUEST_APPROVED",
        details=f"Chair approved InterDepartmentRequest #{req_id} for {req_obj.source_department}.",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Inter-department request approved. Timetable updated.",
        "data": req_obj.to_dict()
    }), 200


@reschedule_bp.route("/rooms/request", methods=["POST"])
@login_required
def request_room_booking():
    """
    POST /api/rooms/request
    Student Mayor or Faculty submits an ad-hoc room reservation request.
    """
    data = request.get_json(silent=True) or {}
    room_id = data.get("room_id")
    raw_day = data.get("day_of_week") or data.get("day") or "MON"
    day = str(raw_day).strip().upper()
    start_time_str = (data.get("start_time") or "10:00").strip()
    end_time_str = (data.get("end_time") or "11:30").strip()
    reason = (data.get("reason") or data.get("purpose") or "Class / Section Activity").strip()

    # Time slot string fallback support (e.g., 'MON 13:00-16:00')
    time_slot = data.get("time_slot")
    if time_slot and " " in time_slot and "-" in time_slot:
        parts = time_slot.split(" ", 1)
        day = parts[0].strip().upper()
        times = parts[1].split("-", 1)
        start_time_str = times[0].strip()
        end_time_str = times[1].strip()

    room = db.session.get(Room, room_id) if room_id else None
    if not room:
        return jsonify({"error": "Valid room_id is required."}), 400

    effective_role = get_effective_role()
    effective_ref_id = get_effective_reference_id()
    effective_prog = get_effective_program()

    sec = None
    if effective_role in ("STUDENT", "STDN_MYR"):
        if effective_ref_id:
            sec = db.session.get(Section, effective_ref_id)
        if not sec and effective_prog:
            sec = Section.query.filter_by(program=effective_prog).first()
    elif effective_prog:
        sec = Section.query.filter_by(program=effective_prog).first()

    if not sec:
        sec = Section.query.first()

    sec_id = sec.id if sec else 1

    req = RescheduleRequest(
        schedule_id=None,
        student_section_id=sec_id,
        proposed_day=day,
        proposed_start_time=parse_time(start_time_str) or parse_time("10:00"),
        proposed_end_time=parse_time(end_time_str) or parse_time("11:30"),
        proposed_room_id=room.id,
        requested_by_role=effective_role,
        requested_by_name=session.get("username") or "Student Mayor",
        reason=f"[Room Booking Request] {reason} for room {room.room_code}",
        status="PENDING_FACULTY" if effective_role in ("STUDENT", "STDN_MYR") else "PENDING_CHAIR",
    )
    db.session.add(req)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Room reservation request for {room.room_code} submitted successfully.",
        "data": req.to_dict()
    }), 201


@reschedule_bp.route("/requests/pending-summary", methods=["GET"])
def get_pending_requests_summary():
    """
    GET /api/requests/pending-summary
    Returns counts of pending inter-department and reschedule requests for notification bell.
    """
    purge_expired_reschedule_requests()
    effective_role = normalize_role(get_effective_role())
    effective_prog = get_effective_program()
    ref_id = session.get("active_reference_id") or session.get("reference_id")

    reschedule_q = (
        RescheduleRequest.query.filter(
            RescheduleRequest.status.in_(["PENDING", "PENDING_FACULTY", "PENDING_CHAIR"])
        )
        .outerjoin(Schedule, RescheduleRequest.schedule_id == Schedule.id)
        .outerjoin(Section, RescheduleRequest.student_section_id == Section.id)
        .outerjoin(Room, RescheduleRequest.proposed_room_id == Room.id)
    )
    if effective_role == "STUDENT":
        uname = session.get("username")
        if ref_id and uname:
            reschedule_q = reschedule_q.filter(
                db.or_(
                    RescheduleRequest.student_section_id == ref_id,
                    RescheduleRequest.requested_by_name == uname
                )
            )
        elif ref_id:
            reschedule_q = reschedule_q.filter(RescheduleRequest.student_section_id == ref_id)
        elif uname:
            reschedule_q = reschedule_q.filter(RescheduleRequest.requested_by_name == uname)
    elif effective_role == "FACULTY":
        fac = db.session.get(Faculty, ref_id) if ref_id else None
        fac_prog = fac.program if fac else effective_prog
        uname = session.get("username")
        conditions = []
        if ref_id:
            conditions.append(Schedule.faculty_id == ref_id)
        if fac_prog:
            conditions.append(
                db.and_(
                    RescheduleRequest.schedule_id.is_(None),
                    db.or_(
                        Section.program == fac_prog,
                        Room.department == fac_prog,
                    ),
                )
            )
        if uname:
            conditions.append(RescheduleRequest.requested_by_name == uname)
        if conditions:
            reschedule_q = reschedule_q.filter(db.or_(*conditions))
    elif effective_role == "CHAIR":
        if effective_prog and effective_prog != "ALL":
            reschedule_q = reschedule_q.filter(
                db.or_(
                    Section.program == effective_prog,
                    Room.department == effective_prog,
                    Schedule.faculty.has(program=effective_prog),
                    RescheduleRequest.requested_by_name == session.get("username"),
                )
            )

    reschedule_count = reschedule_q.count()

    interdept_q = InterDepartmentRequest.query.filter_by(status="PENDING_APPROVAL")
    if effective_role == "CHAIR" and effective_prog and effective_prog != "ALL":
        interdept_q = interdept_q.filter(
            db.or_(
                InterDepartmentRequest.target_department == effective_prog,
                InterDepartmentRequest.source_department == effective_prog,
                InterDepartmentRequest.target_department == "ADMIN",
            )
        )
    elif effective_role not in ("CHAIR", "ADMIN", "DEAN"):
        interdept_q = interdept_q.filter(InterDepartmentRequest.id == -1)

    interdept_count = interdept_q.count()
    total = reschedule_count + interdept_count

    return jsonify({
        "status": "success",
        "total_pending": total,
        "reschedule_count": reschedule_count,
        "interdept_count": interdept_count,
    }), 200
