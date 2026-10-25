"""COE SYNC 2026 - Summary & Analytics API

Endpoints:
- GET /api/analytics/summary:
    * total_classes: Count of schedules
    * room_utilization: % of scheduled room-hours against available weekly slots (Mon-Sat 7am-7pm)
    * unresolved_conflicts: Overlapping rows or constraint violations in the database
    * schedule_quality_score: 100 minus soft constraint penalties (-5 for gaps >2h, -5 for waste >50 seats)
    * faculty_workloads: Faculty teaching load metrics and overload indicators
"""

from flask import Blueprint, jsonify, request, session
from models import (
    db,
    Schedule,
    Room,
    Faculty,
    Section,
    Subject,
    FacultyAvailability,
)
from services.conflict_detector import (
    times_overlap,
    time_to_minutes,
)

analytics_bp = Blueprint("analytics", __name__)


def _resolve_analytics_program(enforce_chair_scope=True):
    """Resolve target program filter based on user role and optional query parameter."""
    from routes.auth import get_effective_role, get_effective_program

    role = get_effective_role()
    effective_prog = get_effective_program()
    query_prog = request.args.get("program", "").strip().upper()

    if query_prog and query_prog != "ALL":
        return query_prog
    # Program Chairs are strictly scoped to their assigned engineering department
    if enforce_chair_scope and role == "CHAIR" and effective_prog:
        return effective_prog.strip().upper()
    return None


