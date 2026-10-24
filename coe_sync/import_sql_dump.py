"""COE SYNC 2026 - SQL Dump Parser & Data Migration Utility
Parses raw coe-database.sql dump with 12 fragmented department tables,
cleans corrupted faculty, sections, and subjects, and yields unified datasets.
"""

import re
from pathlib import Path
from typing import Dict, List, Any, Optional


def parse_insert_tuples(sql_text: str, table_name: str) -> List[tuple]:
    """Extract inserted tuples for a specific table name from MySQL dump."""
    pattern = rf"INSERT INTO `{re.escape(table_name)}` VALUES\s*(.*?);"
    match = re.search(pattern, sql_text, re.DOTALL | re.IGNORECASE)
    if not match:
        return []
    
    values_str = match.group(1).strip()
    # Parse rows: (val1, val2, ...), (val1, val2, ...)
    # Split by '),(' or parse safely
    rows = []
    # Tokenizer for SQL tuple rows
    current = []
    in_str = False
    str_char = ""
    token = ""
    in_tuple = False

    i = 0
    while i < len(values_str):
        ch = values_str[i]

        if not in_str:
            if ch == "(":
                in_tuple = True
                current = []
                token = ""
                i += 1
                continue
            elif ch == ")":
                if in_tuple:
                    current.append(token.strip())
                    rows.append(current)
                    in_tuple = False
                    current = []
                    token = ""
                i += 1
                continue
            elif ch == "," and in_tuple:
                current.append(token.strip())
                token = ""
                i += 1
                continue
            elif ch in ("'", '"'):
                in_str = True
                str_char = ch
                i += 1
                continue
            elif in_tuple:
                token += ch
                i += 1
                continue
            else:
                i += 1
                continue
        else:
            # Inside string
            if ch == "\\" and i + 1 < len(values_str):
                # Escape sequence
                next_ch = values_str[i + 1]
                if next_ch == "n":
                    token += "\n"
                elif next_ch == "r":
                    token += "\r"
                elif next_ch == "t":
                    token += "\t"
                else:
                    token += next_ch
                i += 2
                continue
            elif ch == str_char:
                # Check for double quote escaping
                if i + 1 < len(values_str) and values_str[i + 1] == str_char:
                    token += str_char
                    i += 2
                    continue
                else:
                    in_str = False
                    i += 1
                    continue
            else:
                token += ch
                i += 1
                continue

    return rows


DEPT_MAP = {
    "Civil Engineering": "CE",
    "Computer Engineering": "CPE",
    "Electrical Engineering": "EE",
    "Electronics Engineering": "ECE",
    "Industrial Engineering": "IE",
    "Manufacturing Engineering": "MFGE",
    "Manufactoring Engineering": "MFGE",
    "Mechanical Engineering": "ME",
    "Mechatronics Engineering": "MEE",
    "General Engineering": "GEN",
    "General Subject": "GEN",
}

DEPT_FULL_LABELS = {
    "CE": "Civil Engineering (CE)",
    "CPE": "Computer Engineering (CPE)",
    "EE": "Electrical Engineering (EE)",
    "ECE": "Electronics Engineering (ECE)",
    "IE": "Industrial Engineering (IE)",
    "MFGE": "Manufacturing Engineering (MFGE)",
    "ME": "Mechanical Engineering (ME)",
    "MEE": "Mechatronics Engineering (MEE)",
    "GEN": "General Engineering (GEN)",
}


def generate_faculty_email(name: str, dept_code: str, existing_emails: set) -> str:
    """Generate a unique deterministic bulsu.edu.ph email address for a faculty member."""
    clean_name = re.sub(r"^(ENGR\.|DR\.|PROF\.|ARCH\.)\s+", "", name, flags=re.IGNORECASE).strip()
    parts = clean_name.lower().replace("-", " ").replace(",", " ").split()
    if len(parts) >= 2:
        first = re.sub(r"[^a-z0-9]", "", parts[0])
        last = re.sub(r"[^a-z0-9]", "", parts[-1])
        base_username = f"{first}.{last}"
    elif len(parts) == 1:
        base_username = re.sub(r"[^a-z0-9]", "", parts[0])
    else:
        base_username = "faculty.member"

    email = f"{base_username}@bulsu.edu.ph"
    counter = 2
    while email in existing_emails:
        email = f"{base_username}{counter}@bulsu.edu.ph"
        counter += 1
    existing_emails.add(email)
    return email


