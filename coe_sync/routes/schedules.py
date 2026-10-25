"""COE SYNC 2026 - Schedule & Conflict Management Routes

Endpoints:
- GET  /api/schedules: List schedules with role-based filtering (Student/Faculty row-level security)
- POST /api/conflicts/check: Pre-flight conflict check & 3-step recommendation suggestions
- POST /api/schedules: Create a new schedule slot (atomic transaction + conflict validation)
- PUT  /api/schedules/<id>: Update schedule (blocked if PUBLISHED)
- DELETE /api/schedules/<id>: Delete schedule and log audit entry
- PATCH /api/schedules/<id>/status: Publish / unpublish schedule
"""

from flask import Blueprint, request, jsonify, session
from models import (
    db,
    Schedule,
    Subject,
    Section,
    Faculty,
    Room,
    FacultyAvailability,
    AuditLog,
)
from services.conflict_detector import (
    validate_schedule_slot,
    find_alternatives,
    parse_time,
    time_to_minutes,
    minutes_to_time,
    times_overlap,
)
from services.scheduler import run_smart_scheduler, normalize_prog_code
from routes.auth import (
    login_required,
    require_roles,
    get_effective_role,
    get_effective_reference_id,
    get_effective_program,
)

schedules_bp = Blueprint("schedules", __name__)


def recalculate_faculty_units(faculty_id: int):
    """Sync Faculty.current_units with the sum of units across all their schedules."""
    faculty = db.session.get(Faculty, faculty_id)
    if faculty:
        total = (
            db.session.query(db.func.sum(Subject.units))
            .join(Schedule, Schedule.subject_id == Subject.id)
            .filter(Schedule.faculty_id == faculty_id)
            .scalar()
            or 0
        )
        faculty.current_units = total