@analytics_bp.route("/summary", methods=["GET"])
def get_analytics_summary():
    """
    GET /api/analytics/summary
    Comprehensive analytics dashboard data.
    Program-scoped if ?program=... is provided; defaults to institutional view.
    """
    target_program = _resolve_analytics_program(enforce_chair_scope=False)

    if target_program:
        all_sections = (
            Section.query.filter_by(program=target_program)
            .order_by(Section.year_level.asc(), Section.name.asc())
            .all()
        )
        sec_ids = [s.id for s in all_sections]
        schedules = (
            Schedule.query.filter(Schedule.section_id.in_(sec_ids)).all()
            if sec_ids
            else []
        )
        all_faculty = (
            Faculty.query.filter_by(program=target_program)
            .order_by(Faculty.name.asc())
            .all()
        )
    else:
        all_sections = Section.query.order_by(
            Section.year_level.asc(), Section.name.asc()
        ).all()
        schedules = Schedule.query.all()
        all_faculty = Faculty.query.order_by(Faculty.name.asc()).all()

    all_available_rooms = Room.query.filter_by(is_available=True).all()
    if target_program:
        dept_room_ids = {s.room_id for s in schedules if s.room_id}
        if dept_room_ids:
            rooms = [r for r in all_available_rooms if r.id in dept_room_ids]
        else:
            rooms = all_available_rooms
    else:
        rooms = all_available_rooms

    total_classes = len(schedules)

    # -------------------------------------------------------------
    # 1. Room Utilization Calculation
    # Mon-Sat (6 days) x 12 hours (07:00 to 19:00) = 72 available hours per room
    # Calculated strictly per available room
    # -------------------------------------------------------------
    total_available_room_hours = len(rooms) * 72.0
    total_scheduled_hours = 0.0

    for r in rooms:
        r_scheds = [s for s in schedules if s.room_id == r.id]
        for s in r_scheds:
            dm = time_to_minutes(s.end_time) - time_to_minutes(s.start_time)
            if dm > 0:
                total_scheduled_hours += dm / 60.0

    room_utilization = 0.0
    if total_available_room_hours > 0:
        room_utilization = round(
            (total_scheduled_hours / total_available_room_hours) * 100.0, 2
        )

    # -------------------------------------------------------------
    # 2. Unresolved Conflicts in Database
    # Checks pairs of schedules for collisions and solo records for invalid states
    # -------------------------------------------------------------
    unresolved_conflicts = 0

    # Pairwise overlap checks
    n = len(schedules)
    for i in range(n):
        s1 = schedules[i]
        for j in range(i + 1, n):
            s2 = schedules[j]
            if s1.day_of_week == s2.day_of_week:
                if times_overlap(
                    s1.start_time, s1.end_time, s2.start_time, s2.end_time
                ):
                    # Room collision
                    if s1.room_id == s2.room_id:
                        unresolved_conflicts += 1
                    # Faculty collision
                    elif s1.faculty_id == s2.faculty_id:
                        unresolved_conflicts += 1
                    # Section collision
                    elif s1.section_id == s2.section_id:
                        unresolved_conflicts += 1

        # Check room capacity overflow (DEPRECATED - room capacity is not a conflict)

        # Check room type mismatch
        if (
            s1.subject
            and s1.room
            and s1.subject.subject_type == "LAB"
            and s1.room.room_type != "LAB"
        ):
            unresolved_conflicts += 1

        # Check faculty availability blackout
        blackouts = FacultyAvailability.query.filter_by(
            faculty_id=s1.faculty_id,
            day_of_week=s1.day_of_week,
            is_preferred=False,
        ).all()
        for b in blackouts:
            if times_overlap(s1.start_time, s1.end_time, b.start_time, b.end_time):
                unresolved_conflicts += 1
                break

    # -------------------------------------------------------------
    # 3. Schedule Quality Score
    # Starts at 100.
    # Penalties:
    #   - 5 points per gap > 2 hours in a section's daily timetable
    #   - 5 points per overloaded faculty instructor
    # -------------------------------------------------------------
    penalties = 0

    # Check daily gaps per section
    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    for sec in all_sections:
        for day in days:
            sec_schedules = [
                s
                for s in schedules
                if s.section_id == sec.id and s.day_of_week == day
            ]
            sec_schedules.sort(key=lambda s: time_to_minutes(s.start_time))

            for k in range(len(sec_schedules) - 1):
                prev_end = time_to_minutes(sec_schedules[k].end_time)
                next_start = time_to_minutes(sec_schedules[k + 1].start_time)
                gap = next_start - prev_end
                if gap > 120:  # Gap greater than 2 hours (120 minutes)
                    penalties += 5

    # Check faculty overload penalties
    for f in all_faculty:
        f_units = (
            db.session.query(db.func.sum(Subject.units))
            .join(Schedule, Schedule.subject_id == Subject.id)
            .filter(Schedule.faculty_id == f.id)
            .scalar()
            or 0
        )
        if f_units > f.max_units:
            penalties += 5

    quality_score = max(0, min(100, 100 - penalties))

    # -------------------------------------------------------------
    # 4. Faculty Workloads & Teaching Hours
    # -------------------------------------------------------------
    faculty_workloads = []
    for f in all_faculty:
        assigned_units = (
            db.session.query(db.func.sum(Subject.units))
            .join(Schedule, Schedule.subject_id == Subject.id)
            .filter(Schedule.faculty_id == f.id)
            .scalar()
            or 0
        )
        fac_scheds = [s for s in schedules if s.faculty_id == f.id]
        teaching_hours = 0.0
        for s in fac_scheds:
            dm = time_to_minutes(s.end_time) - time_to_minutes(s.start_time)
            if dm > 0:
                teaching_hours += dm / 60.0

        faculty_workloads.append(
            {
                "id": f.id,
                "name": f.name,
                "email": f.email,
                "program": f.program,
                "max_units": f.max_units,
                "assigned_units": assigned_units,
                "teaching_hours": round(teaching_hours, 1),
                "class_count": len(fac_scheds),
                "is_overloaded": bool(assigned_units > f.max_units),
            }
        )
    faculty_workloads.sort(key=lambda x: x["assigned_units"], reverse=True)

    # -------------------------------------------------------------
    # 5. Room Utilization Breakdown (Mon-Sat 7am-7pm = 72 hours max)
    # -------------------------------------------------------------
    room_breakdown = []
    for r in rooms:
        r_scheds = [s for s in schedules if s.room_id == r.id]
        sched_hours = 0.0
        for s in r_scheds:
            dm = time_to_minutes(s.end_time) - time_to_minutes(s.start_time)
            if dm > 0:
                sched_hours += dm / 60.0
        util_pct = round((sched_hours / 72.0) * 100.0, 1) if 72.0 > 0 else 0.0
        room_breakdown.append(
            {
                "id": r.id,
                "room_code": r.room_code,
                "name": r.room_code,
                "room_type": r.room_type,
                "capacity": r.capacity,
                "scheduled_hours": round(sched_hours, 1),
                "available_hours": 72.0,
                "utilization_rate": util_pct,
                "schedule_count": len(r_scheds),
                "is_available": r.is_available,
            }
        )
    room_breakdown.sort(key=lambda x: x["utilization_rate"], reverse=True)

    # -------------------------------------------------------------
    # 6. Section Breakdown
    # -------------------------------------------------------------
    section_breakdown = []
    for sec in all_sections:
        sec_scheds = [s for s in schedules if s.section_id == sec.id]
        sec_hours = 0.0
        for s in sec_scheds:
            dm = time_to_minutes(s.end_time) - time_to_minutes(s.start_time)
            if dm > 0:
                sec_hours += dm / 60.0
        section_breakdown.append(
            {
                "id": sec.id,
                "name": sec.name,
                "program": sec.program,
                "year_level": sec.year_level,
                "student_count": sec.student_count,
                "scheduled_hours": round(sec_hours, 1),
                "class_count": len(sec_scheds),
            }
        )
    section_breakdown.sort(key=lambda x: x["name"])

    unassigned_tba_classes = sum(1 for s in schedules if not s.faculty_id)

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "total_classes": total_classes,
                    "unassigned_tba_classes": unassigned_tba_classes,
                    "tba_count": unassigned_tba_classes,
                    "room_utilization": room_utilization,
                    "overall_room_utilization_pct": room_utilization,
                    "unresolved_conflicts": unresolved_conflicts,
                    "schedule_quality_score": quality_score,
                    "faculty_workloads": faculty_workloads,
                    "room_breakdown": room_breakdown,
                    "section_breakdown": section_breakdown,
                    "program_scope": target_program,
                    "is_department_scoped": bool(target_program),
                    "department_name": (
                        f"{target_program} Department"
                        if target_program
                        else "Institutional (All Programs)"
                    ),
                },
            }
        ),
        200,
    )


