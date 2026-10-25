"""COE SYNC 2026 - Master Data Management CRUD Routes

Endpoints for Rooms, Faculty, Sections, and Subjects:
- POST   /api/rooms, PUT /api/rooms/<id>, DELETE /api/rooms/<id>
- POST   /api/faculty, PUT /api/faculty/<id>, DELETE /api/faculty/<id>
- POST   /api/sections, PUT /api/sections/<id>, DELETE /api/sections/<id>
- POST   /api/subjects, PUT /api/subjects/<id>, DELETE /api/subjects/<id>
"""

from flask import Blueprint, request, jsonify, session
from datetime import time
from models import (
    db,
    Room,
    Faculty,
    Section,
    Subject,
    AuditLog,
    FacultyAvailability,
    Schedule,
)
from routes.auth import require_roles

master_data_bp = Blueprint("master_data", __name__, url_prefix="/api")


# -----------------------------------------------------------------
# ROOMS CRUD
# -----------------------------------------------------------------
@master_data_bp.route("/rooms", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def create_room():
    """Create a new Room."""
    data = request.get_json(silent=True) or {}
    room_code = str(data.get("room_code", "")).strip()
    room_type = str(data.get("room_type", "LECTURE")).strip().upper()
    capacity = data.get("capacity")
    is_available = bool(data.get("is_available", True))

    if not room_code:
        return jsonify({"error": "Room code is required."}), 400
    if room_type not in {"LECTURE", "LAB"}:
        return jsonify({"error": "Room type must be LECTURE or LAB."}), 400
    cap_val = 40
    if capacity is not None and str(capacity).strip() != "":
        try:
            parsed_c = int(capacity)
            if parsed_c > 0:
                cap_val = parsed_c
        except (ValueError, TypeError):
            cap_val = 40

    # Check uniqueness
    if Room.query.filter_by(room_code=room_code).first():
        return jsonify({"error": f"Room code '{room_code}' already exists."}), 409

    department = str(data.get("department", "GEN")).strip().upper() or "GEN"

    room = Room(
        room_code=room_code,
        room_type=room_type,
        capacity=cap_val,
        is_available=is_available,
        department=department,
    )
    db.session.add(room)
    db.session.flush()

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="ROOM_CREATED",
        details=f"Created room {room.room_code} ({room.room_type}, capacity: {room.capacity}, dept: {room.department}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": "Room created successfully.", "data": room.to_dict()}), 201


@master_data_bp.route("/rooms/<int:room_id>", methods=["PUT"])
@require_roles("CHAIR", "ADMIN")
def update_room(room_id: int):
    """Update an existing Room."""
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"error": f"Room #{room_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    if "room_code" in data:
        code = str(data["room_code"]).strip()
        if not code:
            return jsonify({"error": "Room code cannot be empty."}), 400
        existing = Room.query.filter_by(room_code=code).first()
        if existing and existing.id != room.id:
            return jsonify({"error": f"Room code '{code}' is already taken."}), 409
        room.room_code = code

    if "room_type" in data:
        rtype = str(data["room_type"]).strip().upper()
        if rtype not in {"LECTURE", "LAB"}:
            return jsonify({"error": "Room type must be LECTURE or LAB."}), 400
        room.room_type = rtype

    if "capacity" in data:
        try:
            cap = int(data["capacity"])
            if cap <= 0:
                raise ValueError()
            room.capacity = cap
        except (ValueError, TypeError):
            return jsonify({"error": "Capacity must be greater than 0."}), 400

    if "is_available" in data:
        room.is_available = bool(data["is_available"])

    if "department" in data:
        dept = str(data["department"]).strip().upper()
        if dept:
            room.department = dept

    if "booked_by_label" in data:
        room.booked_by_label = data["booked_by_label"]

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="ROOM_UPDATED",
        details=f"Updated room #{room.id} ({room.room_code}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": "Room updated successfully.", "data": room.to_dict()}), 200


@master_data_bp.route("/rooms/<int:room_id>", methods=["DELETE"])
@require_roles("CHAIR", "ADMIN")
def delete_room(room_id: int):
    """Delete a Room."""
    room = db.session.get(Room, room_id)
    if not room:
        return jsonify({"error": f"Room #{room_id} not found."}), 404

    code = room.room_code
    db.session.delete(room)

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="ROOM_DELETED",
        details=f"Deleted room {code} (#{room_id}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": f"Room '{code}' deleted successfully."}), 200