@schedules_bp.route("/schedules", methods=["GET"])
@login_required
def get_schedules():
    """
    GET /api/schedules
    Query filters: ?section_id=, ?faculty_id=, ?room_id=, ?day=, ?status=, ?program=, ?year_level=, ?search=
    Row-level security:
      - Role STUDENT: Forced to filter by session['reference_id'] (section_id) and status=PUBLISHED only.
                      Attempts to view other sections return HTTP 403.
      - Role FACULTY: Forced to filter by session['reference_id'] (faculty_id).
                      Attempts to view other faculty assignments return HTTP 403.
      - Role CHAIR / ADMIN: Allowed to view all schedules
    """
    query = Schedule.query

    effective_role = get_effective_role()
    effective_ref_id = get_effective_reference_id()

    # Enforce row-level security
    if effective_role == "STUDENT":
        auth_role = session.get("role")
        is_impersonating = auth_role in ("CHAIR", "ADMIN") and session.get("impersonated_role") == "STUDENT"
        req_section_id = request.args.get("section_id", type=int)
        target_section_id = req_section_id or effective_ref_id

        if not is_impersonating:
            # Genuine students can only view approved PUBLISHED classes
            query = query.filter(Schedule.status == "PUBLISHED")
            if effective_ref_id:
                if req_section_id and req_section_id != effective_ref_id:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "error": "Unauthorized: Cross-section schedule viewing is forbidden for student accounts.",
                            }
                        ),
                        403,
                    )
                query = query.filter(Schedule.section_id == effective_ref_id)
            elif req_section_id:
                query = query.filter(Schedule.section_id == req_section_id)
            else:
                query = query.filter(Schedule.id == -1)
        else:
            # Chair/Admin impersonating student: view selected section or default section
            if target_section_id:
                query = query.filter(Schedule.section_id == target_section_id)
            else:
                query = query.filter(Schedule.id == -1)
    elif effective_role == "FACULTY":
        auth_role = session.get("role")
        is_impersonating = auth_role in ("CHAIR", "ADMIN") and session.get("impersonated_role") == "FACULTY"
        req_faculty_id = request.args.get("faculty_id", type=int)
        target_faculty_id = req_faculty_id or effective_ref_id

        if not is_impersonating:
            if effective_ref_id:
                if req_faculty_id and req_faculty_id != effective_ref_id:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "error": "Unauthorized: Access restricted to your own instructional assignments.",
                            }
                        ),
                        403,
                    )
                query = query.filter(Schedule.faculty_id == effective_ref_id)
            elif req_faculty_id:
                query = query.filter(Schedule.faculty_id == req_faculty_id)
            else:
                query = query.filter(Schedule.id == -1)
        else:
            # Chair/Admin impersonating faculty: view selected instructor or default
            if target_faculty_id:
                query = query.filter(Schedule.faculty_id == target_faculty_id)
            else:
                query = query.filter(Schedule.id == -1)
    else:
        # Standard administrative query filters
        section_id = request.args.get("section_id", type=int)
        faculty_id = request.args.get("faculty_id", type=int)
        room_id = request.args.get("room_id", type=int)
        day = request.args.get("day", type=str)
        status = request.args.get("status", type=str)
        program = request.args.get("program", type=str)
        year_level = request.args.get("year_level", type=int)
        search = request.args.get("search", type=str)

        effective_prog = get_effective_program()
        if effective_role == "CHAIR" and effective_prog:
            program = effective_prog

        if section_id:
            query = query.filter(Schedule.section_id == section_id)
        if faculty_id:
            query = query.filter(Schedule.faculty_id == faculty_id)
        if room_id:
            query = query.filter(Schedule.room_id == room_id)
        if day:
            query = query.filter(Schedule.day_of_week == day.strip().upper())
        if status and status.strip().upper() in ("DRAFT", "PUBLISHED"):
            query = query.filter(Schedule.status == status.strip().upper())
        if program or year_level:
            query = query.join(Section, Schedule.section_id == Section.id)
            if program and program.strip().upper() != "ALL":
                norm_p = normalize_prog_code(program)
                query = query.filter(
                    db.or_(
                        Section.program == norm_p,
                        Section.program.ilike(f"%{program.strip()}%"),
                        Section.program.ilike(f"%{norm_p}%"),
                    )
                )
            if year_level:
                query = query.filter(Section.year_level == year_level)
        if search:
            search_str = f"%{search.strip()}%"
            query = query.join(Subject, Schedule.subject_id == Subject.id).filter(
                (Subject.code.ilike(search_str)) | (Subject.title.ilike(search_str))
            )

    semester = request.args.get("semester", type=int)
    if semester:
        query = query.filter(Schedule.subject.has(Subject.semester == semester))

    schedules = query.order_by(
        Schedule.day_of_week.asc(), Schedule.start_time.asc()
    ).all()

    return (
        jsonify(
            {
                "status": "success",
                "count": len(schedules),
                "data": [s.to_dict() for s in schedules],
            }
        ),
        200,
    )


@schedules_bp.route("/conflicts/check", methods=["POST"])
@login_required
def check_conflicts():
    """
    POST /api/conflicts/check
    Pre-flight validation check for UI without writing to the database.
    Payload: { subject_id, section_id, faculty_id, room_id, day_of_week, start_time, end_time }
    Returns: { "valid": bool, "conflicts": [...], "suggestions": [...] }
    """
    payload = request.get_json(silent=True) or {}
    exclude_id = request.args.get(
        "exclude_id", type=int
    ) or payload.get("exclude_schedule_id")

    # Temporal inversion check
    try:
        st = parse_time(payload.get("start_time"))
        et = parse_time(payload.get("end_time"))
        if time_to_minutes(st) >= time_to_minutes(et):
            return (
                jsonify(
                    {
                        "valid": False,
                        "conflicts": [
                            "Invalid time slot: start_time must be strictly earlier than end_time."
                        ],
                        "suggestions": [],
                    }
                ),
                200,
            )
    except Exception as e:
        return (
            jsonify(
                {
                    "valid": False,
                    "conflicts": [f"Invalid time format: {str(e)}"],
                    "suggestions": [],
                }
            ),
            200,
        )

    validation_result = validate_schedule_slot(
        payload, exclude_schedule_id=exclude_id
    )

    suggestions = []
    if not validation_result["valid"]:
        suggestions = find_alternatives(payload, exclude_schedule_id=exclude_id)

    return (
        jsonify(
            {
                "valid": validation_result["valid"],
                "conflicts": validation_result["conflicts"],
                "suggestions": suggestions,
            }
        ),
        200,
    )