def match_faculty_for_user(uname: str, faculty_list: List[Dict[str, Any]], user_id: int) -> Optional[Dict[str, Any]]:
    """Match FAC-<SURNAME> and CHAIR-<SURNAME> users against coe facculty names."""
    clean = uname.replace("FAC-", "").replace("CHAIR-", "").strip()
    initial = clean[0].lower() if len(clean) > 1 else ""
    surname = clean[1:].lower() if len(clean) > 1 else clean.lower()
    surname_compact = surname.replace(" ", "")

    candidates = []
    for f in faculty_list:
        fname = f["name"].lower()
        fname_compact = fname.replace(" ", "")
        if surname_compact in fname_compact or surname in fname:
            candidates.append(f)

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        filtered = []
        for c in candidates:
            tokens = c["name"].upper().replace("ENGR.", "").replace("DR.", "").replace("PROF.", "").strip().split()
            if tokens and tokens[0].lower().startswith(initial):
                filtered.append(c)
        if len(filtered) == 1:
            return filtered[0]
        elif len(filtered) > 1:
            # Disambiguate by ID proximity/order
            return filtered[0] if int(user_id) < 60 else filtered[-1]
        return candidates[0]
    return None


SECTION_CLASS_MAYORS = {
    1: "Marc Andrei Santos",
    2: "Angelo Christian Reyes",
    3: "Patricia Mae Cruz",
    4: "Joshua David Mendoza",
    5: "Alyssa Marie Garcia",
    6: "John Carlo Ramos",
    7: "Gabriel Paolo Bautista",
    8: "Bea Bianca Fernandez",
    9: "Kenneth Roy Morales",
    10: "Justin Kyle Dela Cruz",
    11: "Christine Joy Villanueva",
    12: "Rafael Luis Soriano",
    13: "Nathaniel Clark Rivera",
    14: "Samantha Nicole Gomez",
    15: "Ethan James Aquino",
    16: "Chloe Danielle Castro",
    17: "Mark Anthony Salazar",
    18: "Princess Dianne Mercado",
    19: "Vincent Paul Tolentino",
    20: "Jasmine Rose Navarro",
    21: "Adrian Miguel Valenzuela",
    22: "Hannah Camille Pineda",
    23: "Christian Dave Manalo",
    24: "Elijah Kyle Ocampo",
    25: "Nicole Anne Cortez",
    26: "Dominic Rafael Domingo",
    27: "Kevin Carl Pascual",
    28: "Angelica Faith Lim",
    29: "Timothy John Estrada",
    30: "Maria Cristina Roxas",
    31: "Daniel Joseph Serrano",
    32: "Erica Louise Magat",
    33: "Aaron Philip Guzman",
    34: "Stephanie Jane Dizon",
    35: "Patrick Lance Bulaong",
    36: "Bryan Lester Galang",
    37: "Andrea Sophia Fabian",
    38: "Jerico Vince Quizon",
    39: "Kyle Matthew David",
    40: "Katrina Isabelle Tan",
    41: "Sean Michael Bernardo",
    42: "Rachel Anne Sioson",
    43: "Neil Patrick Guinto",
    44: "Clarisse Mae Mariano",
    45: "Lance Gabriel Dionisio",
    46: "Matthew Ryan Carpio",
    47: "Danielle Marie Tanjutco",
    48: "Paolo Miguel Sevilla",
    49: "Carlo James Alcantara",
    50: "Hazel Grace Mallari",
    51: "Ryan Christian Dimagiba",
    52: "Mary Grace Concepcion",
    53: "John Paul Hernandez",
    54: "Kimberly Rose Espino",
    55: "Miguel Angelo Cordova",
    56: "Denise Valerie Santos",
    57: "Tristan Jay Vergara",
    58: "Rochelle Ann Palad",
    59: "Francis Eric Agulto",
    60: "Janelle Marie Trinidad",
    61: "Cedric Vance Maclang",
    62: "Shaira Mae Perez",
    63: "Kurt Russel Alcaraz",
    64: "Joanna Marie Centeno",
    65: "Lester Troy Valencia",
    66: "Kimberly Joyce Adriano",
    67: "Renz Marion Santiago",
    68: "Chelsea Nicole Cruz",
    69: "Rommel Dave San Diego",
    70: "Patricia Ann Nicolas",
    71: "Aldrin James Bartolome",
    72: "Kyla Maureen Enriquez",
    73: "Christian Paul Lazaro",
    74: "Joanna Rose Maningas",
    75: "Earl Justine Silverio",
    76: "Camille Denise Roxas",
    77: "Renzo Miguel Angeles",
    78: "Kristine Joy Beltran",
    79: "Dave Michael Catu",
    80: "Alyssa Bianca Valerio",
    81: "Ian M. De Jesus",
    82: "Patricia Ysabel Castro",
    83: "Justine Carl Mendoza",
    84: "Ralph Lauren Panganiban",
    85: "Kimberly Anne Del Rosario",
    86: "John Vincent Tolentino",
    87: "Sophia Danielle Garcia",
    88: "Paul Andrei Santos",
    89: "Mark Laurence Bulaon",
    90: "Andrea Nicole Ramos",
}

