"""COE SYNC 2026 - SQL Dump Parser & Data Migration Utility
Parses raw coe-database.sql dump with 12 fragmented department tables,
cleans corrupted faculty, sections, and subjects, and yields unified datasets.
"""

import re
from pathlib import Path
from typing import Dict, List, Any


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


def load_and_clean_sql_dump(sql_file_path: Path = None) -> Dict[str, Any]:
    """Parse and clean all 12 department tables from coe-database.sql."""
    if sql_file_path is None:
        sql_file_path = Path(__file__).resolve().parent / "coe-database.sql"

    if not sql_file_path.exists():
        raise FileNotFoundError(f"SQL dump file not found at {sql_file_path}")

    sql_text = sql_file_path.read_text(encoding="utf-8")

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