@schedules_bp.route("/schedules", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def create_schedule():
    """
    POST /api/schedules
    Protected endpoint: CHAIR and ADMIN only.
    Validates Hard Constraints; returns HTTP 409 with alternatives on conflict.
    """
    payload = request.get_json(silent=True) or {}

    # Validate required parameters (room_id and faculty_id can be null/empty for unassigned / TBA)
    required_fields = [
        "subject_id",
        "section_id",
        "day_of_week",
        "start_time",
        "end_time",
    ]
    missing = [f for f in required_fields if payload.get(f) is None]
    if missing:
        return (
            jsonify(
                {"error": f"Missing required fields: {', '.join(missing)}"}
            ),
            400,
        )

    # Normalize room_id and faculty_id
    raw_room_id = payload.get("room_id")
    room_id = int(raw_room_id) if (raw_room_id is not None and str(raw_room_id).isdigit() and int(raw_room_id) > 0) else None
    raw_fac_id = payload.get("faculty_id")
    faculty_id = int(raw_fac_id) if (raw_fac_id is not None and str(raw_fac_id).isdigit() and int(raw_fac_id) > 0) else None

    # Validate temporal ordering
    try:
        st = parse_time(payload["start_time"])
        et = parse_time(payload["end_time"])
        if time_to_minutes(st) >= time_to_minutes(et):
            return (
                jsonify(
                    {
                        "error": "Invalid time slot: start_time must be strictly earlier than end_time."
                    }
                ),
                400,
            )
    except Exception as e:
        return jsonify({"error": f"Invalid time format: {str(e)}"}), 400

    # Sub-group handling (G1/G2 or split into both)
    split_lab_groups = bool(payload.get("split_lab_groups", False))
    raw_sub_group = payload.get("sub_group")
    sub_group = str(raw_sub_group).strip().upper() if raw_sub_group in ("G1", "G2") else None

    # Execute Hard Constraint validation
    validation = validate_schedule_slot(payload)
    if not validation["valid"]:
        suggestions = find_alternatives(payload)
        return (
            jsonify(
                {
                    "error": "Schedule conflict detected",
                    "conflicts": validation["conflicts"],
                    "suggestions": suggestions,
                }
            ),
            409,
        )

    # Atomic creation transaction
    try:
        status_val = payload.get("status", "DRAFT").strip().upper()
        if status_val not in {"DRAFT", "PUBLISHED"}:
            status_val = "DRAFT"

        subj = db.session.get(Subject, int(payload["subject_id"]))
        split_pref = payload.get("split_preference")
        if not split_pref:
            split_pref = getattr(subj, "split_preference", "1.5_HOUR_SPLIT") if subj else "1.5_HOUR_SPLIT"

        created_schedules = []
        target_subgroups = ["G1", "G2"] if split_lab_groups else [sub_group]

        for grp in target_subgroups:
            new_schedule = Schedule(
                subject_id=int(payload["subject_id"]),
                section_id=int(payload["section_id"]),
                faculty_id=faculty_id,
                room_id=room_id,
                day_of_week=payload["day_of_week"].strip().upper(),
                start_time=st,
                end_time=et,
                status=status_val,
                split_preference=split_pref,
                sub_group=grp,
            )
            db.session.add(new_schedule)
            created_schedules.append(new_schedule)

        db.session.flush()

        # Update faculty current units if faculty was assigned
        if faculty_id:
            recalculate_faculty_units(faculty_id)

        # Audit Log
        user_id = session.get("user_id")
        audit = AuditLog(
            user_id=user_id,
            action="SCHEDULE_CREATED",
            details=(
                f"Created schedule(s) for {created_schedules[0].subject.code} "
                f"({created_schedules[0].section.name}) with {created_schedules[0].faculty.name} "
                f"on {created_schedules[0].day_of_week} {st.strftime('%H:%M')}-{et.strftime('%H:%M')}."
            ),
        )
        db.session.add(audit)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Schedule slot created successfully.",
                    "data": created_schedules[0].to_dict(),
                    "schedules": [s.to_dict() for s in created_schedules],
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": f"Failed to persist schedule: {str(e)}",
                }
            ),
            500,
        )