SECTION_ID_BY_NAME = {
    "CE-1A": 1, "CE-1B": 2, "CE-1C": 3, "CE-2A": 4, "CE-2B": 5, "CE-2C": 6,
    "CE-3A": 7, "CE-3B": 8, "CE-3C": 9, "CE-4A": 10, "CE-4B": 11, "CE-4C": 12,
    "CPE-1A": 13, "CPE-1B": 14, "CPE-1C": 15, "CPE-1D": 16, "CPE-2A": 17, "CPE-2B": 18, "CPE-2C": 19, "CPE-2D": 20,
    "CPE-3A": 21, "CPE-3B": 22, "CPE-3C": 23, "CPE-4A": 24, "CPE-4B": 25, "CPE-4C": 26,
    "EE-1A": 27, "EE-1B": 28, "EE-1C": 29, "EE-2A": 30, "EE-2B": 31, "EE-2C": 32,
    "EE-3A": 33, "EE-3B": 34, "EE-3C": 35, "EE-4A": 36, "EE-4B": 37, "EE-4C": 38,
    "ECE-1A": 39, "ECE-1B": 40, "ECE-2A": 41, "ECE-2B": 42, "ECE-3A": 43, "ECE-3B": 44, "ECE-3C": 45, "ECE-4A": 46, "ECE-4B": 47, "ECE-4C": 48,
    "IE-1A": 49, "IE-1B": 50, "IE-1C": 51, "IE-2A": 52, "IE-2B": 53, "IE-2C": 54,
    "IE-3A": 55, "IE-3B": 56, "IE-3C": 57, "IE-4A": 58, "IE-4B": 59, "IE-4C": 60,
    "MFGE-1A": 61, "MFGE-1B": 62, "MFGE-2A": 63, "MFGE-2B": 64, "MFGE-3A": 65, "MFGE-3B": 66, "MFGE-4A": 67, "MFGE-4B": 68,
    "ME-1A": 69, "ME-1B": 70, "ME-1C": 71, "ME-2A": 72, "ME-2B": 73, "ME-2C": 74,
    "ME-3A": 75, "ME-3B": 76, "ME-3C": 77, "ME-4A": 78, "ME-4B": 79, "ME-4C": 80,
    "MEE-1A": 81, "MEE-1B": 82, "MEE-1C": 83, "MEE-2A": 84, "MEE-2B": 85, "MEE-2C": 86,
    "MEE-3A": 87, "MEE-3B": 88, "MEE-4A": 89, "MEE-4B": 90,
}


def get_default_mayor_for_section(section_id: int = None, section_name: str = None) -> str:
    """Retrieve the authoritative default class mayor for a cohort section."""
    if section_id and section_id in SECTION_CLASS_MAYORS:
        return SECTION_CLASS_MAYORS[section_id]
    if section_name:
        clean = section_name.replace(" ", "").upper()
        sid = SECTION_ID_BY_NAME.get(clean)
        if sid and sid in SECTION_CLASS_MAYORS:
            return SECTION_CLASS_MAYORS[sid]
    return "Student Class Mayor"