# -----------------------------------------------------------------
# FACULTY CRUD
# -----------------------------------------------------------------
@master_data_bp.route("/faculty", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def create_faculty():
    """Create a new Faculty member."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    max_units = data.get("max_units", 21)

    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400
    try:
        max_units = int(max_units)
        if max_units <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Max units must be greater than 0."}), 400

    if Faculty.query.filter_by(email=email).first():
        return jsonify({"error": f"Email '{email}' is already registered."}), 409

    faculty = Faculty(
        name=name,
        email=email,
        max_units=max_units,
        current_units=0,
    )
    db.session.add(faculty)
    db.session.flush()

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_CREATED",
        details=f"Created faculty {faculty.name} ({faculty.email}, max units: {faculty.max_units}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": "Faculty member created successfully.", "data": faculty.to_dict()}), 201


@master_data_bp.route("/faculty/<int:faculty_id>", methods=["GET"])
@master_data_bp.route("/master/faculty/<int:faculty_id>", methods=["GET"])
def get_faculty_detail(faculty_id: int):
    """Retrieve detailed profile of a faculty member including assigned subjects and availability."""
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

    # Fetch assigned schedules & subjects
    assigned_schedules = (
        Schedule.query.filter_by(faculty_id=faculty_id)
        .order_by(Schedule.day_of_week.asc(), Schedule.start_time.asc())
        .all()
    )
    subjects_dict = {}
    total_units = 0
    for s in assigned_schedules:
        if s.subject:
            total_units += (s.subject.units or 0)
            if s.subject.id not in subjects_dict:
                subjects_dict[s.subject.id] = {
                    "id": s.subject.id,
                    "code": s.subject.code,
                    "title": s.subject.title,
                    "units": s.subject.units,
                    "type": s.subject.subject_type,
                    "sections": [s.section.name] if s.section else [],
                    "schedule_id": s.id,
                    "day_of_week": s.day_of_week,
                    "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                    "room_code": s.room.room_code if s.room else "",
                }
            else:
                if s.section and s.section.name not in subjects_dict[s.subject.id]["sections"]:
                    subjects_dict[s.subject.id]["sections"].append(s.section.name)

    # Fetch availability records
    avails = FacultyAvailability.query.filter_by(faculty_id=faculty_id).all()

    return jsonify({
        "status": "success",
        "data": {
            **faculty.to_dict(),
            "current_units": total_units or faculty.current_units,
            "assigned_subjects": list(subjects_dict.values()),
            "schedules": [s.to_dict() for s in assigned_schedules],
            "availabilities": [a.to_dict() for a in avails],
        }
    }), 200


@master_data_bp.route("/faculty/<int:faculty_id>", methods=["PUT"])
@master_data_bp.route("/master/faculty/<int:faculty_id>", methods=["PUT"])
@require_roles("CHAIR", "ADMIN", "FACULTY")
def update_faculty(faculty_id: int):
    """Update an existing Faculty member with strict self-ownership validation for FACULTY role."""
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

    effective_role = session.get("active_role") or session.get("role")
    effective_ref_id = session.get("active_reference_id") or session.get("reference_id")

    if effective_role == "FACULTY":
        if not effective_ref_id or int(effective_ref_id) != int(faculty_id):
            return jsonify({"error": "Unauthorized: You are only permitted to update your own faculty profile."}), 403

    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = str(data["name"]).strip()
        if not name:
            return jsonify({"error": "Name cannot be empty."}), 400
        faculty.name = name

    if "email" in data:
        email = str(data["email"]).strip().lower()
        if not email:
            return jsonify({"error": "Email cannot be empty."}), 400
        existing = Faculty.query.filter_by(email=email).first()
        if existing and existing.id != faculty.id:
            return jsonify({"error": f"Email '{email}' is already taken."}), 409
        faculty.email = email

    if "max_units" in data:
        try:
            m = int(data["max_units"])
            if m <= 0:
                raise ValueError()
            faculty.max_units = m
        except (ValueError, TypeError):
            return jsonify({"error": "Max units must be greater than 0."}), 400

    if "preferred_session_type" in data:
        sess_pref = str(data["preferred_session_type"]).strip().upper()
        if sess_pref in {"SPLIT", "STRAIGHT"}:
            faculty.preferred_session_type = sess_pref

    if "availabilities" in data and isinstance(data["availabilities"], list):
        # Update or set availability windows
        FacultyAvailability.query.filter_by(faculty_id=faculty_id).delete()
        for item in data["availabilities"]:
            day = (item.get("day_of_week") or "").strip().upper()
            if day in {"MON", "TUE", "WED", "THU", "FRI", "SAT"}:
                st_parts = [int(p) for p in str(item.get("start_time", "08:00")).split(":")[:2]]
                et_parts = [int(p) for p in str(item.get("end_time", "17:00")).split(":")[:2]]
                db.session.add(
                    FacultyAvailability(
                        faculty_id=faculty_id,
                        day_of_week=day,
                        start_time=time(st_parts[0], st_parts[1]),
                        end_time=time(et_parts[0], et_parts[1]),
                        is_preferred=bool(item.get("is_preferred", True)),
                    )
                )

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_UPDATED",
        details=f"Updated faculty #{faculty.id} ({faculty.name}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": "Faculty updated successfully.", "data": faculty.to_dict()}), 200


@master_data_bp.route("/faculty/<int:faculty_id>", methods=["DELETE"])
@require_roles("CHAIR", "ADMIN")
def delete_faculty(faculty_id: int):
    """Delete a Faculty member."""
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

    name = faculty.name
    db.session.delete(faculty)

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_DELETED",
        details=f"Deleted faculty {name} (#{faculty_id}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": f"Faculty '{name}' deleted successfully."}), 200


# -----------------------------------------------------------------
# SECTIONS CRUD
# -----------------------------------------------------------------
@master_data_bp.route("/sections", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def create_section():
    """Create a new Cohort Section."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    program = str(data.get("program", "BSCpE")).strip()
    year_level = data.get("year_level")
    student_count = data.get("student_count")

    if not name or not program:
        return jsonify({"error": "Section name and program are required."}), 400
    try:
        year_level = int(year_level)
        if year_level <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Year level must be a positive integer."}), 400

    sc_val = None
    if student_count is not None and str(student_count).strip() != "":
        try:
            parsed_sc = int(student_count)
            if parsed_sc > 0:
                sc_val = parsed_sc
        except (ValueError, TypeError):
            pass

    class_mayor = str(data.get("class_mayor", "")).strip() or None

    section = Section(
        name=name,
        program=program,
        year_level=year_level,
        student_count=sc_val,
        class_mayor=class_mayor,
    )
    db.session.add(section)
    db.session.flush()

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SECTION_CREATED",
        details=f"Created section {section.name} ({section.program}, Year {section.year_level}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": "Section created successfully.", "data": section.to_dict()}), 201


