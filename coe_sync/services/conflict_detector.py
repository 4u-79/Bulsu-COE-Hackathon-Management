"""COE SYNC 2026 - Conflict Detection & Recommendation Engine

This module implements:
1. Mathematical Time Overlap Detection:
     Two windows A and B overlap iff: Start_A < End_B and Start_B < End_A on the same day_of_week.
2. Hard Constraint (HC) Validation:
     - Room Double-Booking
     - Faculty Double-Booking
     - Section Collision
     - Room Capacity Exceeded
     - Room Type Mismatch (e.g. LAB subject in non-LAB room)
     - Faculty Unavailability Blackout
3. 3-Step Recommendation Heuristics:
     - Step 1: Same Time, Alt Room
     - Step 2: Same Room, Next Slot
     - Step 3: Alternative Day
"""

from datetime import time, timedelta
from typing import Dict, Any, List, Optional
from models import (
    db,
    Schedule,
    Faculty,
    Section,
    Subject,
    Room,
    FacultyAvailability,
)


def parse_time(val: Any) -> time:
    """Safely convert string or time instance to datetime.time."""
    if isinstance(val, time):
        return val
    if isinstance(val, str):
        val = val.strip()
        parts = [int(p) for p in val.split(":")]
        if len(parts) == 2:
            return time(parts[0], parts[1], 0)
        elif len(parts) == 3:
            return time(parts[0], parts[1], parts[2])
    raise ValueError(f"Invalid time format: {val}. Expected HH:MM or HH:MM:SS.")


def time_to_minutes(t: time) -> int:
    """Convert time object to total minutes since midnight."""
    return t.hour * 60 + t.minute


