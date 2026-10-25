from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize shared SQLAlchemy instance
db = SQLAlchemy()


class User(db.Model):
    """
    User Account model representing system users with role-based access.
    Roles:
      - ADMIN: Full system administration
      - CHAIR: Department chair (academic management & conflict overrides)
      - FACULTY: Assigned faculty member (reference_id -> Faculty.id)
      - STUDENT: Section student representative (reference_id -> Section.id)
    """

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum(
            "DEAN",
            "ADMIN",
            "CHAIR",
            "PROG_CHA",
            "FACULTY",
            "FCLTY_DEPT",
            "STUDENT",
            "STDN_MYR",
            name="user_role_enum",
        ),
        nullable=False,
    )
    program = db.Column(db.String(20), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    is_active_status = db.Column(db.Boolean, default=True, nullable=False)
    must_change_credentials = db.Column(db.Boolean, default=False, nullable=False)
    demo_password = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    audit_logs = db.relationship(
        "AuditLog",
        backref="user",
        lazy=True,
        passive_deletes=True,
    )

    def set_password(self, password: str) -> None:
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify plain text password against stored hash with backward-compatible demo fallback."""
        if not password:
            return False
        if check_password_hash(self.password_hash, password):
            return True
        if self.demo_password and password == self.demo_password:
            return True
        # Keep default password verification compatible with password and nexus2026 for uncustomized demo accounts
        if self.demo_password in {"password", "nexus2026", "chair123", "admin123", "faculty123", "student123"} or self.must_change_credentials:
            if password in {self.demo_password, "password", "nexus2026", "chair123", "admin123", "faculty123", "student123"}:
                return True
        return False

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Serialize User to dictionary."""
        title = "System Administrator"
        if self.role == "DEAN":
            title = "College Dean"
        elif self.role in ("CHAIR", "PROG_CHA"):
            title = f"{self.program or ''} Program Chair".strip()
        elif self.role in ("FACULTY", "FCLTY_DEPT"):
            title = "Faculty Member"
        elif self.role in ("STUDENT", "STDN_MYR"):
            title = "Student Mayor"

        data = {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "title": title,
            "program": self.program,
            "reference_id": self.reference_id,
            "is_active_status": self.is_active_status,
            "must_change_credentials": self.must_change_credentials,
            "demo_password": self.demo_password,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "updated_at": (
                self.updated_at.isoformat() if self.updated_at else None
            ),
        }
        if include_sensitive:
            data["password_hash"] = self.password_hash
        return data

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}' role='{self.role}'>"


class Faculty(db.Model):
    """
    Faculty model storing faculty member credentials, workload limits,
    department program assignment, and current unit assignments.
    """

    __tablename__ = "faculty"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    program = db.Column(db.String(50), default="CE", nullable=False, index=True)
    max_units = db.Column(db.Integer, default=21, nullable=False)
    current_units = db.Column(db.Integer, default=0, nullable=False)
    preferred_session_type = db.Column(db.String(20), default="SPLIT", nullable=False)

    # Relationships
    schedules = db.relationship(
        "Schedule",
        backref="faculty",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    availabilities = db.relationship(
        "FacultyAvailability",
        backref="faculty",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self) -> dict:
        """Serialize Faculty to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "program": self.program,
            "department": self.program,
            "max_units": self.max_units,
            "current_units": self.current_units,
            "preferred_session_type": self.preferred_session_type or "SPLIT",
        }

    def __repr__(self) -> str:
        return f"<Faculty id={self.id} name='{self.name}' program='{self.program}' units={self.current_units}/{self.max_units}>"


class Section(db.Model):
    """
    Academic Section model representing student cohort classes (e.g. CE-1A, ECE-1A, MEE-1A, MFE-1A).
    """

    __tablename__ = "section"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    program = db.Column(db.String(50), nullable=True, index=True)
    year_level = db.Column(db.Integer, nullable=True)
    student_count = db.Column(db.Integer, nullable=True, default=None)
    class_mayor = db.Column(db.String(100), nullable=True, default=None)

    # Relationships
    schedules = db.relationship(
        "Schedule",
        backref="section",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def mayor_name(self) -> str:
        """Retrieve assigned class mayor or default mapping."""
        if self.class_mayor:
            return self.class_mayor
        try:
            from import_sql_dump import get_default_mayor_for_section
            return get_default_mayor_for_section(self.id, self.name)
        except Exception:
            return "Student Class Mayor"

    def to_dict(self) -> dict:
        """Serialize Section to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "program": self.program,
            "year_level": self.year_level,
            "student_count": getattr(self, "student_count", None),
            "class_mayor": self.mayor_name,
        }

    def __repr__(self) -> str:
        return f"<Section id={self.id} name='{self.name}' program='{self.program}' mayor='{self.mayor_name}'>"