@master_data_bp.route("/sections/<int:section_id>", methods=["PUT"])
@require_roles("CHAIR", "ADMIN")
def update_section(section_id: int):
    """Update an existing Cohort Section."""
    section = db.session.get(Section, section_id)
    if not section:
        return jsonify({"error": f"Section #{section_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    if "name" in data:
        name = str(data["name"]).strip()
        if not name:
            return jsonify({"error": "Section name cannot be empty."}), 400
        section.name = name

    if "program" in data:
        p = str(data["program"]).strip()
        if not p:
            return jsonify({"error": "Program cannot be empty."}), 400
        section.program = p

    if "year_level" in data:
        try:
            yl = int(data["year_level"])
            if yl <= 0:
                raise ValueError()
            section.year_level = yl
        except (ValueError, TypeError):
            return jsonify({"error": "Year level must be a positive integer."}), 400

    if "class_mayor" in data:
        raw_cm = str(data["class_mayor"]).strip() if data["class_mayor"] else ""
        section.class_mayor = raw_cm if raw_cm else None

    if "student_count" in data:
        raw_sc = data["student_count"]
        if raw_sc is None or str(raw_sc).strip() == "":
            section.student_count = None
        else:
            try:
                sc = int(raw_sc)
                if sc > 0:
                    section.student_count = sc
            except (ValueError, TypeError):
                pass

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SECTION_UPDATED",
        details=f"Updated section #{section.id} ({section.name}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": "Section updated successfully.", "data": section.to_dict()}), 200