@schedules_bp.route("/schedules/<int:schedule_id>", methods=["PUT"])
@require_roles("CHAIR", "ADMIN")
def update_schedule(schedule_id: int):
    """
    PUT /api/schedules/<id>
    Protected endpoint: CHAIR and ADMIN only.
    Checks if schedule is locked (PUBLISHED).
    """
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": f"Schedule #{schedule_id} not found."}), 404

    # Enforce locked schedule rule
    if schedule.status == "PUBLISHED":
        return (
            jsonify(
                {
                    "error": "Must unpublish before editing",
                    "hint": "Set status to DRAFT before modifying an approved timetable.",
                }
            ),
            400,
        )

    payload = request.get_json(silent=True) or {}

    # Merge existing fields with incoming updates
    merged_data = {
        "subject_id": payload.get("subject_id", schedule.subject_id),
        "section_id": payload.get("section_id", schedule.section_id),
        "faculty_id": payload.get("faculty_id", schedule.faculty_id),
        "room_id": payload.get("room_id", schedule.room_id),
        "day_of_week": payload.get("day_of_week", schedule.day_of_week),
        "start_time": payload.get("start_time", schedule.start_time),
        "end_time": payload.get("end_time", schedule.end_time),
    }

    try:
        st = parse_time(merged_data["start_time"])
        et = parse_time(merged_data["end_time"])
        if time_to_minutes(st) >= time_to_minutes(et):
            return (
                jsonify(
                    {
                        "error": "Invalid time slot: start_time must be strictly earlier than end_time."
                    }
                ),
                400,
            )
    except Exception as e:
        return jsonify({"error": f"Invalid time format: {str(e)}"}), 400

    merged_data["start_time"] = st
    merged_data["end_time"] = et

    # Run conflict validation excluding this schedule
    validation = validate_schedule_slot(
        merged_data, exclude_schedule_id=schedule_id
    )
    if not validation["valid"]:
        suggestions = find_alternatives(
            merged_data, exclude_schedule_id=schedule_id
        )
        return (
            jsonify(
                {
                    "error": "Schedule conflict detected",
                    "conflicts": validation["conflicts"],
                    "suggestions": suggestions,
                }
            ),
            409,
        )

    old_faculty_id = schedule.faculty_id

    # Update attributes
    schedule.subject_id = int(merged_data["subject_id"])
    schedule.section_id = int(merged_data["section_id"])
    raw_fac = merged_data.get("faculty_id")
    schedule.faculty_id = int(raw_fac) if (raw_fac is not None and str(raw_fac).isdigit() and int(raw_fac) > 0) else None
    raw_rm = merged_data.get("room_id")
    schedule.room_id = int(raw_rm) if (raw_rm is not None and str(raw_rm).isdigit() and int(raw_rm) > 0) else None
    schedule.day_of_week = str(merged_data["day_of_week"]).strip().upper()
    schedule.start_time = st
    schedule.end_time = et

    if "status" in payload:
        new_status = payload["status"].strip().upper()
        if new_status in {"DRAFT", "PUBLISHED"}:
            schedule.status = new_status

    if "split_preference" in payload:
        new_split = str(payload["split_preference"]).strip().upper()
        if new_split in {"3_HOUR_BLOCK", "1.5_HOUR_SPLIT"}:
            schedule.split_preference = new_split

    db.session.flush()

    # Recalculate workloads
    if schedule.faculty_id:
        recalculate_faculty_units(schedule.faculty_id)
    if old_faculty_id and old_faculty_id != schedule.faculty_id:
        recalculate_faculty_units(old_faculty_id)

    # Log audit
    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SCHEDULE_UPDATED",
        details=f"Updated schedule #{schedule.id} ({schedule.subject.code} for {schedule.section.name}).",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": "Schedule updated successfully.",
                "data": schedule.to_dict(),
            }
        ),
        200,
    )


