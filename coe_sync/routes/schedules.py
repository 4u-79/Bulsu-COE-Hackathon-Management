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
    times_overlap,
)
from services.scheduler import run_smart_scheduler, normalize_prog_code
from routes.auth import (
    login_required,
    require_roles,
    get_effective_role,
    get_effective_reference_id,
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
        # Students can only view approved PUBLISHED classes
        query = query.filter(Schedule.status == "PUBLISHED")
        req_section_id = request.args.get("section_id", type=int)
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
    elif effective_role == "FACULTY":
        req_faculty_id = request.args.get("faculty_id", type=int)
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
        # Standard administrative query filters
        section_id = request.args.get("section_id", type=int)
        faculty_id = request.args.get("faculty_id", type=int)
        room_id = request.args.get("room_id", type=int)
        day = request.args.get("day", type=str)
        status = request.args.get("status", type=str)
        program = request.args.get("program", type=str)
        year_level = request.args.get("year_level", type=int)
        search = request.args.get("search", type=str)

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

    # Validate required parameters
    required_fields = [
        "subject_id",
        "section_id",
        "faculty_id",
        "room_id",
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

        new_schedule = Schedule(
            subject_id=int(payload["subject_id"]),
            section_id=int(payload["section_id"]),
            faculty_id=int(payload["faculty_id"]),
            room_id=int(payload["room_id"]),
            day_of_week=payload["day_of_week"].strip().upper(),
            start_time=st,
            end_time=et,
            status=status_val,
            split_preference=split_pref,
        )
        db.session.add(new_schedule)
        db.session.flush()

        # Update faculty current units
        recalculate_faculty_units(new_schedule.faculty_id)

        # Audit Log
        user_id = session.get("user_id")
        audit = AuditLog(
            user_id=user_id,
            action="SCHEDULE_CREATED",
            details=(
                f"Created schedule #{new_schedule.id}: {new_schedule.subject.code} "
                f"for {new_schedule.section.name} with {new_schedule.faculty.name} "
                f"in {new_schedule.room.room_code} on {new_schedule.day_of_week} "
                f"{st.strftime('%H:%M')}-{et.strftime('%H:%M')}."
            ),
        )
        db.session.add(audit)
        db.session.commit()

        return (
            jsonify(
                {
                    "status": "success",
                    "message": "Schedule slot created successfully.",
                    "data": new_schedule.to_dict(),
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
    schedule.faculty_id = int(merged_data["faculty_id"])
    schedule.room_id = int(merged_data["room_id"])
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
    recalculate_faculty_units(schedule.faculty_id)
    if old_faculty_id != schedule.faculty_id:
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
    Smart Schedule Generator with Program, Year Level, Section, Room, Faculty, and Preference options.
    """
    payload = request.get_json(silent=True) or {}
    user_id = session.get("user_id")
    result = run_smart_scheduler(payload, user_id=user_id)
    status_code = 200 if result.get("status") == "success" else 400
    return jsonify(result), status_code


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
    subjects = Subject.query.order_by(Subject.id.asc()).all()
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
        # Match curriculum: only subjects corresponding to this section's program and year level
        sec_p = normalize_prog_code(sec.program)
        sec_subjects = [
            sub
            for sub in subjects
            if (
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
    Validates that zero hard conflicts exist before batch-publishing all DRAFT schedules.
    If hard conflicts exist, returns HTTP 409 with details.
    """
    from services.conflict_detector import times_overlap

    schedules = Schedule.query.all()
    conflicts = []

    # Check pairwise hard conflicts
    n = len(schedules)
    for i in range(n):
        s1 = schedules[i]
        for j in range(i + 1, n):
            s2 = schedules[j]
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

        # Room capacity is no longer checked or enforced

    if conflicts:
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

    # Publish all draft schedules
    drafts = Schedule.query.filter_by(status="DRAFT").all()
    count = len(drafts)
    for d in drafts:
        d.status = "PUBLISHED"

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="ALL_SCHEDULES_PUBLISHED",
        details=f"Batch-published {count} schedule(s). Timetable locked.",
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
    Reverts all PUBLISHED schedules to DRAFT status for administrative modification.
    """
    published = Schedule.query.filter_by(status="PUBLISHED").all()
    count = len(published)
    for p in published:
        p.status = "DRAFT"

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="ALL_SCHEDULES_UNPUBLISHED",
        details=f"Batch-reverted {count} schedule(s) to DRAFT status.",
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


@schedules_bp.route("/scheduler/generate", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def generate_smart_schedule():
    """
    POST /api/scheduler/generate
    Execute multi-criteria AI heuristic placement for batch schedule generation.
    Protected by role: CHAIR, ADMIN only.
    Payload:
    {
      "program": "BSCpE",
      "year_level": 2,
      "section_ids": [1, 2],
      "room_ids": [1, 2, 3, 4],
      "faculty_ids": "all",
      "preferences": {
        "minimize_gaps": true,
        "balance_workload": true,
        "optimize_utilization": true
      }
    }
    """
    payload = request.get_json(silent=True) or {}
    user_id = session.get("user_id")

    result = run_smart_scheduler(payload, user_id=user_id)
    if result.get("status") == "error":
        msg = str(result.get("message", "")).lower()
        status_code = 409 if ("conflict" in msg or "impossible" in msg) else 400
        return jsonify(result), status_code

    return jsonify(result), 200