def load_and_clean_data_final_sql(sql_file_path: Path = None) -> Dict[str, Any]:
    """
    Parse and clean data-final.sql (Authoritative Primary SQL Dump for NEXUS 2.0).
    Ingests all 539 Subjects, 90 Sections, 126 Faculty, and 129 Users.
    Disambiguates duplicate lab codes, cleans whitespace, normalizes departments,
    and resolves user-faculty/section relationships automatically.
    """
    if sql_file_path is None:
        sql_file_path = Path(__file__).resolve().parent / "data-final.sql"

    if not sql_file_path.exists():
        raise FileNotFoundError(f"data-final.sql not found at {sql_file_path}")

    sql_text = sql_file_path.read_text(encoding="utf-8", errors="ignore")

    # 1. Faculty (126 real BulSU COE faculty across 8 depts + General Engineering)
    raw_fac = parse_insert_tuples(sql_text, "coe facculty")
    if not raw_fac:
        raw_fac = parse_insert_tuples(sql_text, "coe faculty")
    faculty_list = []
    existing_emails = set()

    for r in raw_fac:
        row_id = int(r[0])
        name = " ".join(r[1].split())
        dept_raw = r[3].strip()
        prog = DEPT_MAP.get(dept_raw, "GEN")
        raw_email = r[2].strip() if len(r) > 2 and r[2] else ""
        if raw_email and "@" in raw_email:
            email = raw_email
            existing_emails.add(email)
        else:
            email = generate_faculty_email(name, prog, existing_emails)

        max_units = int(r[4]) if len(r) > 4 and r[4] and r[4].isdigit() else 21
        curr_units = int(r[5]) if len(r) > 5 and r[5] and r[5].isdigit() else 0

        faculty_list.append({
            "id": row_id,
            "name": name,
            "email": email,
            "program": prog,
            "max_units": max_units,
            "current_units": curr_units,
            "preferred_session_type": "SPLIT",
        })

    # 2. Sections (90 sections across 8 departments, student_count = 40)
    raw_sec = parse_insert_tuples(sql_text, "coe sections")
    sections_list = []

    for r in raw_sec:
        row_id = int(r[0])
        sec_name = " ".join(r[1].split())
        dept_raw = r[2].strip()
        yr = int(r[3]) if len(r) > 3 and r[3] and r[3] != "NULL" else 1
        prog = DEPT_MAP.get(dept_raw, "GEN")

        sections_list.append({
            "id": row_id,
            "name": sec_name,
            "program": prog,
            "year_level": yr,
            "student_count": 40,
            "class_mayor": get_default_mayor_for_section(row_id, sec_name),
        })

    # Find MEE - 1A section id for student mayor
    mee_1a_sec = next((s for s in sections_list if "MEE" in s["name"] and "1A" in s["name"].replace(" ", "")), None)
    mee_1a_id = mee_1a_sec["id"] if mee_1a_sec else 81

    # 3. Subjects (539 Curricular Subjects in 9-column format)
    # (ID, Subject Code, Course Description, No. of Units, Total Hours, Type, Department, Year Level, Semester)
    raw_subj = parse_insert_tuples(sql_text, "coe subjects")
    subjects_list = []
    seen_codes = set()

    for r in raw_subj:
        row_id = int(r[0])
        raw_code = r[1]
        raw_desc = r[2]
        units = int(r[3]) if len(r) > 3 and r[3] and r[3] != "NULL" else 3
        hours = int(r[4]) if len(r) > 4 and r[4] and r[4] != "NULL" else 3
        stype_raw = r[5] if len(r) > 5 and r[5] else "Lecture"
        dept_raw = r[6] if len(r) > 6 and r[6] else "General Subject"
        yr = int(r[7]) if len(r) > 7 and r[7] and r[7] != "NULL" else 1
        sem = int(r[8]) if len(r) > 8 and r[8] and r[8] != "NULL" else 1

        # Anomaly Fix 1: Collapse extra whitespace (e.g. 'Introduction     to     Mechatronics Engineering')
        desc = " ".join(raw_desc.split())

        # Anomaly Fix 2: Clean subject codes (strip trailing periods, normalize internal space before lab suffixes L/D/F)
        code = " ".join(raw_code.split()).rstrip(".").strip()
        code = re.sub(r"\s+([LDF])$", r"\1", code)

        prog = DEPT_MAP.get(dept_raw.strip(), "GEN")
        is_lab = "LAB" in stype_raw.strip().upper()
        norm_type = "LAB" if is_lab else "LECTURE"

        # Anomaly Fix 3: Disambiguate duplicate lecture/lab subject codes (e.g. MFG 221 Lecture vs Lab)
        if is_lab and (not (code.endswith("L") or code.endswith("D") or code.endswith("F")) or code in seen_codes):
            code += "L"

        seen_codes.add(code)

        is_gen = (prog == "GEN")
        req_grouping = is_lab or code.endswith("D") or code.endswith("F") or "DESIGN" in desc.upper() or "FIELD" in desc.upper()
        pref_session = "STRAIGHT" if norm_type == "LAB" else ("SPLIT" if (hours == 3 or units == 3) else "STRAIGHT")
        split_pref = "3_HOUR_BLOCK" if pref_session == "STRAIGHT" else "1.5_HOUR_SPLIT"

        subjects_list.append({
            "id": row_id,
            "code": code,
            "title": desc,
            "program": prog,
            "units": units,
            "hours_per_week": hours,
            "subject_type": norm_type,
            "year_level": yr,
            "semester": sem,
            "is_general": is_gen,
            "requires_grouping": req_grouping,
            "preferred_session_type": pref_session,
            "split_preference": split_pref,
        })

    # 4. Users (129 users: admin, DEAN-AAlba, 10 CHAIRs, 116 FACs, SMIDeJesus)
    raw_users = parse_insert_tuples(sql_text, "users")
    users_list = []
    seen_usernames = set()

    for r in raw_users:
        user_id = int(r[0])
        raw_uname = r[1].strip()
        raw_pwd = r[2].strip() if len(r) > 2 else "password"
        raw_role = r[3].strip() if len(r) > 3 else "FCLTY_DEPT"

        assigned_role = raw_role
        assigned_prog = None
        assigned_ref = None

        if raw_uname == "admin":
            assigned_role = "ADMIN"
            assigned_prog = None
            assigned_ref = None
        elif raw_uname == "DEAN-AAlba":
            assigned_role = "DEAN"
            assigned_prog = None
            assigned_ref = None
        elif raw_uname == "SMIDeJesus":
            assigned_role = "STUDENT"
            assigned_prog = "MEE"
            assigned_ref = mee_1a_id
        elif raw_uname.startswith("CHAIR-"):
            assigned_role = "PROG_CHA"
            fac = match_faculty_for_user(raw_uname, faculty_list, user_id)
            if fac:
                assigned_ref = fac["id"]
                assigned_prog = fac["program"]
            elif len(r) > 4 and r[4]:
                assigned_prog = DEPT_MAP.get(r[4].strip(), "GEN")
        elif raw_uname.startswith("FAC-"):
            assigned_role = "FCLTY_DEPT"
            fac = match_faculty_for_user(raw_uname, faculty_list, user_id)
            if fac:
                assigned_ref = fac["id"]
                assigned_prog = fac["program"]
            elif len(r) > 4 and r[4]:
                assigned_prog = DEPT_MAP.get(r[4].strip(), "GEN")

        # Disambiguate duplicate usernames to guarantee zero duplicate-key drops
        unique_uname = raw_uname
        if unique_uname in seen_usernames:
            unique_uname = f"{raw_uname}-{assigned_prog}" if assigned_prog else f"{raw_uname}2"
        seen_usernames.add(unique_uname)

        users_list.append({
            "id": user_id,
            "username": unique_uname,
            "password": raw_pwd,
            "role": assigned_role,
            "program": assigned_prog,
            "reference_id": assigned_ref,
        })

    return {
        "faculty": faculty_list,
        "sections": sections_list,
        "subjects": subjects_list,
        "users": users_list,
    }