@schedules_bp.route("/schedules/<int:schedule_id>/drag-move", methods=["POST"])
@schedules_bp.route("/schedules/<int:schedule_id>/move-slot", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def move_schedule_slot(schedule_id: int):
    """
    Drag-and-drop schedule mover:
    Moves the dragged schedule to the target day and start time.
    If it overlaps an existing class on that day (or was dropped onto another class),
    the class below it is adjusted to start at the end of the moved class.
    Returns the adjustment details and warnings so the user can review or ignore them.
    """
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": f"Schedule #{schedule_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    target_day = str(data.get("day_of_week") or data.get("target_day") or schedule.day_of_week).strip().upper()
    target_start_str = data.get("start_time") or data.get("target_start_time")
    target_end_str = data.get("end_time") or data.get("target_end_time")
    target_schedule_id = data.get("target_schedule_id")

    orig_st = parse_time(schedule.start_time)
    orig_et = parse_time(schedule.end_time)
    dur_mins = time_to_minutes(orig_et) - time_to_minutes(orig_st)
    if dur_mins <= 0:
        dur_mins = 90

    if target_schedule_id:
        target_sched = db.session.get(Schedule, int(target_schedule_id))
        if target_sched:
            target_day = target_sched.day_of_week
            new_st = parse_time(target_sched.start_time)
        elif target_start_str:
            new_st = parse_time(target_start_str)
        else:
            new_st = orig_st
    elif target_start_str:
        new_st = parse_time(target_start_str)
    else:
        new_st = orig_st

    if target_end_str:
        new_et = parse_time(target_end_str)
    else:
        new_et = minutes_to_time(time_to_minutes(new_st) + dur_mins)

    # Find overlapping schedules on the target day for this section or room or faculty
    all_day_scheds = Schedule.query.filter(
        Schedule.id != schedule.id,
        Schedule.day_of_week == target_day,
    ).all()

    colliding = []
    for other in all_day_scheds:
        is_explicit_target = bool(target_schedule_id and other.id == int(target_schedule_id))
        other_st = parse_time(other.start_time)
        other_et = parse_time(other.end_time)
        if is_explicit_target or times_overlap(new_st, new_et, other_st, other_et):
            if (
                is_explicit_target
                or other.section_id == schedule.section_id
                or other.room_id == schedule.room_id
                or other.faculty_id == schedule.faculty_id
            ):
                colliding.append(other)

    displaced_info = []
    # Auto-adjust overlapping subjects to start at the end of the dragged class
    if colliding:
        colliding.sort(key=lambda s: time_to_minutes(parse_time(s.start_time)))
        cursor_mins = time_to_minutes(new_et)
        for other in colliding:
            other_orig_st = parse_time(other.start_time)
            other_orig_et = parse_time(other.end_time)
            other_dur = time_to_minutes(other_orig_et) - time_to_minutes(other_orig_st)
            if other_dur <= 0:
                other_dur = 90

            adj_st = minutes_to_time(cursor_mins)
            adj_et = minutes_to_time(cursor_mins + other_dur)
            cursor_mins += other_dur

            old_slot = f"{other.day_of_week} {other_orig_st.strftime('%H:%M')}–{other_orig_et.strftime('%H:%M')}"
            new_slot = f"{other.day_of_week} {adj_st.strftime('%H:%M')}–{adj_et.strftime('%H:%M')}"

            other.start_time = adj_st
            other.end_time = adj_et

            sub_name = other.subject.code if other.subject else f"Subject #{other.subject_id}"
            displaced_info.append({
                "id": other.id,
                "subject": sub_name,
                "old_slot": old_slot,
                "new_slot": new_slot,
                "message": f"Class '{sub_name}' was auto-adjusted from {old_slot} to {new_slot} (moved to the end of {schedule.subject.code if schedule.subject else 'dragged class'}).",
            })

    # Update dragged schedule
    schedule.day_of_week = target_day
    schedule.start_time = new_st
    schedule.end_time = new_et

    # Audit log
    dragged_code = schedule.subject.code if schedule.subject else f"Schedule #{schedule.id}"
    dragged_slot = f"{target_day} {new_st.strftime('%H:%M')}–{new_et.strftime('%H:%M')}"
    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SCHEDULE_DRAG_MOVED",
        details=f"Moved {dragged_code} to {dragged_slot}. Auto-adjusted {len(displaced_info)} overlapping class(es).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Moved {dragged_code} to {dragged_slot}.",
        "dragged_schedule": schedule.to_dict(),
        "displaced_adjustments": displaced_info,
        "warnings": [d["message"] for d in displaced_info],
    }), 200