class Subject(db.Model):
    """
    Course Subject model representing academic offerings across departments (Lecture or Lab).
    """

    __tablename__ = "subject"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(50), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    program = db.Column(db.String(50), nullable=True, index=True)
    units = db.Column(db.Integer, nullable=False)
    subject_type = db.Column(
        db.Enum("LECTURE", "LAB", name="subject_type_enum"),
        nullable=False,
    )
    hours_per_week = db.Column(db.Integer, nullable=False)
    year_level = db.Column(db.Integer, nullable=True)
    semester = db.Column(db.Integer, nullable=True)
    split_preference = db.Column(
        db.Enum("3_HOUR_BLOCK", "1.5_HOUR_SPLIT", name="subject_split_pref_enum"),
        default="1.5_HOUR_SPLIT",
        nullable=False,
    )
    is_general = db.Column(db.Boolean, default=False, nullable=False)
    requires_grouping = db.Column(db.Boolean, default=False, nullable=False)
    preferred_session_type = db.Column(db.String(20), default="SPLIT", nullable=False)

    # Relationships
    schedules = db.relationship(
        "Schedule",
        backref="subject",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def computed_year_level(self) -> int:
        """
        Derive year level from course code:
        100s -> 1st Year (e.g. MEE 101, COE 100)
        200s -> 2nd Year (e.g. MEE 201, COE 200)
        300s -> 3rd Year (e.g. MEE 300, MEE 301)
        400s -> 4th Year (e.g. MEE 400, MEE 401)
        Falls back to self.year_level or 1.
        """
        import re
        code_str = (self.code or "").strip().upper()
        m = re.search(r'([1-4])\d\d', code_str)
        if m:
            return int(m.group(1))
        return self.year_level or 1

    @property
    def classification(self) -> str:
        """
        Classify subject into 'MAJOR' or 'MINOR':
        - 3rd & 4th Year (300/400-level): Treated as Major subjects.
        - 1st & 2nd Year:
            - General Engineering (GEN):
                - Course codes starting with 'COE' (e.g. COE 100, COE 101, COE 200) -> Major Subjects
                - Rest of General Engineering (GEN) -> Minor Subjects (e.g. ETH 101, MATH 101, NSTP, PE)
            - Department courses (e.g. MEE 101, CE 101, ECE 201) -> Major Subjects
        """
        code_str = (self.code or "").strip().upper()
        prog_str = (self.program or "").strip().upper()
        yr = self.computed_year_level

        if yr >= 3:
            return "MAJOR"

        if code_str.startswith("COE"):
            return "MAJOR"

        if prog_str in ("GEN", "GENERAL", "GENERAL ENGINEERING"):
            return "MINOR"

        return "MAJOR"

    def to_dict(self) -> dict:
        """Serialize Subject to dictionary."""
        return {
            "id": self.id,
            "code": self.code,
            "title": self.title,
            "program": self.program,
            "units": self.units,
            "subject_type": self.subject_type,
            "hours_per_week": self.hours_per_week,
            "year_level": self.computed_year_level,
            "computed_year_level": self.computed_year_level,
            "classification": self.classification,
            "semester": self.semester,
            "split_preference": self.split_preference,
            "is_general": self.is_general,
            "requires_grouping": self.requires_grouping,
            "preferred_session_type": self.preferred_session_type or "SPLIT",
        }

    def __repr__(self) -> str:
        return f"<Subject id={self.id} code='{self.code}' program='{self.program}' units={self.units} type='{self.subject_type}'>"


class Room(db.Model):
    """
    Classroom and Laboratory facility model with equipment and capacity metadata.
    """

    __tablename__ = "room"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_code = db.Column(
        db.String(50), unique=True, nullable=False, index=True
    )
    room_type = db.Column(
        db.Enum("LECTURE", "LAB", name="room_type_enum"),
        nullable=False,
    )
    capacity = db.Column(db.Integer, nullable=False)
    equipment = db.Column(db.String(255), nullable=True)
    building = db.Column(db.String(100), default="COE 1 Building", nullable=True)
    is_available = db.Column(db.Boolean, default=True, nullable=False)
    department = db.Column(db.String(20), default="GEN", nullable=False)
    booked_by_label = db.Column(db.String(120), nullable=True)

    # Relationships
    schedules = db.relationship(
        "Schedule",
        backref="room",
        lazy=True,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self) -> dict:
        """Serialize Room to dictionary."""
        return {
            "id": self.id,
            "room_code": self.room_code,
            "room_type": self.room_type,
            "capacity": self.capacity,
            "equipment": self.equipment,
            "building": self.building or ("COE 2 Building" if "COE 2" in self.room_code else "COE 1 Building"),
            "is_available": self.is_available,
            "department": self.department or "GEN",
            "booked_by_label": self.booked_by_label,
        }

    def __repr__(self) -> str:
        return f"<Room id={self.id} code='{self.room_code}' type='{self.room_type}' capacity={self.capacity}>"


class Conflict(db.Model):
    """
    Conflict log entity tracking detected hard constraints and schedule overlaps.
    """

    __tablename__ = "conflict"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(
        db.Integer,
        db.ForeignKey("schedule.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    conflict_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), default="HARD", nullable=False)
    description = db.Column(db.Text, nullable=False)
    resolved = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    schedule = db.relationship(
        "Schedule",
        backref=db.backref("conflicts", cascade="all, delete-orphan", lazy=True),
    )

    def to_dict(self) -> dict:
        """Serialize Conflict to dictionary."""
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "conflict_type": self.conflict_type,
            "severity": self.severity,
            "description": self.description,
            "resolved": self.resolved,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
        }

    def __repr__(self) -> str:
        return f"<Conflict id={self.id} type='{self.conflict_type}' resolved={self.resolved}>"


class FacultyAvailability(db.Model):
    """
    Faculty Availability preference model specifying day and time bounds.
    If is_preferred is False, marks slot as unavailable / non-preferred.
    """

    __tablename__ = "faculty_availability"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    faculty_id = db.Column(
        db.Integer,
        db.ForeignKey("faculty.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day_of_week = db.Column(
        db.Enum(
            "MON",
            "TUE",
            "WED",
            "THU",
            "FRI",
            "SAT",
            name="day_of_week_enum",
        ),
        nullable=False,
    )
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_preferred = db.Column(db.Boolean, default=True, nullable=False)
    split_preference = db.Column(
        db.Enum("3_HOUR_BLOCK", "1.5_HOUR_SPLIT", name="fac_split_pref_enum"),
        default="1.5_HOUR_SPLIT",
        nullable=True,
    )

    def to_dict(self) -> dict:
        """Serialize FacultyAvailability to dictionary."""
        return {
            "id": self.id,
            "faculty_id": self.faculty_id,
            "day_of_week": self.day_of_week,
            "start_time": (
                self.start_time.strftime("%H:%M:%S")
                if self.start_time
                else None
            ),
            "end_time": (
                self.end_time.strftime("%H:%M:%S") if self.end_time else None
            ),
            "is_preferred": self.is_preferred,
            "split_preference": self.split_preference,
        }

    def __repr__(self) -> str:
        pref = "Preferred" if self.is_preferred else "Unavailable"
        return f"<FacultyAvailability faculty_id={self.faculty_id} {self.day_of_week} {self.start_time}-{self.end_time} ({pref})>"


class Schedule(db.Model):
    """
    Core timetable schedule entity binding subject, section, faculty, room,
    and assigned weekly day/time slot.
    """

    __tablename__ = "schedule"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey("subject.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section_id = db.Column(
        db.Integer,
        db.ForeignKey("section.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    faculty_id = db.Column(
        db.Integer,
        db.ForeignKey("faculty.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("room.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    sub_group = db.Column(db.String(10), nullable=True)  # 'G1', 'G2', or None
    day_of_week = db.Column(
        db.Enum(
            "MON",
            "TUE",
            "WED",
            "THU",
            "FRI",
            "SAT",
            "SUN",
            name="schedule_day_enum",
        ),
        nullable=False,
    )
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(
        db.Enum("DRAFT", "PUBLISHED", name="schedule_status_enum"),
        default="DRAFT",
        nullable=False,
    )
    split_preference = db.Column(
        db.Enum("3_HOUR_BLOCK", "1.5_HOUR_SPLIT", name="sched_split_pref_enum"),
        default="1.5_HOUR_SPLIT",
        nullable=False,
    )

    def to_dict(self) -> dict:
        """Serialize Schedule to dictionary, optionally resolving joined names."""
        return {
            "id": self.id,
            "subject_id": self.subject_id,
            "section_id": self.section_id,
            "faculty_id": self.faculty_id,
            "room_id": self.room_id,
            "day_of_week": self.day_of_week,
            "start_time": (
                self.start_time.strftime("%H:%M:%S")
                if self.start_time
                else None
            ),
            "end_time": (
                self.end_time.strftime("%H:%M:%S") if self.end_time else None
            ),
            "status": self.status,
            "split_preference": self.split_preference,
            "sub_group": self.sub_group,
            # Resolved display fields
            "subject_code": self.subject.code if self.subject else None,
            "subject_name": self.subject.title if self.subject else None,
            "subject_title": self.subject.title if self.subject else None,
            "section_name": f"{self.section.name} ({self.sub_group})" if (self.section and self.sub_group) else (self.section.name if self.section else None),
            "faculty_name": self.faculty.name if self.faculty else None,
            "room_code": self.room.room_code if self.room else ("Unassigned" if not self.room_id else None),
            # Conflict flag — resolved at API layer; default False here
            "has_conflict": False,
        }

    def __repr__(self) -> str:
        return (
            f"<Schedule id={self.id} subject_id={self.subject_id} "
            f"section_id={self.section_id} room_id={self.room_id} "
            f"{self.day_of_week} {self.start_time}-{self.end_time} status='{self.status}'>"
        )


class AuditLog(db.Model):
    """
    Audit Log entity recording chronological administrative and system actions.
    """

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        """Serialize AuditLog to dictionary."""
        return {
            "id": self.id,
            "timestamp": (
                self.timestamp.isoformat() if self.timestamp else None
            ),
            "user_id": self.user_id,
            "action": self.action,
            "details": self.details,
            "username": self.user.username if self.user else None,
        }

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} action='{self.action}' user_id={self.user_id} timestamp='{self.timestamp}'>"


class RescheduleRequest(db.Model):
    """
    Multi-tier Student Reschedule Request workflow model.
    Workflow:
      1. Student submits proposed day/time slot for their section's class -> PENDING_FACULTY
      2. Faculty member reviews and gives feedback -> PENDING_CHAIR or REJECTED
      3. Program Chair / Admin makes final decision -> APPROVED (atomically updates Schedule) or REJECTED
    """

    __tablename__ = "reschedule_request"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    schedule_id = db.Column(
        db.Integer,
        db.ForeignKey("schedule.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    student_section_id = db.Column(
        db.Integer,
        db.ForeignKey("section.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    proposed_day = db.Column(
        db.Enum(
            "MON",
            "TUE",
            "WED",
            "THU",
            "FRI",
            "SAT",
            name="reschedule_day_enum",
        ),
        nullable=False,
    )
    proposed_start_time = db.Column(db.Time, nullable=False)
    proposed_end_time = db.Column(db.Time, nullable=False)
    proposed_room_id = db.Column(
        db.Integer,
        db.ForeignKey("room.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by_role = db.Column(db.String(20), nullable=True, default="STUDENT")
    requested_by_name = db.Column(db.String(120), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.Enum(
            "PENDING",
            "PENDING_FACULTY",
            "PENDING_CHAIR",
            "APPROVED",
            "REJECTED",
            name="reschedule_status_enum",
        ),
        default="PENDING_FACULTY",
        nullable=False,
        index=True,
    )
    faculty_feedback = db.Column(db.Text, nullable=True)
    chair_feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    schedule = db.relationship(
        "Schedule",
        backref=db.backref("reschedule_requests", cascade="all, delete-orphan", lazy=True),
    )
    section = db.relationship(
        "Section",
        backref=db.backref("reschedule_requests", cascade="all, delete-orphan", lazy=True),
    )
    proposed_room = db.relationship(
        "Room",
        foreign_keys=[proposed_room_id],
        lazy=True,
    )

    def to_dict(self) -> dict:
        """Serialize RescheduleRequest to dictionary with joined helpers."""
        now = datetime.utcnow()
        days_passed = (now - self.created_at).days if self.created_at else 0
        expires_days = max(0, 7 - days_passed)

        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "student_section_id": self.student_section_id,
            "requested_by_role": self.requested_by_role or "STUDENT",
            "requested_by_name": self.requested_by_name,
            "proposed_day": self.proposed_day,
            "proposed_start_time": (
                self.proposed_start_time.strftime("%H:%M:%S")
                if self.proposed_start_time
                else None
            ),
            "proposed_end_time": (
                self.proposed_end_time.strftime("%H:%M:%S")
                if self.proposed_end_time
                else None
            ),
            "proposed_room_id": self.proposed_room_id,
            "proposed_room_code": (
                self.proposed_room.room_code if self.proposed_room else None
            ),
            "reason": self.reason,
            "status": self.status,
            "faculty_feedback": self.faculty_feedback,
            "chair_feedback": self.chair_feedback,
            "created_at": (
                self.created_at.isoformat() if self.created_at else None
            ),
            "expires_in_days": expires_days,
            # Joined presentation metadata
            "subject_code": (
                self.schedule.subject.code
                if self.schedule and self.schedule.subject
                else None
            ),
            "subject_title": (
                self.schedule.subject.title
                if self.schedule and self.schedule.subject
                else None
            ),
            "faculty_name": (
                self.schedule.faculty.name
                if self.schedule and self.schedule.faculty
                else None
            ),
            "faculty_id": self.schedule.faculty_id if self.schedule else None,
            "room_code": (
                self.schedule.room.room_code
                if self.schedule and self.schedule.room
                else None
            ),
            "section_name": self.section.name if self.section else None,
            "current_day": self.schedule.day_of_week if self.schedule else None,
            "current_start_time": (
                self.schedule.start_time.strftime("%H:%M")
                if self.schedule and self.schedule.start_time
                else None
            ),
            "current_end_time": (
                self.schedule.end_time.strftime("%H:%M")
                if self.schedule and self.schedule.end_time
                else None
            ),
        }

    def __repr__(self) -> str:
        return (
            f"<RescheduleRequest id={self.id} schedule_id={self.schedule_id} "
            f"section_id={self.student_section_id} status='{self.status}'>"
        )


class InterDepartmentRequest(db.Model):
    """
    NEXUS 2.0 Inter-Department Room & Conflict Request Model.
    Tracks overflow requests into GEN or other department rooms and room bookings.
    """

    __tablename__ = "inter_department_request"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_department = db.Column(db.String(20), nullable=False, default="GEN")
    target_department = db.Column(db.String(20), nullable=False, default="GEN")
    schedule_id = db.Column(
        db.Integer,
        db.ForeignKey("schedule.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    room_id = db.Column(
        db.Integer,
        db.ForeignKey("room.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_by_role = db.Column(db.String(30), nullable=True, default="CHAIR")
    requested_by_name = db.Column(db.String(120), nullable=True)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(30),
        default="PENDING_APPROVAL",
        nullable=False,
        index=True,
    )
    alternative_recommendations = db.Column(db.Text, nullable=True)
    chair_feedback = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    schedule = db.relationship(
        "Schedule",
        backref=db.backref("interdept_requests", cascade="all, delete-orphan", lazy=True),
    )
    room = db.relationship(
        "Room",
        foreign_keys=[room_id],
        lazy=True,
    )

    def to_dict(self) -> dict:
        """Serialize InterDepartmentRequest to dictionary."""
        import json
        now = datetime.utcnow()
        days_passed = (now - self.created_at).days if self.created_at else 0
        expires_days = max(0, 7 - days_passed)

        alts = []
        if self.alternative_recommendations:
            try:
                alts = json.loads(self.alternative_recommendations)
            except Exception:
                alts = [{"description": self.alternative_recommendations}]

        return {
            "id": self.id,
            "type": "INTER_DEPARTMENT",
            "source_department": self.source_department,
            "target_department": self.target_department,
            "schedule_id": self.schedule_id,
            "room_id": self.room_id,
            "room_code": self.room.room_code if self.room else None,
            "requested_by_role": self.requested_by_role or "CHAIR",
            "requested_by_name": self.requested_by_name,
            "reason": self.reason,
            "status": self.status,
            "alternative_recommendations": alts,
            "chair_feedback": self.chair_feedback,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_in_days": expires_days,
            "subject_code": self.schedule.subject.code if self.schedule and self.schedule.subject else None,
            "subject_title": self.schedule.subject.title if self.schedule and self.schedule.subject else None,
            "section_name": self.schedule.section.name if self.schedule and self.schedule.section else None,
            "faculty_name": self.schedule.faculty.name if self.schedule and self.schedule.faculty else None,
            "current_day": self.schedule.day_of_week if self.schedule else None,
            "current_start_time": self.schedule.start_time.strftime("%H:%M") if self.schedule and self.schedule.start_time else None,
            "current_end_time": self.schedule.end_time.strftime("%H:%M") if self.schedule and self.schedule.end_time else None,
        }

    def __repr__(self) -> str:
        return (
            f"<InterDepartmentRequest id={self.id} from={self.source_department} "
            f"to={self.target_department} status='{self.status}'>"
        )