def load_and_clean_data3_sql(sql_file_path: Path = None) -> Dict[str, Any]:
    """
    Parse and clean data-3.sql (Primary SQL Dump for NEXUS 2.0).
    Ingests all 539 Subjects, 90 Sections, and 126 Faculty.
    Applies exact column parsing for 9-column coe subjects:
    (ID, Subject Code, Course Description, No. of Units, Total Hours, Type, Department, Year Level, Semester)
    """
    if sql_file_path is None:
        sql_file_path = Path(__file__).resolve().parent / "data-3.sql"

    if not sql_file_path.exists():
        raise FileNotFoundError(f"data-3.sql not found at {sql_file_path}")

    sql_text = sql_file_path.read_text(encoding="utf-8")

    # 1. Faculty (126 real BulSU COE faculty across 8 depts + General Engineering)
    raw_fac = parse_insert_tuples(sql_text, "coe facculty")
    faculty_list = []
    existing_emails = set()

    for r in raw_fac:
        row_id = int(r[0])
        name = " ".join(r[1].split())
        dept_raw = r[3].strip()
        prog = DEPT_MAP.get(dept_raw, "GEN")
        email = generate_faculty_email(name, prog, existing_emails)

        faculty_list.append({
            "id": row_id,
            "name": name,
            "email": email,
            "program": prog,
            "max_units": 21,
            "current_units": 0,
            "preferred_session_type": "SPLIT",
        })

    # 2. Sections (90 sections across 8 departments, student_count = 40)
    raw_sec = parse_insert_tuples(sql_text, "coe sections")
    sections_list = []

    for r in raw_sec:
        row_id = int(r[0])
        sec_name = " ".join(r[1].split())
        dept_raw = r[2].strip()
        yr = int(r[3]) if len(r) > 3 and r[3] and r[3] != "NULL" else 1
        prog = DEPT_MAP.get(dept_raw, "GEN")

        sections_list.append({
            "id": row_id,
            "name": sec_name,
            "program": prog,
            "year_level": yr,
            "student_count": 40,
        })

    # 3. Subjects (539 Curricular Subjects in 9-column format)
    # (ID, Subject Code, Course Description, No. of Units, Total Hours, Type, Department, Year Level, Semester)
    raw_subj = parse_insert_tuples(sql_text, "coe subjects")
    subjects_list = []
    seen_codes = set()

    for r in raw_subj:
        row_id = int(r[0])
        raw_code = r[1]
        raw_desc = r[2]
        units = int(r[3]) if len(r) > 3 and r[3] and r[3] != "NULL" else 3
        hours = int(r[4]) if len(r) > 4 and r[4] and r[4] != "NULL" else 3
        stype_raw = r[5] if len(r) > 5 and r[5] else "Lecture"
        dept_raw = r[6] if len(r) > 6 and r[6] else "General Subject"
        yr = int(r[7]) if len(r) > 7 and r[7] and r[7] != "NULL" else 1
        sem = int(r[8]) if len(r) > 8 and r[8] and r[8] != "NULL" else 1

        # Anomaly Fix 1: Collapse extra whitespace (IDs 471-536 e.g. MEE course descriptions)
        desc = " ".join(raw_desc.split())

        # Anomaly Fix 2: Clean subject codes (strip trailing periods, normalize internal space before lab suffixes L/D/F)
        code = " ".join(raw_code.split()).rstrip(".").strip()
        code = re.sub(r"\s+([LDF])$", r"\1", code)

        prog = DEPT_MAP.get(dept_raw.strip(), "GEN")
        is_lab = "LAB" in stype_raw.strip().upper()
        norm_type = "LAB" if is_lab else "LECTURE"

        # Anomaly Fix 3: Disambiguate duplicate lecture/lab subject codes in MFG & CPE
        if is_lab and (not (code.endswith("L") or code.endswith("D") or code.endswith("F")) or code in seen_codes):
            code += "L"

        seen_codes.add(code)

        is_gen = (prog == "GEN")
        req_grouping = is_lab or code.endswith("D") or code.endswith("F") or "DESIGN" in desc.upper() or "FIELD" in desc.upper()
        pref_session = "STRAIGHT" if norm_type == "LAB" else ("SPLIT" if (hours == 3 or units == 3) else "STRAIGHT")
        split_pref = "3_HOUR_BLOCK" if pref_session == "STRAIGHT" else "1.5_HOUR_SPLIT"

        subjects_list.append({
            "id": row_id,
            "code": code,
            "title": desc,
            "program": prog,
            "units": units,
            "hours_per_week": hours,
            "subject_type": norm_type,
            "year_level": yr,
            "semester": sem,
            "is_general": is_gen,
            "requires_grouping": req_grouping,
            "preferred_session_type": pref_session,
            "split_preference": split_pref,
        })

    return {
        "faculty": faculty_list,
        "sections": sections_list,
        "subjects": subjects_list,
    }