@schedules_bp.route("/schedules/<int:schedule_id>", methods=["DELETE"])
@require_roles("CHAIR", "ADMIN")
def delete_schedule(schedule_id: int):
    """
    DELETE /api/schedules/<id>
    Protected endpoint: CHAIR and ADMIN only.
    """
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": f"Schedule #{schedule_id} not found."}), 404

    faculty_id = schedule.faculty_id
    sched_desc = (
        f"Schedule #{schedule.id}: {schedule.subject.code} "
        f"({schedule.section.name}) with {schedule.faculty.name}"
    )

    db.session.delete(schedule)
    db.session.flush()

    recalculate_faculty_units(faculty_id)

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SCHEDULE_DELETED",
        details=f"Deleted {sched_desc}.",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": "Schedule slot deleted successfully.",
            }
        ),
        200,
    )


@schedules_bp.route("/schedules/<int:schedule_id>/status", methods=["PATCH"])
@require_roles("CHAIR", "ADMIN")
def update_schedule_status(schedule_id: int):
    """
    PATCH /api/schedules/<id>/status
    Toggle or set DRAFT / PUBLISHED status.
    Payload: { "status": "DRAFT" | "PUBLISHED" }
    """
    schedule = db.session.get(Schedule, schedule_id)
    if not schedule:
        return jsonify({"error": f"Schedule #{schedule_id} not found."}), 404

    payload = request.get_json(silent=True) or {}
    new_status = payload.get("status", "").strip().upper()
    if new_status not in {"DRAFT", "PUBLISHED"}:
        # Toggle if no valid status passed
        new_status = "PUBLISHED" if schedule.status == "DRAFT" else "DRAFT"

    schedule.status = new_status
    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SCHEDULE_STATUS_CHANGED",
        details=f"Schedule #{schedule.id} status changed to {new_status}.",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Schedule status updated to {new_status}.",
                "data": schedule.to_dict(),
            }
        ),
        200,
    )