@master_data_bp.route("/sections/<int:section_id>", methods=["DELETE"])
@require_roles("CHAIR", "ADMIN")
def delete_section(section_id: int):
    """Delete a Cohort Section."""
    section = db.session.get(Section, section_id)
    if not section:
        return jsonify({"error": f"Section #{section_id} not found."}), 404

    name = section.name
    db.session.delete(section)

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SECTION_DELETED",
        details=f"Deleted section {name} (#{section_id}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": f"Section '{name}' deleted successfully."}), 200


# -----------------------------------------------------------------
# SUBJECTS CRUD
# -----------------------------------------------------------------
@master_data_bp.route("/subjects", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def create_subject():
    """Create a new Curricular Subject."""
    data = request.get_json(silent=True) or {}
    code = str(data.get("code", "")).strip().upper()
    title = str(data.get("title", "")).strip()
    units = data.get("units")
    subject_type = str(data.get("subject_type", "LECTURE")).strip().upper()
    hours_per_week = data.get("hours_per_week")

    if not code or not title:
        return jsonify({"error": "Course code and title are required."}), 400
    if subject_type not in {"LECTURE", "LAB"}:
        return jsonify({"error": "Subject type must be LECTURE or LAB."}), 400
    try:
        units = int(units)
        hours_per_week = int(hours_per_week)
        if units <= 0 or hours_per_week <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Units and hours per week must be positive integers."}), 400

    if Subject.query.filter_by(code=code).first():
        return jsonify({"error": f"Subject code '{code}' already exists."}), 409

    subject = Subject(
        code=code,
        title=title,
        units=units,
        subject_type=subject_type,
        hours_per_week=hours_per_week,
    )
    db.session.add(subject)
    db.session.flush()

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SUBJECT_CREATED",
        details=f"Created subject {subject.code} - {subject.title} ({subject.units}u, {subject.subject_type}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": "Subject created successfully.", "data": subject.to_dict()}), 201


@master_data_bp.route("/subjects/<int:subject_id>", methods=["PUT"])
@require_roles("CHAIR", "ADMIN")
def update_subject(subject_id: int):
    """Update an existing Curricular Subject."""
    subject = db.session.get(Subject, subject_id)
    if not subject:
        return jsonify({"error": f"Subject #{subject_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    if "code" in data:
        code = str(data["code"]).strip().upper()
        if not code:
            return jsonify({"error": "Subject code cannot be empty."}), 400
        existing = Subject.query.filter_by(code=code).first()
        if existing and existing.id != subject.id:
            return jsonify({"error": f"Subject code '{code}' already exists."}), 409
        subject.code = code

    if "title" in data:
        t = str(data["title"]).strip()
        if not t:
            return jsonify({"error": "Subject title cannot be empty."}), 400
        subject.title = t

    if "units" in data:
        try:
            u = int(data["units"])
            if u <= 0:
                raise ValueError()
            subject.units = u
        except (ValueError, TypeError):
            return jsonify({"error": "Units must be a positive integer."}), 400

    if "subject_type" in data:
        st = str(data["subject_type"]).strip().upper()
        if st not in {"LECTURE", "LAB"}:
            return jsonify({"error": "Subject type must be LECTURE or LAB."}), 400
        subject.subject_type = st

    if "hours_per_week" in data:
        try:
            hpw = int(data["hours_per_week"])
            if hpw <= 0:
                raise ValueError()
            subject.hours_per_week = hpw
        except (ValueError, TypeError):
            return jsonify({"error": "Hours per week must be a positive integer."}), 400

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SUBJECT_UPDATED",
        details=f"Updated subject #{subject.id} ({subject.code}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": "Subject updated successfully.", "data": subject.to_dict()}), 200


@master_data_bp.route("/subjects/<int:subject_id>", methods=["DELETE"])
@require_roles("CHAIR", "ADMIN")
def delete_subject(subject_id: int):
    """Delete a Curricular Subject."""
    subject = db.session.get(Subject, subject_id)
    if not subject:
        return jsonify({"error": f"Subject #{subject_id} not found."}), 404

    code = subject.code
    db.session.delete(subject)

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SUBJECT_DELETED",
        details=f"Deleted subject {code} (#{subject_id}).",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({"status": "success", "message": f"Subject '{code}' deleted successfully."}), 200


