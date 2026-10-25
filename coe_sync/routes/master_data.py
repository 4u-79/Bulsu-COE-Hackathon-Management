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
    FacultySubject,
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


@master_data_bp.route("/faculty/<int:faculty_id>/subjects", methods=["GET"])
@master_data_bp.route("/master/faculty/<int:faculty_id>/subjects", methods=["GET"])
def get_faculty_subjects(faculty_id: int):
    """Retrieve all subject offerings handled/assigned to this faculty member."""
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404
    return jsonify({
        "status": "success",
        "faculty_id": faculty.id,
        "faculty_name": faculty.name,
        "assigned_subjects": faculty.assigned_subjects,
    }), 200


@master_data_bp.route("/faculty/<int:faculty_id>/assign-subject", methods=["POST"])
@master_data_bp.route("/master/faculty/<int:faculty_id>/assign-subject", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def assign_subject_to_faculty(faculty_id: int):
    """
    Assign curricular subject offerings to a faculty member (pure assignment).
    Does NOT create a Schedule record with default day, time, room, or section.
    """
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

    assigned_items = []
    synced_schedules = []

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

        # Assign subject to faculty in database
        subject.assigned_faculty_id = faculty.id

        # Record in FacultySubject table
        existing_fs = FacultySubject.query.filter_by(faculty_id=faculty.id, subject_id=subject.id).first()
        if not existing_fs:
            fs = FacultySubject(faculty_id=faculty.id, subject_id=subject.id)
            db.session.add(fs)
            db.session.flush()
            assigned_items.append(fs)
        else:
            assigned_items.append(existing_fs)

        # Synchronize any existing unassigned (TBA) schedules for this subject if conflict-free
        unassigned_scheds = Schedule.query.filter_by(subject_id=subject.id, faculty_id=None).all()
        for sched in unassigned_scheds:
            from services.conflict_detector import validate_schedule_slot
            candidate = {
                "subject_id": sched.subject_id,
                "section_id": sched.section_id,
                "faculty_id": faculty.id,
                "room_id": sched.room_id,
                "day_of_week": sched.day_of_week,
                "start_time": sched.start_time.strftime("%H:%M:%S"),
                "end_time": sched.end_time.strftime("%H:%M:%S"),
            }
            res = validate_schedule_slot(candidate, exclude_schedule_id=sched.id)
            if res["valid"]:
                sched.faculty_id = faculty.id
                synced_schedules.append(sched)

    # Recalculate faculty current_units from assigned subjects
    unit_sum = (
        db.session.query(db.func.sum(Subject.units))
        .join(FacultySubject, FacultySubject.subject_id == Subject.id)
        .filter(FacultySubject.faculty_id == faculty.id)
        .scalar()
        or 0
    )
    faculty.current_units = unit_sum

    subj_codes = ", ".join([fs.subject.code for fs in assigned_items if fs.subject])
    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_SUBJECT_ASSIGNED",
        details=f"Assigned subject(s) {subj_codes} to {faculty.name}.",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Successfully assigned {subj_codes} to {faculty.name}.",
        "data": {
            "faculty": faculty.to_dict(),
            "assigned_subjects": faculty.assigned_subjects,
            "synced_schedules": [s.to_dict() for s in synced_schedules],
        }
    }), 201


@master_data_bp.route("/faculty/<int:faculty_id>/unassign-subject", methods=["POST"])
@master_data_bp.route("/master/faculty/<int:faculty_id>/unassign-subject", methods=["POST"])
@require_roles("CHAIR", "ADMIN")
def unassign_subject_from_faculty(faculty_id: int):
    """
    Unassign / remove a subject offering from a faculty member.
    Does NOT delete timetable schedules; instead reverts Schedule.faculty_id to None (TBA).
    """
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

    if not subject_id and schedule_id:
        sched = db.session.get(Schedule, int(schedule_id))
        if sched:
            subject_id = sched.subject_id

    if not subject_id:
        return jsonify({"error": "subject_id or schedule_id is required."}), 400

    subject = db.session.get(Subject, int(subject_id))
    if not subject:
        return jsonify({"error": f"Subject #{subject_id} not found."}), 404

    # Remove from FacultySubject
    FacultySubject.query.filter_by(faculty_id=faculty.id, subject_id=subject.id).delete()

    # Clear assigned_faculty_id on Subject if set to this faculty
    if subject.assigned_faculty_id == faculty.id:
        subject.assigned_faculty_id = None

    # Convert any schedules assigned to this faculty for this subject to TBA (faculty_id = None)
    matching_scheds = Schedule.query.filter_by(faculty_id=faculty.id, subject_id=subject.id).all()
    for s in matching_scheds:
        s.faculty_id = None

    db.session.flush()

    # Recalculate faculty current_units
    unit_sum = (
        db.session.query(db.func.sum(Subject.units))
        .join(FacultySubject, FacultySubject.subject_id == Subject.id)
        .filter(FacultySubject.faculty_id == faculty.id)
        .scalar()
        or 0
    )
    faculty.current_units = unit_sum

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="FACULTY_SUBJECT_UNASSIGNED",
        details=f"Unassigned {subject.code} from {faculty.name}.",
    )
    db.session.add(audit)
    db.session.commit()

    return jsonify({
        "status": "success",
        "message": f"Successfully unassigned {subject.code} from {faculty.name}.",
        "data": faculty.to_dict(),
    }), 200