@schedules_bp.route("/scheduler/generate", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def api_smart_generate_schedule():
    """
    POST /api/scheduler/generate
    Smart Schedule Generator with Program, Year Level, Semester, Section, Room, Faculty, and Preference options.
    """
    payload = request.get_json(silent=True) or {}
    user_id = session.get("user_id")

    # Enforce Program Chair department scope locking
    effective_role = get_effective_role()
    effective_prog = get_effective_program()
    if effective_role in ("CHAIR", "PROG_CHA") and effective_prog:
        payload["program"] = effective_prog

    result = run_smart_scheduler(payload, user_id=user_id)
    if result.get("status") == "error":
        msg = str(result.get("message", "")).lower()
        status_code = 409 if ("conflict" in msg or "impossible" in msg) else 400
        return jsonify(result), status_code
    return jsonify(result), 200


@schedules_bp.route("/schedules/generate-draft", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def generate_draft_schedules():
    """
    POST /api/schedules/generate-draft
    Intelligent heuristic draft schedule generation for curriculum offerings.
    Places unassigned section-subject pairs into conflict-free draft slots.
    Returns: { "placed_count": int, "unplaced_items": list, "quality_score": int }
    """
    sections = Section.query.order_by(Section.id.asc()).all()
    # Auto-generate draft schedules for Major subjects only (Minors are scheduled manually)
    subjects = [s for s in Subject.query.order_by(Subject.id.asc()).all() if s.classification == "MAJOR"]
    faculty_list = Faculty.query.all()
    rooms = Room.query.filter_by(is_available=True).all()

    current_schedules = list(Schedule.query.all())
    blackouts = FacultyAvailability.query.filter_by(is_preferred=False).all()
    faculty_units_map = {f.id: (f.current_units or 0) for f in faculty_list}

    placed = []
    unplaced = []

    candidate_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    candidate_slots = [
        ("08:00", "09:30"),
        ("09:30", "11:00"),
        ("11:00", "12:30"),
        ("13:00", "14:30"),
        ("14:30", "16:00"),
        ("16:00", "17:30"),
    ]

    # Pre-parse candidate slots once
    parsed_slots = [
        (idx, day, parse_time(st_str), parse_time(et_str))
        for day in candidate_days
        for idx, (st_str, et_str) in enumerate(candidate_slots)
    ]

    # Pre-populate O(1) busy sets
    busy_sections = set()
    busy_rooms = set()
    busy_faculty = set()

    for s in current_schedules:
        for idx, day, st, et in parsed_slots:
            if s.day_of_week == day and times_overlap(s.start_time, s.end_time, st, et):
                busy_sections.add((s.section_id, day, idx))
                busy_rooms.add((s.room_id, day, idx))
                busy_faculty.add((s.faculty_id, day, idx))

    blackout_faculty = set()
    for b in blackouts:
        for idx, day, st, et in parsed_slots:
            if b.day_of_week == day and times_overlap(b.start_time, b.end_time, st, et):
                blackout_faculty.add((b.faculty_id, day, idx))

    for sec in sections:
        # Match curriculum: only Major subjects corresponding to this section's program and year level
        sec_p = normalize_prog_code(sec.program)
        sec_subjects = [
            sub
            for sub in subjects
            if sub.classification == "MAJOR"
            and (
                not sub.program
                or not sec.program
                or normalize_prog_code(sub.program) == sec_p
                or normalize_prog_code(sub.program) in ("GEN", "ALL", "COMMON", "COE")
            )
            and (
                not sub.year_level
                or not sec.year_level
                or sub.year_level == sec.year_level
            )
        ]

        for sub in sec_subjects:
            # Check if this section already has this subject scheduled
            if any(s.section_id == sec.id and s.subject_id == sub.id for s in current_schedules):
                continue

            # Find matching candidate rooms
            valid_rooms = [
                r for r in rooms
                if (sub.subject_type != "LAB" or r.room_type == "LAB")
            ]
            if not valid_rooms:
                unplaced.append({
                    "section": sec.name,
                    "subject": sub.code,
                    "reason": f"No available {sub.subject_type} room",
                })
                continue

            # Find candidate faculty with matching program and remaining unit capacity
            valid_fac = [
                f for f in faculty_list
                if (
                    not f.program
                    or not sec.program
                    or normalize_prog_code(f.program) == sec_p
                    or normalize_prog_code(f.program) in ("GEN", "ALL", "COMMON", "COE")
                )
                and (faculty_units_map.get(f.id, 0) + sub.units <= f.max_units)
            ]
            if not valid_fac:
                valid_fac = [
                    f for f in faculty_list
                    if (
                        not f.program
                        or not sec.program
                        or normalize_prog_code(f.program) == sec_p
                        or normalize_prog_code(f.program) in ("GEN", "ALL", "COMMON", "COE")
                    )
                ]
            if not valid_fac:
                valid_fac = faculty_list  # Fallback to avoid deadlocks

            slot_assigned = False

            # Search across pre-parsed days and time slots
            for idx, day, st, et in parsed_slots:
                if (sec.id, day, idx) in busy_sections:
                    continue

                free_room = next((r for r in valid_rooms if (r.id, day, idx) not in busy_rooms), None)
                if not free_room:
                    continue

                free_fac = next((f for f in valid_fac if (f.id, day, idx) not in busy_faculty and (f.id, day, idx) not in blackout_faculty), None)
                if not free_fac:
                    continue

                new_sched = Schedule(
                    subject_id=sub.id,
                    section_id=sec.id,
                    faculty_id=free_fac.id,
                    room_id=free_room.id,
                    day_of_week=day,
                    start_time=st,
                    end_time=et,
                    status="DRAFT",
                )
                db.session.add(new_sched)
                current_schedules.append(new_sched)
                busy_sections.add((sec.id, day, idx))
                busy_rooms.add((free_room.id, day, idx))
                busy_faculty.add((free_fac.id, day, idx))
                faculty_units_map[free_fac.id] = faculty_units_map.get(free_fac.id, 0) + sub.units
                placed.append(new_sched)
                slot_assigned = True
                break

            if not slot_assigned:
                unplaced.append({
                    "section": sec.name,
                    "subject": sub.code,
                    "reason": "All matching time windows collide with existing schedules",
                })

    if placed:
        audit = AuditLog(
            user_id=session.get("user_id"),
            action="DRAFT_SCHEDULE_GENERATED",
            details=f"Generated {len(placed)} draft schedule slots. Unplaced offerings: {len(unplaced)}.",
        )
        db.session.add(audit)
        db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Draft generation complete. {len(placed)} slots created, {len(unplaced)} unplaced.",
                "placed_count": len(placed),
                "unplaced_items": unplaced,
                "unplaced_count": len(unplaced),
                "total_schedules": Schedule.query.count(),
            }
        ),
        200,
    )