# -----------------------------------------------------------------
# FACULTY AVAILABILITY CRUD (Workflow 2 support)
# -----------------------------------------------------------------
@master_data_bp.route("/faculty/<int:faculty_id>/availability", methods=["GET"])
def get_faculty_availability(faculty_id: int):
    """List availability windows for a given faculty member."""
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

    avails = FacultyAvailability.query.filter_by(faculty_id=faculty_id).order_by(
        FacultyAvailability.day_of_week.asc(), FacultyAvailability.start_time.asc()
    ).all()

    return jsonify({
        "status": "success",
        "faculty_id": faculty_id,
        "faculty_name": faculty.name,
        "count": len(avails),
        "data": [a.to_dict() for a in avails],
    }), 200


@master_data_bp.route("/faculty/<int:faculty_id>/availability", methods=["POST"])
@require_roles("CHAIR", "ADMIN", "FACULTY")
def create_faculty_availability(faculty_id: int):
    """
    Add an availability or blackout window for a faculty member.
    Prototype behavior: allows faculty members or chairs to maintain availability windows.
    """
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

    data = request.get_json(silent=True) or {}
    day_of_week = str(data.get("day_of_week", "")).strip().upper()
    start_time_str = str(data.get("start_time", "")).strip()
    end_time_str = str(data.get("end_time", "")).strip()
    is_preferred = bool(data.get("is_preferred", True))

    valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
    if day_of_week not in valid_days:
        return jsonify({"error": f"Invalid day of week: {day_of_week}"}), 400

    try:
        sp = [int(p) for p in start_time_str.split(":")]
        ep = [int(p) for p in end_time_str.split(":")]
        st = time(sp[0], sp[1])
        et = time(ep[0], ep[1])
        if (st.hour * 60 + st.minute) >= (et.hour * 60 + et.minute):
            raise ValueError()
    except Exception:
        return jsonify({"error": "Invalid time window. Start time must be strictly earlier than end time (HH:MM)."}), 400

    avail = FacultyAvailability(
        faculty_id=faculty_id,
        day_of_week=day_of_week,
        start_time=st,
        end_time=et,
        is_preferred=is_preferred,
    )
    db.session.add(avail)
    db.session.flush()

    label = "preferred availability" if is_preferred else "blackout period"
    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_AVAILABILITY_SET",
        details=f"Added {label} for {faculty.name}: {day_of_week} {start_time_str}-{end_time_str}.",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Availability window saved for {faculty.name}.",
        "data": avail.to_dict(),
    }), 201


@master_data_bp.route("/availabilities/<int:avail_id>", methods=["DELETE"])
@require_roles("CHAIR", "ADMIN", "FACULTY")
def delete_faculty_availability(avail_id: int):
    """Delete an availability window."""
    avail = db.session.get(FacultyAvailability, avail_id)
    if not avail:
        return jsonify({"error": f"Availability record #{avail_id} not found."}), 404

    faculty_name = avail.faculty.name if avail.faculty else f"Faculty #{avail.faculty_id}"
    db.session.delete(avail)

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_AVAILABILITY_DELETED",
        details=f"Deleted availability window #{avail_id} for {faculty_name}.",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": "Availability window removed successfully.",
    }), 200


# -----------------------------------------------------------------
# FACULTY SUBJECT ASSIGNMENT (Program Chair & Admin)
# -----------------------------------------------------------------
@master_data_bp.route("/faculty/<int:faculty_id>/assignable-options", methods=["GET"])
@master_data_bp.route("/master/faculty/<int:faculty_id>/assignable-options", methods=["GET"])
@require_roles("CHAIR", "ADMIN")
def get_faculty_assignable_options(faculty_id: int):
    """Retrieve subjects, sections, and rooms tailored for assigning to a specific faculty member."""
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

    effective_role = session.get("active_role") or session.get("role")
    effective_prog = session.get("active_program") or session.get("program")

    # Chair scoping check
    if effective_role in ("CHAIR", "PROG_CHA") and effective_prog:
        fac_prog = (faculty.program or "").strip().upper()
        eff_prog = effective_prog.strip().upper()
        if fac_prog != eff_prog and fac_prog != "GEN":
            return jsonify({
                "error": f"Unauthorized: As {effective_prog} Program Chair, you can only manage faculty in your department."
            }), 403

    # Subjects: faculty's program + GEN subjects (or all if ADMIN)
    sub_query = Subject.query
    if effective_role in ("CHAIR", "PROG_CHA") or request.args.get("scoped", "true").lower() == "true":
        fac_prog = (faculty.program or "").strip().upper()
        sub_query = sub_query.filter(Subject.program.in_([fac_prog, "GEN"]))
    subjects = sub_query.order_by(Subject.code.asc()).all()
    # Exclude minor subjects: only Major subjects can be assigned to faculty
    subjects = [s for s in subjects if s.classification == "MAJOR"]

    # Sections: faculty's program sections
    sec_query = Section.query
    if effective_role in ("CHAIR", "PROG_CHA") or request.args.get("scoped", "true").lower() == "true":
        fac_prog = (faculty.program or "").strip().upper()
        sec_query = sec_query.filter(Section.program == fac_prog)
    sections = sec_query.order_by(Section.year_level.asc(), Section.name.asc()).all()

    # Rooms: all available rooms
    rooms = Room.query.filter_by(is_available=True).order_by(Room.room_code.asc()).all()

    return jsonify({
        "status": "success",
        "data": {
            "faculty": faculty.to_dict(),
            "subjects": [s.to_dict() for s in subjects],
            "sections": [s.to_dict() for s in sections],
            "rooms": [r.to_dict() for r in rooms],
        }
    }), 200


