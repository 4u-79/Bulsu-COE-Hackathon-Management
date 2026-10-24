"""COE SYNC 2026 - Smart Schedule Generation Solver (services/scheduler.py)

Implements intelligent multi-criteria schedule placement for the Program Chair:
- Hard Constraint satisfaction: HC1 (Room), HC2 (Faculty), HC3 (Section), HC4 (Capacity), HC5 (Blackout), HC6 (Room Type)
- Soft Constraint optimization:
    * minimize_gaps: Clusters classes adjacently to eliminate long student idle gaps
    * balance_workload: Prioritizes instructors with lower teaching loads
    * optimize_utilization: Fits section cohort size tightly to room capacity
"""

from datetime import time
from typing import Dict, Any, List, Optional
from models import (
    db,
    Schedule,
    Section,
    Subject,
    Room,
    Faculty,
    AuditLog,
)
from services.conflict_detector import (
    validate_schedule_slot,
    parse_time,
    time_to_minutes,
    times_overlap,
)


def run_smart_scheduler(config: Dict[str, Any], user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Executes the intelligent timetable placement algorithm based on user parameters.
    """
    program = config.get("program")
    year_level = config.get("year_level")
    section_ids = config.get("section_ids") or []
    room_ids = config.get("room_ids") or []
    faculty_ids = config.get("faculty_ids", "all")
    preferences = config.get("preferences") or {}

    minimize_gaps = preferences.get("minimize_gaps", True)
    balance_workload = preferences.get("balance_workload", True)
    optimize_utilization = preferences.get("optimize_utilization", True)

    # 1. Resolve Target Sections
    sec_query = Section.query
    if section_ids:
        sec_query = sec_query.filter(Section.id.in_(section_ids))
    else:
        if program and str(program).strip().upper() != "ALL":
            sec_query = sec_query.filter(Section.program == str(program).strip())
        if year_level and str(year_level).strip().upper() != "ALL":
            try:
                sec_query = sec_query.filter(Section.year_level == int(year_level))
            except ValueError:
                pass

    sections = sec_query.order_by(Section.year_level.asc(), Section.name.asc()).all()
    if not sections:
        return {
            "status": "error",
            "message": "No cohort sections match the specified program and year level criteria.",
            "placed_count": 0,
            "unplaced_items": [],
            "quality_score": 0,
            "hard_conflicts": 0,
            "metrics": {"classes_scheduled": 0, "rooms_used": 0, "faculty_assigned": 0},
        }

    # 2. Resolve Available Rooms
    room_query = Room.query.filter_by(is_available=True)
    if room_ids:
        room_query = room_query.filter(Room.id.in_(room_ids))
    rooms = room_query.all()
    if not rooms:
        return {
            "status": "error",
            "message": "No active rooms selected for scheduling.",
            "placed_count": 0,
            "unplaced_items": [],
            "quality_score": 0,
            "hard_conflicts": 0,
            "metrics": {"classes_scheduled": 0, "rooms_used": 0, "faculty_assigned": 0},
        }

    # 3. Resolve Faculty Pool
    if faculty_ids != "all" and isinstance(faculty_ids, list) and len(faculty_ids) > 0:
        faculty_list = Faculty.query.filter(Faculty.id.in_(faculty_ids)).all()
    else:
        faculty_list = Faculty.query.all()

    if not faculty_list:
        faculty_list = Faculty.query.all()

    # 4. Resolve Subjects Pool
    subjects = Subject.query.order_by(Subject.units.desc()).all()

    # Time slots for standard classes
    lecture_slots = [
        ("08:00", "09:30"),
        ("09:30", "11:00"),
        ("11:00", "12:30"),
        ("13:00", "14:30"),
        ("14:30", "16:00"),
        ("16:00", "17:30"),
    ]
    lecture_slots_1_5 = [
        ("09:00", "10:30"),
        ("10:30", "12:00"),
        ("13:00", "14:30"),
        ("14:30", "16:00"),
        ("08:00", "09:30"),
        ("16:00", "17:30"),
    ]
    lab_slots = [
        ("08:00", "11:00"),
        ("13:00", "16:00"),
        ("16:00", "19:00"),
    ]
    block_3_hour_slots = [
        ("08:00", "11:00"),
        ("09:00", "12:00"),
        ("13:00", "16:00"),
        ("16:00", "19:00"),
    ]
    non_consecutive_day_pairs = [
        ("MON", "THU"),
        ("TUE", "FRI"),
        ("WED", "SAT"),
        ("MON", "FRI"),
        ("TUE", "SAT"),
    ]
    candidate_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]

    placed_schedules = []
    unplaced_items = []
    used_rooms = set()
    used_faculty = set()

    # Dynamic workload counter during this generation run
    faculty_units_assigned = {f.id: (f.current_units or 0) for f in faculty_list}
    existing_schedules = list(Schedule.query.all())

    def is_sec_busy(sec_id, day, st, et):
        return any(
            s.section_id == sec_id
            and s.day_of_week == day
            and times_overlap(s.start_time, s.end_time, st, et)
            for s in existing_schedules
        )

    def is_room_busy(room_id, day, st, et):
        return any(
            s.room_id == room_id
            and s.day_of_week == day
            and times_overlap(s.start_time, s.end_time, st, et)
            for s in existing_schedules
        )

    def is_fac_busy(fac_id, day, st, et):
        return any(
            s.faculty_id == fac_id
            and s.day_of_week == day
            and times_overlap(s.start_time, s.end_time, st, et)
            for s in existing_schedules
        )

    for sec in sections:
        # Match curriculum: only subjects corresponding to this section's program and year level
        sec_subjects = [
            sub
            for sub in subjects
            if (
                not sub.program
                or not sec.program
                or sec.program == "BSCpE"
                or sub.program in (sec.program, "ALL", "COMMON", "COE")
            )
            and (
                not sub.year_level
                or not sec.year_level
                or sec.program == "BSCpE"
                or sub.year_level == sec.year_level
            )
        ]

        for sub in sec_subjects:
            # Check if this section already has this subject scheduled
            if any(s.section_id == sec.id and s.subject_id == sub.id for s in existing_schedules):
                continue

            # Candidate rooms matching capacity and room type
            valid_rooms = [
                r for r in rooms
                if r.capacity >= sec.student_count
                and (sub.subject_type != "LAB" or r.room_type == "LAB")
            ]
            if not valid_rooms:
                unplaced_items.append({
                    "section": sec.name,
                    "subject": f"{sub.code} - {sub.title}",
                    "reason": f"No available {sub.subject_type} room with capacity >= {sec.student_count}",
                })
                continue

            # Soft constraint: Optimize room utilization (tightest capacity fit first)
            if optimize_utilization:
                valid_rooms.sort(key=lambda r: (r.capacity - sec.student_count))

            # Candidate faculty matching program & workload
            dept_faculty = [
                f for f in faculty_list
                if not f.program or not sec.program or f.program == sec.program or sec.program == "BSCpE"
            ]
            valid_faculty = dept_faculty if dept_faculty else [f for f in faculty_list]
            if balance_workload:
                valid_faculty.sort(
                    key=lambda f: (
                        faculty_units_assigned.get(f.id, 0),
                        faculty_units_assigned.get(f.id, 0) >= f.max_units,
                    )
                )

            # Check if 1.5-hour split preference applies for 3-unit lecture course
            is_split_lecture = (
                sub.subject_type == "LECTURE"
                and (sub.units == 3 or sub.hours_per_week == 3)
                and getattr(sub, "split_preference", "1.5_HOUR_SPLIT") == "1.5_HOUR_SPLIT"
            )

            slot_placed = False

            if is_split_lecture:
                # Search across non-consecutive day pairs with 1.5-hour blocks
                # Enforce that both halves are assigned the same room, section, and instructor
                for day1, day2 in non_consecutive_day_pairs:
                    if slot_placed:
                        break
                    for st_str, et_str in lecture_slots_1_5:
                        if slot_placed:
                            break
                        st = parse_time(st_str)
                        et = parse_time(et_str)

                        # Fast pre-check: section must be free on both days
                        if is_sec_busy(sec.id, day1, st, et) or is_sec_busy(sec.id, day2, st, et):
                            continue

                        for r in valid_rooms:
                            if slot_placed:
                                break
                            # Fast pre-check: room must be free on both days
                            if is_room_busy(r.id, day1, st, et) or is_room_busy(r.id, day2, st, et):
                                continue

                            for fac in valid_faculty:
                                # Fast pre-check: faculty must be free on both days
                                if is_fac_busy(fac.id, day1, st, et) or is_fac_busy(fac.id, day2, st, et):
                                    continue

                                p1 = {
                                    "subject_id": sub.id,
                                    "section_id": sec.id,
                                    "faculty_id": fac.id,
                                    "room_id": r.id,
                                    "day_of_week": day1,
                                    "start_time": st_str,
                                    "end_time": et_str,
                                }
                                p2 = {
                                    "subject_id": sub.id,
                                    "section_id": sec.id,
                                    "faculty_id": fac.id,
                                    "room_id": r.id,
                                    "day_of_week": day2,
                                    "start_time": st_str,
                                    "end_time": et_str,
                                }
                                v1 = validate_schedule_slot(p1)
                                v2 = validate_schedule_slot(p2)
                                if v1["valid"] and v2["valid"]:
                                    sched1 = Schedule(
                                        subject_id=sub.id,
                                        section_id=sec.id,
                                        faculty_id=fac.id,
                                        room_id=r.id,
                                        day_of_week=day1,
                                        start_time=st,
                                        end_time=et,
                                        status="DRAFT",
                                        split_preference="1.5_HOUR_SPLIT",
                                    )
                                    sched2 = Schedule(
                                        subject_id=sub.id,
                                        section_id=sec.id,
                                        faculty_id=fac.id,
                                        room_id=r.id,
                                        day_of_week=day2,
                                        start_time=st,
                                        end_time=et,
                                        status="DRAFT",
                                        split_preference="1.5_HOUR_SPLIT",
                                    )
                                    db.session.add(sched1)
                                    db.session.add(sched2)
                                    db.session.flush()

                                    placed_schedules.extend([sched1, sched2])
                                    existing_schedules.extend([sched1, sched2])
                                    used_rooms.add(r.id)
                                    used_faculty.add(fac.id)
                                    faculty_units_assigned[fac.id] = faculty_units_assigned.get(fac.id, 0) + sub.units

                                    slot_placed = True
                                    break

            if not slot_placed:
                # Single block placement (for LABs, 3_HOUR_BLOCK, or fallback)
                slots = lab_slots if sub.subject_type == "LAB" else (
                    block_3_hour_slots if getattr(sub, "split_preference", None) == "3_HOUR_BLOCK" else lecture_slots
                )
                split_val = getattr(sub, "split_preference", "3_HOUR_BLOCK")

                days_to_try = list(candidate_days)
                if minimize_gaps:
                    sec_days_with_classes = {
                        s.day_of_week
                        for s in existing_schedules
                        if s.section_id == sec.id
                    }
                    days_to_try.sort(key=lambda d: 0 if d in sec_days_with_classes else 1)

                for day in days_to_try:
                    if slot_placed:
                        break

                    for st_str, et_str in slots:
                        if slot_placed:
                            break
                        st = parse_time(st_str)
                        et = parse_time(et_str)

                        # Fast pre-check: section free
                        if is_sec_busy(sec.id, day, st, et):
                            continue

                        for r in valid_rooms:
                            if slot_placed:
                                break
                            # Fast pre-check: room free
                            if is_room_busy(r.id, day, st, et):
                                continue

                            for fac in valid_faculty:
                                # Fast pre-check: faculty free
                                if is_fac_busy(fac.id, day, st, et):
                                    continue

                                candidate_payload = {
                                    "subject_id": sub.id,
                                    "section_id": sec.id,
                                    "faculty_id": fac.id,
                                    "room_id": r.id,
                                    "day_of_week": day,
                                    "start_time": st_str,
                                    "end_time": et_str,
                                }

                                validation = validate_schedule_slot(candidate_payload)
                                if validation["valid"]:
                                    new_sched = Schedule(
                                        subject_id=sub.id,
                                        section_id=sec.id,
                                        faculty_id=fac.id,
                                        room_id=r.id,
                                        day_of_week=day,
                                        start_time=st,
                                        end_time=et,
                                        status="DRAFT",
                                        split_preference=split_val,
                                    )
                                    db.session.add(new_sched)
                                    db.session.flush()

                                    placed_schedules.append(new_sched)
                                    existing_schedules.append(new_sched)
                                    used_rooms.add(r.id)
                                    used_faculty.add(fac.id)
                                    faculty_units_assigned[fac.id] = faculty_units_assigned.get(fac.id, 0) + sub.units

                                    slot_placed = True
                                    break

            if not slot_placed:
                unplaced_items.append({
                    "section": sec.name,
                    "subject": f"{sub.code} - {sub.title}",
                    "reason": "Hard constraints prevented slot placement without collision.",
                })

    # Detect impossible scheduling state: zero offerings placed due to conflicts
    if len(placed_schedules) == 0 and unplaced_items:
        db.session.rollback()
        return {
            "status": "error",
            "message": "Impossible scheduling state: Hard constraint collisions prevented any offerings from being placed with the selected room and faculty constraints.",
            "placed_count": 0,
            "unplaced_items": unplaced_items,
            "quality_score": 0,
            "hard_conflicts": len(unplaced_items),
            "metrics": {
                "classes_scheduled": 0,
                "rooms_used": 0,
                "faculty_assigned": 0,
            },
        }

    # Calculate Quality Score
    quality_score = 100
    if unplaced_items:
        quality_score = max(50, quality_score - len(unplaced_items) * 5)

    # Soft constraint deduction: Room capacity excess > 30 seats
    for sched in placed_schedules:
        room = db.session.get(Room, sched.room_id)
        section = db.session.get(Section, sched.section_id)
        if room and section and (room.capacity - section.student_count) > 30:
            quality_score = max(50, quality_score - 2)

    # Log audit and commit transaction atomically
    try:
        audit = AuditLog(
            user_id=user_id,
            action="SMART_SCHEDULE_GENERATED",
            details=(
                f"Smart generation completed: {len(placed_schedules)} classes placed, "
                f"{len(unplaced_items)} unplaced. Quality Score: {quality_score}/100."
            ),
        )
        db.session.add(audit)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return {
            "status": "error",
            "message": f"Database transaction failed during schedule persistence: {str(e)}",
            "placed_count": 0,
            "unplaced_items": unplaced_items,
            "quality_score": 0,
            "hard_conflicts": len(unplaced_items),
            "metrics": {"classes_scheduled": 0, "rooms_used": 0, "faculty_assigned": 0},
        }

    return {
        "status": "success",
        "message": f"Successfully generated {len(placed_schedules)} optimal schedule slots.",
        "placed_count": len(placed_schedules),
        "unplaced_items": unplaced_items,
        "quality_score": quality_score,
        "hard_conflicts": 0,
        "metrics": {
            "classes_scheduled": len(placed_schedules),
            "rooms_used": len(used_rooms),
            "faculty_assigned": len(used_faculty),
        },
    }
