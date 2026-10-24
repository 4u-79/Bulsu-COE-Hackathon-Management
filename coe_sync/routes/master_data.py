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
    try:
        capacity = int(capacity)
        if capacity <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Capacity must be an integer greater than 0."}), 400

    # Check uniqueness
    if Room.query.filter_by(room_code=room_code).first():
        return jsonify({"error": f"Room code '{room_code}' already exists."}), 409

    room = Room(
        room_code=room_code,
        room_type=room_type,
        capacity=capacity,
        is_available=is_available,
    )
    db.session.add(room)
    db.session.flush()

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="ROOM_CREATED",
        details=f"Created room {room.room_code} ({room.room_type}, capacity: {room.capacity}).",
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


@master_data_bp.route("/faculty/<int:faculty_id>", methods=["PUT"])
@require_roles("CHAIR", "ADMIN")
def update_faculty(faculty_id: int):
    """Update an existing Faculty member."""
    faculty = db.session.get(Faculty, faculty_id)
    if not faculty:
        return jsonify({"error": f"Faculty #{faculty_id} not found."}), 404

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
        student_count = int(student_count)
        if year_level <= 0 or student_count <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return jsonify({"error": "Year level and student count must be positive integers."}), 400

    section = Section(
        name=name,
        program=program,
        year_level=year_level,
        student_count=student_count,
    )
    db.session.add(section)
    db.session.flush()

    audit = AuditLog(
        user_id=session.get("user_id"),
        action="SECTION_CREATED",
        details=f"Created section {section.name} ({section.program}, Year {section.year_level}, {section.student_count} students).",
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

    if "student_count" in data:
        try:
            sc = int(data["student_count"])
            if sc <= 0:
                raise ValueError()
            section.student_count = sc
        except (ValueError, TypeError):
            return jsonify({"error": "Student count must be a positive integer."}), 400

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