def load_and_clean_data2_sql(sql_file_path: Path = None) -> Dict[str, Any]:
    """
    Parse and clean data-2.sql (Single Source of Truth for Faculty, Sections, Subjects).
    Applies all canonical normalization, typo cleanup, deduplication, and department mapping.
    """
    if sql_file_path is None:
        sql_file_path = Path(__file__).resolve().parent / "data-2.sql"

    if not sql_file_path.exists():
        raise FileNotFoundError(f"data-2.sql not found at {sql_file_path}")

    sql_text = sql_file_path.read_text(encoding="utf-8")

    # 1. Clean Faculty (126 real BulSU COE faculty across 8 depts + General Engineering)
    raw_fac = parse_insert_tuples(sql_text, "coe facculty")
    faculty_list = []
    existing_emails = set()

    for r in raw_fac:
        row_id = int(r[0])
        name = r[1].strip()
        dept_raw = r[3].strip()
        prog = DEPT_MAP.get(dept_raw, "GEN")
        email = generate_faculty_email(name, prog, existing_emails)

        faculty_list.append({
            "id": row_id,
            "name": name,
            "email": email,
            "program": prog,
            "max_units": 21,
            "current_units": 0,
        })

    # 2. Clean Sections (90 sections across 8 departments, student_count = 40)
    raw_sec = parse_insert_tuples(sql_text, "coe sections")
    sections_list = []

    for r in raw_sec:
        row_id = int(r[0])
        sec_name = r[1].strip()
        dept_raw = r[2].strip()
        yr = int(r[3]) if len(r) > 3 and r[3] else 1
        prog = DEPT_MAP.get(dept_raw, "GEN")

        sections_list.append({
            "id": row_id,
            "name": sec_name,
            "program": prog,
            "year_level": yr,
            "student_count": 40,
        })

    # 3. Clean Subjects (429 subject range with deduplication and typo fixes)
    raw_subj = parse_insert_tuples(sql_text, "coe subjects")
    subjects_list = []
    seen_codes = set()

    for r in raw_subj:
        row_id = int(r[0])
        code = r[1].strip()
        title = r[2].strip()
        dept_raw = r[3].strip()
        yr = int(r[4]) if len(r) > 4 and r[4] and r[4] != "NULL" else 1
        sem = int(r[5]) if len(r) > 5 and r[5] and r[5] != "NULL" else 1
        units = int(r[6]) if len(r) > 6 and r[6] and r[6] != "NULL" else 3
        stype = (r[7] or "Lecture").strip().upper() if len(r) > 7 else "LECTURE"
        norm_type = "LAB" if "LAB" in stype else "LECTURE"
        hours = int(r[8]) if len(r) > 8 and r[8] and r[8] != "NULL" else (3 if norm_type == "LAB" else units)

        # Subject Fix 1: Fix ID 94 (CIV 414-CEM) department from 'General Subject' to 'Civil Engineering'
        if row_id == 94 or code == "CIV 414-CEM":
            dept_raw = "Civil Engineering"

        # Subject Fix 2: Deduplicate COE 104 (IDs 8 and 9 are both Calculus 2 in Year 1 Sem 2)
        if code == "COE 104":
            if "COE 104" in seen_codes:
                continue
            seen_codes.add("COE 104")
            title = "Calculus 2"

        # Subject Fix 3: Clean typos
        if code.startswith("MFE 201"):
            code = "MFE 201"
        title = title.replace("Microcontroller/Microproce ssor", "Microcontroller/Microprocessor")
        title = title.replace("Enegineering Management", "Engineering Management")
        title = title.replace("Desgin", "Design")

        prog = DEPT_MAP.get(dept_raw, "GEN")
        split_pref = "3_HOUR_BLOCK" if norm_type == "LAB" else "1.5_HOUR_SPLIT"

        subjects_list.append({
            "id": row_id,
            "code": code,
            "title": title,
            "program": prog,
            "year_level": yr,
            "semester": sem,
            "units": units,
            "subject_type": norm_type,
            "hours_per_week": hours,
            "split_preference": split_pref,
        })

    return {
        "faculty": faculty_list,
        "sections": sections_list,
        "subjects": subjects_list,
    }