@master_data_bp.route("/faculty/<int:faculty_id>/assign-subject", methods=["POST"])
@master_data_bp.route("/master/faculty/<int:faculty_id>/assign-subject", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def assign_subject_to_faculty(faculty_id: int):
    """Assign a curricular subject offering to a faculty member with conflict validation."""
    from services.conflict_detector import validate_schedule_slot, parse_time

    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

    effective_role = session.get("active_role") or session.get("role")
    effective_prog = session.get("active_program") or session.get("program")

    # Chair scoping check
    if effective_role in ("CHAIR", "PROG_CHA") and effective_prog:
        fac_prog = (faculty.program or "").strip().upper()
        eff_prog = effective_prog.strip().upper()
        if fac_prog != eff_prog and fac_prog != "GEN":
            return jsonify({
                "error": f"Unauthorized: As {effective_prog} Program Chair, you can only assign subjects to faculty in your department."
            }), 403

    data = request.get_json(silent=True) or {}
    # Can receive single subject_id or list of subject_ids/subject objects
    raw_subjects = data.get("subjects") or []
    if not raw_subjects and data.get("subject_id"):
        raw_subjects = [{
            "subject_id": data.get("subject_id"),
            "split_preference": data.get("split_preference") or "1.5_HOUR_SPLIT"
        }]
    elif isinstance(raw_subjects, list) and raw_subjects and not isinstance(raw_subjects[0], dict):
        raw_subjects = [{"subject_id": sid, "split_preference": "1.5_HOUR_SPLIT"} for sid in raw_subjects]

    if not raw_subjects:
        return jsonify({"error": "At least one Subject Offering is required."}), 400

    section_id = data.get("section_id")
    raw_room_id = data.get("room_id")
    day_of_week = str(data.get("day_of_week", "MON")).strip().upper()
    if day_of_week not in {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}:
        day_of_week = "MON"

    start_time_str = data.get("start_time")
    end_time_str = data.get("end_time")
    allow_override = bool(data.get("allow_override", False))

    # Resolve Room if specified; if "none" / "do_not_assign" / 0 / None -> keep room None
    room = None
    if raw_room_id and str(raw_room_id).lower() not in ("none", "do_not_assign", "0", ""):
        if str(raw_room_id).isdigit() and int(raw_room_id) > 0:
            room = db.session.get(Room, int(raw_room_id))

    # If section_id is not provided, pick or assign to a default program section if needed, or find candidate
    section = None
    if section_id:
        section = db.session.get(Section, int(section_id))

    assigned_schedules = []

    for item in raw_subjects:
        s_id = item.get("subject_id") if isinstance(item, dict) else item
        item_split_pref = (item.get("split_preference") if isinstance(item, dict) else None) or "1.5_HOUR_SPLIT"
        if not s_id:
            continue

        subject = db.session.get(Subject, int(s_id))
        if not subject:
            return jsonify({"error": f"Subject #{s_id} not found."}), 404

        if subject.classification == "MINOR":
            return jsonify({
                "error": f"Minor subject '{subject.code} - {subject.title}' cannot be assigned to faculty members. Only Major subjects may be assigned."
            }), 400

        # Update subject's split preference if explicitly chosen
        if item_split_pref in ("1.5_HOUR_SPLIT", "3_HOUR_BLOCK"):
            subject.split_preference = item_split_pref

        # Resolve section if not selected
        sec_for_sched = section
        if not sec_for_sched:
            fac_prog = (faculty.program or "").strip().upper()
            sec_for_sched = Section.query.filter(
                (Section.program == fac_prog) | (Section.program == subject.program)
            ).order_by(Section.year_level.asc(), Section.name.asc()).first()
            if not sec_for_sched:
                sec_for_sched = Section.query.order_by(Section.year_level.asc(), Section.name.asc()).first()

        # Check existing schedule
        existing_sched = None
        if sec_for_sched:
            existing_sched = Schedule.query.filter_by(subject_id=subject.id, section_id=sec_for_sched.id).first()
        exclude_id = existing_sched.id if existing_sched else None

        # Resolve Day and Times: if multiple subjects are assigned without custom times, stagger them or pick available slots
        candidate_days_list = [day_of_week] if data.get("day_of_week") else ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
        standard_staggers = [
            ("08:00", "09:30"),
            ("09:30", "11:00"),
            ("11:00", "12:30"),
            ("13:00", "14:30"),
            ("14:30", "16:00"),
            ("16:00", "17:30"),
        ]
        standard_3hr_staggers = [
            ("08:00", "11:00"),
            ("11:00", "14:00"),
            ("14:00", "17:00"),
        ]

        if start_time_str and end_time_str:
            cur_start_str = start_time_str
            cur_end_str = end_time_str
            cur_day = day_of_week
        else:
            # Find an open slot for this instructor and section
            chosen_slot = None
            slot_options = standard_3hr_staggers if item_split_pref == "3_HOUR_BLOCK" else standard_staggers
            for d in candidate_days_list:
                for s_st, s_et in slot_options:
                    p_st = parse_time(s_st)
                    p_et = parse_time(s_et)
                    from services.conflict_detector import times_overlap
                    # Check faculty collision
                    fac_overlap = any(
                        s.day_of_week == d and times_overlap(p_st, p_et, s.start_time, s.end_time)
                        for s in Schedule.query.filter_by(faculty_id=faculty.id).all()
                    )
                    sec_overlap = sec_for_sched and any(
                        s.day_of_week == d and times_overlap(p_st, p_et, s.start_time, s.end_time)
                        for s in Schedule.query.filter_by(section_id=sec_for_sched.id).all()
                    )
                    if not fac_overlap and not sec_overlap:
                        chosen_slot = (d, s_st, s_et)
                        break
                if chosen_slot:
                    break

            if chosen_slot:
                cur_day, cur_start_str, cur_end_str = chosen_slot
            else:
                cur_day = day_of_week
                cur_start_str = "08:00"
                cur_end_str = "11:00" if item_split_pref == "3_HOUR_BLOCK" else "09:30"

        try:
            st = parse_time(cur_start_str)
            et = parse_time(cur_end_str)
        except Exception:
            st = parse_time("08:00")
            et = parse_time("09:30")

        # Resolve room if auto was requested or room not explicitly "none"
        sched_room = room
        if str(raw_room_id).lower() == "auto" and not sched_room:
            from services.conflict_detector import times_overlap
            is_lab = subject.subject_type == "LAB"
            target_room_type = "LAB" if is_lab else "LECTURE"
            fac_prog = (faculty.program or "").strip().upper()

            candidate_rooms = Room.query.filter_by(room_type=target_room_type, is_available=True).all()
            def room_rank(r):
                if r.department == fac_prog:
                    return 0
                if r.department == "GEN":
                    return 1
                return 2
            candidate_rooms.sort(key=room_rank)

            for r in candidate_rooms:
                overlapping = Schedule.query.filter_by(room_id=r.id, day_of_week=day_of_week).all()
                if exclude_id:
                    overlapping = [o for o in overlapping if o.id != exclude_id]
                if not any(times_overlap(st, et, s.start_time, s.end_time) for s in overlapping):
                    sched_room = r
                    break
            if not sched_room and candidate_rooms:
                sched_room = candidate_rooms[0]

        # Preflight Check if section exists
        if sec_for_sched:
            candidate = {
                "subject_id": subject.id,
                "section_id": sec_for_sched.id,
                "faculty_id": faculty.id,
                "room_id": sched_room.id if sched_room else None,
                "day_of_week": cur_day,
                "start_time": cur_start_str,
                "end_time": cur_end_str,
            }
            validation = validate_schedule_slot(candidate, exclude_schedule_id=exclude_id)
            if not validation["valid"] and not allow_override:
                # If room collision or section collision and override not requested, return error
                return jsonify({
                    "status": "error",
                    "error": f"Scheduling collision detected for {subject.code}.",
                    "conflicts": validation["conflicts"],
                    "can_override": True,
                }), 409

        # Save or update schedule
        if existing_sched:
            sched = existing_sched
            old_faculty_id = sched.faculty_id
            sched.faculty_id = faculty.id
            sched.room_id = sched_room.id if sched_room else None
            sched.day_of_week = cur_day
            sched.start_time = st
            sched.end_time = et
            sched.split_preference = item_split_pref
            if old_faculty_id and old_faculty_id != faculty.id:
                old_fac = db.session.get(Faculty, old_faculty_id)
                if old_fac:
                    old_u = db.session.query(db.func.sum(Subject.units)).join(Schedule, Schedule.subject_id == Subject.id).filter(Schedule.faculty_id == old_fac.id).scalar() or 0
                    old_fac.current_units = old_u
        else:
            sched = Schedule(
                subject_id=subject.id,
                section_id=sec_for_sched.id if sec_for_sched else 1,
                faculty_id=faculty.id,
                room_id=sched_room.id if sched_room else None,
                day_of_week=cur_day,
                start_time=st,
                end_time=et,
                status="PUBLISHED",
                split_preference=item_split_pref,
            )
            db.session.add(sched)

        db.session.flush()
        assigned_schedules.append(sched)

    # Recalculate faculty current_units
    new_units = db.session.query(db.func.sum(Subject.units)).join(Schedule, Schedule.subject_id == Subject.id).filter(Schedule.faculty_id == faculty.id).scalar() or 0
    faculty.current_units = new_units

    subj_codes = ", ".join([s.subject.code for s in assigned_schedules if s.subject])
    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_SUBJECT_ASSIGNED",
        details=f"Assigned {subj_codes} to {faculty.name}.",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Successfully assigned {subj_codes} to {faculty.name}.",
        "data": {
            "schedule": assigned_schedules[0].to_dict() if assigned_schedules else None,
            "schedules": [s.to_dict() for s in assigned_schedules],
            "faculty": faculty.to_dict(),
        }
    }), 201