def minutes_to_time(m: int) -> time:
    """Convert minutes since midnight back to a time object."""
    hours = (m // 60) % 24
    mins = m % 60
    return time(hours, mins, 0)


def times_overlap(
    start_a: time, end_a: time, start_b: time, end_b: time
) -> bool:
    """
    Mathematical time overlap detection:
    Start_A < End_B and Start_B < End_A
    """
    a_start = time_to_minutes(start_a)
    a_end = time_to_minutes(end_a)
    b_start = time_to_minutes(start_b)
    b_end = time_to_minutes(end_b)

    return a_start < b_end and b_start < a_end


def validate_schedule_slot(
    candidate_data: Dict[str, Any],
    exclude_schedule_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Hard Constraint (HC) Checks.
    Returns: { "valid": bool, "conflicts": [ ... ] }
    """
    conflicts: List[str] = []

    try:
        subject_id = int(candidate_data.get("subject_id", 0))
        section_id = int(candidate_data.get("section_id", 0))
        raw_fac_id = candidate_data.get("faculty_id")
        faculty_id = int(raw_fac_id) if (raw_fac_id is not None and str(raw_fac_id).isdigit() and int(raw_fac_id) > 0) else None
        raw_room_id = candidate_data.get("room_id")
        room_id = int(raw_room_id) if (raw_room_id is not None and str(raw_room_id).isdigit() and int(raw_room_id) > 0) else None
        sub_group = candidate_data.get("sub_group")
        if sub_group:
            sub_group = str(sub_group).strip().upper()
            if sub_group not in ("G1", "G2"):
                sub_group = None
        else:
            sub_group = None
        day_of_week = str(candidate_data.get("day_of_week", "")).strip().upper()

        start_time = parse_time(candidate_data.get("start_time"))
        end_time = parse_time(candidate_data.get("end_time"))
    except Exception as e:
        return {
            "valid": False,
            "conflicts": [f"Malformed schedule payload: {str(e)}"],
        }

    # Temporal logic validation
    if time_to_minutes(start_time) >= time_to_minutes(end_time):
        return {
            "valid": False,
            "conflicts": [
                "Invalid time slot: start_time must be strictly earlier than end_time."
            ],
        }

    valid_days = {"MON", "TUE", "WED", "THU", "FRI", "SAT"}
    if day_of_week not in valid_days:
        return {
            "valid": False,
            "conflicts": [
                f"Invalid day_of_week: '{day_of_week}'. Must be one of {sorted(list(valid_days))}."
            ],
        }

    # Fetch referenced database entities
    subject = db.session.get(Subject, subject_id)
    section = db.session.get(Section, section_id)
    faculty = db.session.get(Faculty, faculty_id) if faculty_id else None
    room = db.session.get(Room, room_id) if room_id else None

    if not subject:
        conflicts.append(f"Subject ID {subject_id} not found.")
    if not section:
        conflicts.append(f"Section ID {section_id} not found.")
    if faculty_id and not faculty:
        conflicts.append(f"Faculty ID {faculty_id} not found.")
    if room_id and not room:
        conflicts.append(f"Room ID {room_id} not found.")

    if conflicts:
        return {"valid": False, "conflicts": conflicts}

    # -------------------------------------------------------------
    # HC 4: Room Capacity (DEPRECATED - room capacity is not a blocking constraint)
    # Any section can be assigned to any room regardless of class size.
    # -------------------------------------------------------------

    # -------------------------------------------------------------
    # HC 5: Room Type Mismatch (Checked only if room is assigned)
    # -------------------------------------------------------------
    if room and subject.subject_type == "LAB" and room.room_type != "LAB":
        conflicts.append("Subject requires a specialized Laboratory facility.")

    # -------------------------------------------------------------
    # HC 1: Room Double-Booking (Checked only if room is assigned)
    # -------------------------------------------------------------
    if room_id and room:
        room_query = Schedule.query.filter(
            Schedule.room_id == room_id,
            Schedule.day_of_week == day_of_week,
        )
        if exclude_schedule_id:
            room_query = room_query.filter(Schedule.id != exclude_schedule_id)

        for s in room_query.all():
            if times_overlap(start_time, end_time, s.start_time, s.end_time):
                conflicts.append(
                    f"Room {room.room_code} is already occupied by {s.subject.code} "
                    f"({s.section.name}) at this time."
                )
                break

    # -------------------------------------------------------------
    # HC 2: Faculty Double-Booking (Checked only if faculty is assigned)
    # -------------------------------------------------------------
    if faculty_id and faculty:
        faculty_query = Schedule.query.filter(
            Schedule.faculty_id == faculty_id,
            Schedule.day_of_week == day_of_week,
        )
        if exclude_schedule_id:
            faculty_query = faculty_query.filter(Schedule.id != exclude_schedule_id)

        for s in faculty_query.all():
            if times_overlap(start_time, end_time, s.start_time, s.end_time):
                conflicts.append(
                    f"{faculty.name} is already assigned to {s.subject.code} "
                    f"({s.section.name}) at this time."
                )
                break

    # -------------------------------------------------------------
    # HC 3: Section Collision
    # -------------------------------------------------------------
    section_query = Schedule.query.filter(
        Schedule.section_id == section_id,
        Schedule.day_of_week == day_of_week,
    )
    if exclude_schedule_id:
        section_query = section_query.filter(Schedule.id != exclude_schedule_id)

    for s in section_query.all():
        if times_overlap(start_time, end_time, s.start_time, s.end_time):
            # If section is split into subgroups (e.g. G1 and G2 for lab), they can attend different classes concurrently
            existing_subgroup = getattr(s, "sub_group", None)
            if sub_group and existing_subgroup and sub_group != existing_subgroup:
                continue
            conflicts.append(
                f"Section {section.name} cannot attend two classes concurrently."
            )
            break

    # -------------------------------------------------------------
    # HC 6: Faculty Unavailability Blackout (Checked only if faculty is assigned)
    # -------------------------------------------------------------
    if faculty_id and faculty:
        blackout_slots = FacultyAvailability.query.filter_by(
            faculty_id=faculty_id,
            day_of_week=day_of_week,
            is_preferred=False,
        ).all()

        for blackout in blackout_slots:
            if times_overlap(
                start_time, end_time, blackout.start_time, blackout.end_time
            ):
                conflicts.append(
                    f"{faculty.name} is marked as unavailable during this time window."
                )
                break

    return {
        "valid": len(conflicts) == 0,
        "conflicts": conflicts,
    }


def find_alternatives(
    conflicted_data: Dict[str, Any],
    exclude_schedule_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    3-Step Recommendation Heuristic for resolving conflicted scheduling slots:
      - Step 1 (Same Time, Alt Room): Identical room_type, capacity >= student_count, free at same time.
      - Step 2 (Same Room, Next Slot): Earliest vacant standard slot in the same room on the same day.
      - Step 3 (Alternative Day): Earliest open slot for the room/facility and faculty on another day.
    """
    suggestions: List[Dict[str, Any]] = []

    try:
        subject_id = int(conflicted_data.get("subject_id", 0))
        section_id = int(conflicted_data.get("section_id", 0))
        raw_fac = conflicted_data.get("faculty_id")
        faculty_id = int(raw_fac) if (raw_fac is not None and str(raw_fac).isdigit() and int(raw_fac) > 0) else None
        room_id = int(conflicted_data.get("room_id", 0))
        day_of_week = str(conflicted_data.get("day_of_week", "")).strip().upper()
        start_time = parse_time(conflicted_data.get("start_time"))
        end_time = parse_time(conflicted_data.get("end_time"))
    except Exception:
        return suggestions

    subject = db.session.get(Subject, subject_id)
    section = db.session.get(Section, section_id)
    faculty = db.session.get(Faculty, faculty_id) if faculty_id else None
    room = db.session.get(Room, room_id)

    if not (subject and section and room):
        return suggestions

    start_m = time_to_minutes(start_time)
    end_m = time_to_minutes(end_time)
    duration = end_m - start_m
    if duration <= 0:
        duration = 90  # Default 1.5 hr block

    # =============================================================
    # STEP 1: Same Time, Alt Room
    # =============================================================
    # Query rooms of matching room_type (capacity is no longer a restriction)
    candidate_rooms = (
        Room.query.filter(
            Room.id != room_id,
            Room.room_type == subject.subject_type,
            Room.is_available == True,
        )
        .order_by(Room.room_code.asc())
        .all()
    )

    for alt_room in candidate_rooms:
        test_payload = {
            "subject_id": subject_id,
            "section_id": section_id,
            "faculty_id": faculty_id,
            "room_id": alt_room.id,
            "day_of_week": day_of_week,
            "start_time": start_time,
            "end_time": end_time,
        }
        res = validate_schedule_slot(test_payload, exclude_schedule_id)
        if res["valid"]:
            suggestions.append(
                {
                    "type": "ROOM_CHANGE",
                    "room_id": alt_room.id,
                    "room_code": alt_room.room_code,
                    "day_of_week": day_of_week,
                    "start_time": start_time.strftime("%H:%M:%S"),
                    "end_time": end_time.strftime("%H:%M:%S"),
                    "label": (
                        f"Switch to {alt_room.room_code} ({alt_room.room_type}) at same time"
                    ),
                }
            )
            if len(suggestions) >= 2:
                break

    # =============================================================
    # STEP 2: Same Room, Next Slot
    # =============================================================
    # Target room must satisfy room type
    target_room = (
        room
        if (subject.subject_type != "LAB" or room.room_type == "LAB")
        else (candidate_rooms[0] if candidate_rooms else room)
    )

    # Standard academic operating hours: 07:00 to 19:00 (in 30-min steps)
    day_start_m = 7 * 60  # 07:00
    day_end_m = 19 * 60  # 19:00

    time_slots_found = 0
    curr_m = day_start_m
    while curr_m + duration <= day_end_m and time_slots_found < 2:
        # Skip the exact same slot that had a conflict
        if curr_m == start_m:
            curr_m += 30
            continue

        cand_start = minutes_to_time(curr_m)
        cand_end = minutes_to_time(curr_m + duration)

        test_payload = {
            "subject_id": subject_id,
            "section_id": section_id,
            "faculty_id": faculty_id,
            "room_id": target_room.id,
            "day_of_week": day_of_week,
            "start_time": cand_start,
            "end_time": cand_end,
        }
        res = validate_schedule_slot(test_payload, exclude_schedule_id)
        if res["valid"]:
            suggestions.append(
                {
                    "type": "TIME_CHANGE",
                    "room_id": target_room.id,
                    "room_code": target_room.room_code,
                    "day_of_week": day_of_week,
                    "start_time": cand_start.strftime("%H:%M:%S"),
                    "end_time": cand_end.strftime("%H:%M:%S"),
                    "label": (
                        f"Shift to {cand_start.strftime('%H:%M')}-{cand_end.strftime('%H:%M')} "
                        f"in {target_room.room_code} ({day_of_week})"
                    ),
                }
            )
            time_slots_found += 1
            curr_m += duration
        else:
            curr_m += 30

    # =============================================================
    # STEP 3: Alternative Day
    # =============================================================
    all_days = ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
    alt_days = [d for d in all_days if d != day_of_week]

    day_slots_found = 0
    for alt_day in alt_days:
        if day_slots_found >= 2:
            break

        curr_m = day_start_m
        while curr_m + duration <= day_end_m:
            cand_start = minutes_to_time(curr_m)
            cand_end = minutes_to_time(curr_m + duration)

            test_payload = {
                "subject_id": subject_id,
                "section_id": section_id,
                "faculty_id": faculty_id,
                "room_id": target_room.id,
                "day_of_week": alt_day,
                "start_time": cand_start,
                "end_time": cand_end,
            }
            res = validate_schedule_slot(test_payload, exclude_schedule_id)
            if res["valid"]:
                suggestions.append(
                    {
                        "type": "DAY_CHANGE",
                        "room_id": target_room.id,
                        "room_code": target_room.room_code,
                        "day_of_week": alt_day,
                        "start_time": cand_start.strftime("%H:%M:%S"),
                        "end_time": cand_end.strftime("%H:%M:%S"),
                        "label": (
                            f"Reschedule to {alt_day} {cand_start.strftime('%H:%M')}-"
                            f"{cand_end.strftime('%H:%M')} in {target_room.room_code}"
                        ),
                    }
                )
                day_slots_found += 1
                break  # Found earliest slot for this alternative day
            curr_m += 30

    return suggestions


def validate_split_schedule_pair(
    first_slot: Dict[str, Any],
    second_slot: Dict[str, Any],
    exclude_schedule_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validates a 1.5-hour split pair for 3-unit courses:
    - Enforces both halves are assigned the same room, section, and instructor.
    - Enforces non-consecutive days (e.g. MON & THU, TUE & FRI, WED & SAT).
    - Enforces each half is 1.5 hours (90 minutes).
    - Runs HC1-HC6 validation for each half.
    """
    conflicts: List[str] = []

    # Check same room, section, and instructor
    if int(first_slot.get("room_id", 0)) != int(second_slot.get("room_id", 0)):
        conflicts.append("Split sessions must be assigned to the same room.")
    if int(first_slot.get("section_id", 0)) != int(second_slot.get("section_id", 0)):
        conflicts.append("Split sessions must be assigned to the same section.")
    if int(first_slot.get("faculty_id", 0)) != int(second_slot.get("faculty_id", 0)):
        conflicts.append("Split sessions must be assigned to the same faculty instructor.")
    if int(first_slot.get("subject_id", 0)) != int(second_slot.get("subject_id", 0)):
        conflicts.append("Split sessions must refer to the same subject course.")

    # Check non-consecutive days
    day_indices = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}
    d1 = str(first_slot.get("day_of_week", "")).strip().upper()
    d2 = str(second_slot.get("day_of_week", "")).strip().upper()

    if d1 == d2:
        conflicts.append(f"Split sessions must be scheduled on different days (both were on {d1}).")
    elif abs(day_indices.get(d1, -10) - day_indices.get(d2, -10)) <= 1:
        conflicts.append(f"Split sessions must be scheduled on non-consecutive days ({d1} and {d2} are consecutive).")

    # Check duration is 1.5 hours (90 minutes)
    try:
        st1 = parse_time(first_slot.get("start_time"))
        et1 = parse_time(first_slot.get("end_time"))
        dur1 = time_to_minutes(et1) - time_to_minutes(st1)
        if dur1 != 90:
            conflicts.append(f"First session duration must be exactly 90 minutes (1.5 hours), got {dur1} minutes.")
    except Exception as e:
        conflicts.append(f"Invalid time format for first session: {str(e)}")

    try:
        st2 = parse_time(second_slot.get("start_time"))
        et2 = parse_time(second_slot.get("end_time"))
        dur2 = time_to_minutes(et2) - time_to_minutes(st2)
        if dur2 != 90:
            conflicts.append(f"Second session duration must be exactly 90 minutes (1.5 hours), got {dur2} minutes.")
    except Exception as e:
        conflicts.append(f"Invalid time format for second session: {str(e)}")

    # HC validation on both slots
    v1 = validate_schedule_slot(first_slot, exclude_schedule_id)
    if not v1["valid"]:
        conflicts.extend([f"First session ({d1}): {c}" for c in v1["conflicts"]])

    v2 = validate_schedule_slot(second_slot, exclude_schedule_id)
    if not v2["valid"]:
        conflicts.extend([f"Second session ({d2}): {c}" for c in v2["conflicts"]])

    return {
        "valid": len(conflicts) == 0,
        "conflicts": conflicts,
    }