def load_and_clean_sql_dump(sql_file_path: Path = None) -> Dict[str, Any]:
    """Parse and clean SQL dump data. Prioritizes data-final.sql with backward-compatible fallback to data-3.sql and data-2.sql."""
    base_dir = Path(__file__).resolve().parent
    if sql_file_path is None:
        p_final = base_dir / "data-final.sql"
        if p_final.exists():
            return load_and_clean_data_final_sql(p_final)
        p3 = base_dir / "data-3.sql"
        if p3.exists():
            return load_and_clean_data3_sql(p3)
        sql_file_path = base_dir / "data-2.sql"

    if str(sql_file_path).endswith("data-final.sql"):
        return load_and_clean_data_final_sql(sql_file_path)

    if str(sql_file_path).endswith("data-3.sql"):
        return load_and_clean_data3_sql(sql_file_path)

    if not sql_file_path.exists():
        raise FileNotFoundError(f"SQL dump not found at {sql_file_path}.")

    return load_and_clean_data2_sql(sql_file_path)

    # 1. Faculty Unification
    faculty_list: List[Dict[str, Any]] = []

    # CE Faculty
    # Raw values:
    # (1,'Jennie Roque','jennieroque@gmail.com',40,30),
    # (2,'Robert Chen','robert.chen@example.edu',40,27),
    # (3,'Marcus Vance','s.jenkins@fictionalcollege.edu',40,16),
    # (4,'Elena Rodriguez','mvance@dummy-university.edu',40,25),
    # (5,'Arthur Pendelton','elena.rodriguez@academia-test.edu',40,12),
    # (6,'Linda Al-Fayed','a.pendelton@example-state.edu',40,32),
    # (7,'Robert Chen','l.alfayed@tech-example.edu',40,26), -> Duplicate!
    # (8,'James Connor','j.connor@university-placeholder.edu',40,13);
    ce_email_fixes = {
        "Jennie Roque": "jennieroque@bulsu.edu.ph",
        "Robert Chen": "robert.chen@bulsu.edu.ph",
        "Marcus Vance": "mvance@bulsu.edu.ph",
        "Elena Rodriguez": "elena.rodriguez@bulsu.edu.ph",
        "Arthur Pendelton": "a.pendelton@bulsu.edu.ph",
        "Linda Al-Fayed": "l.alfayed@bulsu.edu.ph",
        "James Connor": "j.connor@bulsu.edu.ph",
    }
    seen_ce = set()
    for row in parse_insert_tuples(sql_text, "ce - facculty"):
        raw_id, raw_name, raw_email, raw_max, raw_cur = row[0], row[1], row[2], row[3], row[4]
        # Remove duplicate Robert Chen (id=7)
        if raw_name == "Robert Chen" and raw_name in seen_ce:
            continue
        seen_ce.add(raw_name)

        email = ce_email_fixes.get(raw_name, f"{raw_name.lower().replace(' ', '.')}@bulsu.edu.ph")
        faculty_list.append({
            "name": raw_name,
            "email": email,
            "program": "CE",
            "max_units": 21,
            "current_units": min(int(raw_cur), 21),
        })

    # ECE Faculty
    # Raw values swap Thomas Wright & Susan Mitchell
    for row in parse_insert_tuples(sql_text, "ece - facculty"):
        raw_id, raw_name, raw_email, raw_max, raw_cur = row[0], row[1], row[2], row[3], row[4]
        if raw_name == "Thomas Wright":
            email = "t.wright@bulsu.edu.ph"
        elif raw_name == "Susan Mitchell":
            email = "smitchell@bulsu.edu.ph"
        else:
            local = raw_email.split("@")[0] if "@" in raw_email else raw_name.lower().replace(" ", ".")
            email = f"{local}@bulsu.edu.ph"

        faculty_list.append({
            "name": raw_name,
            "email": email,
            "program": "ECE",
            "max_units": 21,
            "current_units": min(int(raw_cur), 21),
        })

    # MEE Faculty
    for row in parse_insert_tuples(sql_text, "mee - facculty"):
        raw_id, raw_name, raw_email, raw_max, raw_cur = row[0], row[1], row[2], row[3], row[4]
        local = raw_email.split("@")[0] if "@" in raw_email else raw_name.lower().replace(" ", ".")
        email = f"{local}@bulsu.edu.ph"
        faculty_list.append({
            "name": raw_name,
            "email": email,
            "program": "MEE",
            "max_units": 21,
            "current_units": min(int(raw_cur), 21),
        })

    # MFE Faculty
    for row in parse_insert_tuples(sql_text, "mfe - facculty"):
        raw_id, raw_name, raw_email, raw_max, raw_cur = row[0], row[1], row[2], row[3], row[4]
        local = raw_email.split("@")[0] if "@" in raw_email else raw_name.lower().replace(" ", ".")
        email = f"{local}@bulsu.edu.ph"
        faculty_list.append({
            "name": raw_name,
            "email": email,
            "program": "MFE",
            "max_units": 21,
            "current_units": min(int(raw_cur), 21),
        })

    # 2. Section Unification
    sections_list: List[Dict[str, Any]] = []

    def clean_section_name(raw_sec: str, prog: str) -> str:
        s = raw_sec.strip()
        s = s.replace(" - ", "-").replace(" -", "-").replace("- ", "-").replace(" ", "-")
        # Ensure format like CE-1A, ECE-1A, MEE-1A, MFE-1A
        return s

    for prog, tbl in [("CE", "ce - sections"), ("ECE", "ece - sections"), ("MEE", "mee - sections"), ("MFE", "mfe - sections")]:
        for row in parse_insert_tuples(sql_text, tbl):
            raw_sec, raw_yr, raw_cnt = row[1], int(row[2]), int(row[3])
            std_name = clean_section_name(raw_sec, prog)
            sections_list.append({
                "name": std_name,
                "program": prog,
                "year_level": raw_yr,
                "student_count": raw_cnt if raw_cnt > 0 else 42,
            })

    # 3. Subject Unification
    subjects_list: List[Dict[str, Any]] = []

    def clean_subject_title(title: str) -> str:
        t = title.replace("\n", " ").replace("\r", " ").strip()
        # Fix MFE typos
        t = re.sub(r"Microproce\s+ssor", "Microprocessor", t)
        t = re.sub(r"Manufacturin\s+Processes", "Manufacturing Processes", t)
        return " ".join(t.split())

    def clean_subject_code(code: str) -> str:
        c = code.replace("\n", "").replace("\r", "").strip()
        if c == "STS":
            return "STS 101"
        return c

    for prog, tbl in [("CE", "ce - subjects"), ("ECE", "ece - subjects"), ("MEE", "mee - subjects"), ("MFE", "mfe - subjects")]:
        for row in parse_insert_tuples(sql_text, tbl):
            raw_code, raw_title, raw_units, raw_type, raw_hrs, raw_yr, raw_sem = (
                row[1], row[2], int(row[3]), row[4], int(row[5]), int(row[6]), int(row[7])
            )
            code = clean_subject_code(raw_code)
            title = clean_subject_title(raw_title)

            # Normalize subject type
            stype = raw_type.strip().upper()
            if "LAB" in stype:
                norm_type = "LAB"
                split_pref = "3_HOUR_BLOCK"
            else:
                norm_type = "LECTURE"
                split_pref = "1.5_HOUR_SPLIT"

            subjects_list.append({
                "code": code,
                "title": title,
                "program": prog,
                "units": raw_units,
                "subject_type": norm_type,
                "hours_per_week": raw_hrs,
                "year_level": raw_yr,
                "semester": raw_sem,
                "split_preference": split_pref,
            })

    return {
        "faculty": faculty_list,
        "sections": sections_list,
        "subjects": subjects_list,
    }


if __name__ == "__main__":
    data = load_and_clean_sql_dump()
    print("Parsed Faculty count:", len(data["faculty"]))
    print("Parsed Sections count:", len(data["sections"]))
    print("Parsed Subjects count:", len(data["subjects"]))
    print("\nSample Faculty:", data["faculty"][:3])
    print("\nSample Sections:", data["sections"][:3])
    print("\nSample Subjects:", data["subjects"][:3])