@analytics_bp.route("/reports", methods=["GET"])
def get_analytics_reports():
    """
    GET /api/analytics/reports
    Institutional Term Analytics or Department-Specific Analytics for Program Chairs.
    Room Utilization ranking vs. 72h weekly cap, Faculty Teaching Workloads vs. 21-unit policy limit,
    and Schedule Quality Score with deduction details.
    """
    target_program = _resolve_analytics_program()

    if target_program:
        all_sections = (
            Section.query.filter_by(program=target_program)
            .order_by(Section.year_level.asc(), Section.name.asc())
            .all()
        )
        sec_ids = [s.id for s in all_sections]
        schedules = (
            Schedule.query.filter(Schedule.section_id.in_(sec_ids)).all()
            if sec_ids
            else []
        )
        all_faculty = (
            Faculty.query.filter_by(program=target_program)
            .order_by(Faculty.name.asc())
            .all()
        )
    else:
        all_sections = Section.query.order_by(
            Section.year_level.asc(), Section.name.asc()
        ).all()
        schedules = Schedule.query.all()
        all_faculty = Faculty.query.order_by(Faculty.name.asc()).all()

    all_available_rooms = Room.query.filter_by(is_available=True).all()
    if target_program:
        dept_room_ids = {s.room_id for s in schedules if s.room_id}
        if dept_room_ids:
            rooms = [r for r in all_available_rooms if r.id in dept_room_ids]
        else:
            rooms = all_available_rooms
    else:
        rooms = all_available_rooms

    # 1. Room Utilization Ranking (Mon-Sat 7am-7pm = 72 hours max)
    room_utilization_list = []
    total_scheduled_room_hours = 0.0
    for r in rooms:
        r_scheds = [s for s in schedules if s.room_id == r.id]
        sched_hours = 0.0
        for s in r_scheds:
            dm = time_to_minutes(s.end_time) - time_to_minutes(s.start_time)
            if dm > 0:
                sched_hours += dm / 60.0
        total_scheduled_room_hours += sched_hours
        util_pct = round((sched_hours / 72.0) * 100.0, 1) if 72.0 > 0 else 0.0
        room_utilization_list.append(
            {
                "id": r.id,
                "room_code": r.room_code,
                "name": r.room_code,
                "room_type": r.room_type,
                "capacity": r.capacity,
                "scheduled_hours": round(sched_hours, 1),
                "available_hours": 72.0,
                "utilization_percentage": util_pct,
                "schedule_count": len(r_scheds),
            }
        )
    # Sorted by utilization percentage descending
    room_utilization_list.sort(key=lambda x: x["utilization_percentage"], reverse=True)

    avg_room_utilization = 0.0
    total_avail_hours = len(rooms) * 72.0
    if total_avail_hours > 0:
        avg_room_utilization = round((total_scheduled_room_hours / total_avail_hours) * 100.0, 2)

    # 2. Faculty Workload Distribution (Max Limit: 21 Units)
    faculty_workload_list = []
    for f in all_faculty:
        assigned_units = (
            db.session.query(db.func.sum(Subject.units))
            .join(Schedule, Schedule.subject_id == Subject.id)
            .filter(Schedule.faculty_id == f.id)
            .scalar()
            or 0
        )
        fac_scheds = [s for s in schedules if s.faculty_id == f.id]
        teaching_hours = 0.0
        for s in fac_scheds:
            dm = time_to_minutes(s.end_time) - time_to_minutes(s.start_time)
            if dm > 0:
                teaching_hours += dm / 60.0

        is_overloaded = bool(assigned_units > f.max_units)
        faculty_workload_list.append(
            {
                "id": f.id,
                "name": f.name,
                "email": f.email,
                "program": f.program,
                "max_units": f.max_units,
                "assigned_units": assigned_units,
                "teaching_hours": round(teaching_hours, 1),
                "schedule_count": len(fac_scheds),
                "is_overloaded": is_overloaded,
                "utilization_rate": (
                    round((assigned_units / f.max_units) * 100.0, 1)
                    if f.max_units > 0
                    else 0.0
                ),
            }
        )
    faculty_workload_list.sort(key=lambda x: x["assigned_units"], reverse=True)

    # 3. Schedule Quality Score with Deduction Details
    deductions = []
    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]

    # Check for idle gaps > 2 hours in section daily schedules
    for sec in all_sections:
        for day in days:
            sec_schedules = [
                s for s in schedules if s.section_id == sec.id and s.day_of_week == day
            ]
            sec_schedules.sort(key=lambda s: time_to_minutes(s.start_time))

            for k in range(len(sec_schedules) - 1):
                prev_end = time_to_minutes(sec_schedules[k].end_time)
                next_start = time_to_minutes(sec_schedules[k + 1].start_time)
                gap = next_start - prev_end
                if gap > 120:  # Gap > 2 hours (120 minutes)
                    gap_hours = round(gap / 60.0, 1)
                    deductions.append(
                        {
                            "type": "SECTION_IDLE_GAP",
                            "points": -5,
                            "reason": (
                                f"{sec.name} has a {gap_hours}h idle gap on {day} "
                                f"between {sec_schedules[k].end_time} and {sec_schedules[k+1].start_time}."
                            ),
                        }
                    )

    # Check for faculty workload overload (assigned units > 21)
    for f in faculty_workload_list:
        if f.get("is_overloaded"):
            deductions.append(
                {
                    "type": "FACULTY_OVERLOAD",
                    "points": -5,
                    "reason": f"Faculty {f['name']} assigned {f['assigned_units']} units (exceeds {f['max_units']} limit).",
                }
            )

    total_penalty = sum(abs(d["points"]) for d in deductions)
    quality_score = max(0, min(100, 100 - total_penalty))

    return (
        jsonify(
            {
                "status": "success",
                "data": {
                    "room_utilization": {
                        "average_percentage": avg_room_utilization,
                        "overall_room_utilization_pct": avg_room_utilization,
                        "rooms": room_utilization_list,
                        "weekly_capacity_benchmark_hours": 72.0,
                    },
                    "faculty_workload": {
                        "faculty": faculty_workload_list,
                        "overloaded_count": sum(1 for f in faculty_workload_list if f["is_overloaded"]),
                        "standard_max_units": 21,
                    },
                    "quality_score": {
                        "score": quality_score,
                        "total_penalty": total_penalty,
                        "deductions": deductions,
                    },
                    "program_scope": target_program,
                    "is_department_scoped": bool(target_program),
                    "department_name": (
                        f"{target_program} Department"
                        if target_program
                        else "Institutional (All Programs)"
                    ),
                },
            }
        ),
        200,
    )