@master_data_bp.route("/faculty/<int:faculty_id>/unassign-subject", methods=["POST"])
@master_data_bp.route("/master/faculty/<int:faculty_id>/unassign-subject", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def unassign_subject_from_faculty(faculty_id: int):
    """Unassign / remove a subject offering from a faculty member."""
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

    effective_role = session.get("active_role") or session.get("role")
    effective_prog = session.get("active_program") or session.get("program")

    # Chair scoping check
    if effective_role in ("CHAIR", "PROG_CHA") and effective_prog:
        fac_prog = (faculty.program or "").strip().upper()
        eff_prog = effective_prog.strip().upper()
        if fac_prog != eff_prog and fac_prog != "GEN":
            return jsonify({
                "error": f"Unauthorized: As {effective_prog} Program Chair, you can only manage faculty in your department."
            }), 403

    data = request.get_json(silent=True) or {}
    schedule_id = data.get("schedule_id")
    subject_id = data.get("subject_id")

    if schedule_id:
        sched = db.session.get(Schedule, int(schedule_id))
    elif subject_id:
        sched = Schedule.query.filter_by(faculty_id=faculty_id, subject_id=int(subject_id)).first()
    else:
        return jsonify({"error": "schedule_id or subject_id is required."}), 400

    if not sched or sched.faculty_id != faculty.id:
        return jsonify({"error": "Schedule assignment not found for this faculty member."}), 404

    subj_code = sched.subject.code if sched.subject else "Subject"
    db.session.delete(sched)
    db.session.flush()

    # Recalculate faculty current_units
    new_units = db.session.query(db.func.sum(Subject.units)).join(Schedule, Schedule.subject_id == Subject.id).filter(Schedule.faculty_id == faculty.id).scalar() or 0
    faculty.current_units = new_units

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_SUBJECT_UNASSIGNED",
        details=f"Unassigned {subj_code} from {faculty.name}.",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Successfully unassigned {subj_code} from {faculty.name}.",
        "data": faculty.to_dict(),
    }), 200