@schedules_bp.route("/schedules/publish-all", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def publish_all_schedules():
    """
    POST /api/schedules/publish-all
    Validates that zero hard conflicts exist before publishing DRAFT schedules.
    If hard conflicts exist, returns HTTP 409 with details.
    Supports optional scope filtering by 'program' and 'section_id'.
    """
    from services.conflict_detector import times_overlap

    data = request.get_json(silent=True) or {}
    program = str(data.get("program") or request.args.get("program") or "").strip()
    section_id = data.get("section_id") or request.args.get("section_id", type=int)

    all_schedules = Schedule.query.all()
    conflicts = []

    # Check pairwise hard conflicts across the timetable
    n = len(all_schedules)
    for i in range(n):
        s1 = all_schedules[i]
        for j in range(i + 1, n):
            s2 = all_schedules[j]
            if s1.day_of_week == s2.day_of_week:
                if times_overlap(s1.start_time, s1.end_time, s2.start_time, s2.end_time):
                    if s1.room_id == s2.room_id:
                        conflicts.append(
                            f"Room collision: {s1.room.room_code} double-booked on {s1.day_of_week} "
                            f"between {s1.subject.code} ({s1.section.name}) and {s2.subject.code} ({s2.section.name})."
                        )
                    if s1.faculty_id == s2.faculty_id:
                        conflicts.append(
                            f"Faculty collision: {s1.faculty.name} assigned simultaneously on {s1.day_of_week}."
                        )
                    if s1.section_id == s2.section_id:
                        conflicts.append(
                            f"Section overlap: {s1.section.name} assigned to two classes simultaneously on {s1.day_of_week}."
                        )

    # Resolve target drafts based on scope
    draft_query = Schedule.query.filter_by(status="DRAFT")
    if section_id:
        draft_query = draft_query.filter(Schedule.section_id == int(section_id))
    elif program and program.upper() != "ALL":
        norm_p = normalize_prog_code(program)
        draft_query = draft_query.join(Section, Schedule.section_id == Section.id).filter(
            db.or_(Section.program == norm_p, Section.program == program)
        )
    drafts = draft_query.all()

    if conflicts and len(drafts) > 0:
        return (
            jsonify(
                {
                    "error": "Cannot publish: Unresolved hard conflicts exist in the timetable.",
                    "conflict_count": len(conflicts),
                    "conflicts": conflicts,
                    "hint": "Resolve all collisions in the Conflict Radar before publishing.",
                }
            ),
            409,
        )

    count = len(drafts)
    for d in drafts:
        d.status = "PUBLISHED"

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="ALL_SCHEDULES_PUBLISHED",
        details=f"Batch-published {count} schedule(s) for scope (program='{program}', section_id={section_id}). Timetable locked.",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Successfully published {count} schedule(s). The weekly timetable is now live and locked.",
                "published_count": count,
            }
        ),
        200,
    )


@schedules_bp.route("/schedules/unpublish-all", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def unpublish_all_schedules():
    """
    POST /api/schedules/unpublish-all
    Reverts PUBLISHED schedules to DRAFT status for administrative modification.
    Supports optional scope filtering by 'program' and 'section_id'.
    """
    data = request.get_json(silent=True) or {}
    program = str(data.get("program") or request.args.get("program") or "").strip()
    section_id = data.get("section_id") or request.args.get("section_id", type=int)

    pub_query = Schedule.query.filter_by(status="PUBLISHED")
    if section_id:
        pub_query = pub_query.filter(Schedule.section_id == int(section_id))
    elif program and program.upper() != "ALL":
        norm_p = normalize_prog_code(program)
        pub_query = pub_query.join(Section, Schedule.section_id == Section.id).filter(
            db.or_(Section.program == norm_p, Section.program == program)
        )
    published = pub_query.all()
    count = len(published)
    for p in published:
        p.status = "DRAFT"

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="ALL_SCHEDULES_UNPUBLISHED",
        details=f"Batch-reverted {count} schedule(s) to DRAFT status for editing.",
    )
    db.session.add(audit)
    db.session.commit()

    return (
        jsonify(
            {
                "status": "success",
                "message": f"Reverted {count} schedule(s) to DRAFT status for editing.",
                "reverted_count": count,
            }
        ),
        200,
    )


