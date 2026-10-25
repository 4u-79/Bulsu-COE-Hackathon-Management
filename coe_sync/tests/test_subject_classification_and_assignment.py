import pytest
from app import create_app
from models import db, Subject, Faculty, User


@pytest.fixture
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        # Seed test subjects
        s1 = Subject(code="COE 100", title="Intro to Engineering", program="GEN", units=3, subject_type="LECTURE", hours_per_week=3)
        s2 = Subject(code="ETH 101", title="Ethics", program="GEN", units=3, subject_type="LECTURE", hours_per_week=3)
        s3 = Subject(code="MEE 101", title="Thermodynamics 1", program="MEE", units=3, subject_type="LECTURE", hours_per_week=3)
        s4 = Subject(code="COE 201", title="Engineering Mechanics", program="GEN", units=3, subject_type="LECTURE", hours_per_week=3)
        s5 = Subject(code="MEE 300", title="Machine Design 1", program="MEE", units=3, subject_type="LECTURE", hours_per_week=3)
        s6 = Subject(code="MEE 400", title="Plant Engineering", program="MEE", units=3, subject_type="LECTURE", hours_per_week=3)
        s7 = Subject(code="PE 10", title="Physical Education 1", program="GEN", units=2, subject_type="LECTURE", hours_per_week=2, year_level=1)
        db.session.add_all([s1, s2, s3, s4, s5, s6, s7])
        db.session.commit()

        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_subject_computed_year_and_classification(client):
    """Test computed year level and Major vs Minor classification rules."""
    s_coe100 = Subject.query.filter_by(code="COE 100").first()
    s_eth101 = Subject.query.filter_by(code="ETH 101").first()
    s_mee101 = Subject.query.filter_by(code="MEE 101").first()
    s_coe201 = Subject.query.filter_by(code="COE 201").first()
    s_mee300 = Subject.query.filter_by(code="MEE 300").first()
    s_mee400 = Subject.query.filter_by(code="MEE 400").first()
    s_pe10 = Subject.query.filter_by(code="PE 10").first()

    # Year levels
    assert s_coe100.computed_year_level == 1
    assert s_eth101.computed_year_level == 1
    assert s_mee101.computed_year_level == 1
    assert s_coe201.computed_year_level == 2
    assert s_mee300.computed_year_level == 3
    assert s_mee400.computed_year_level == 4
    assert s_pe10.computed_year_level == 1

    # Classifications:
    # 1st/2nd year COE -> MAJOR
    assert s_coe100.classification == "MAJOR"
    assert s_coe201.classification == "MAJOR"

    # 1st/2nd year GEN non-COE -> MINOR
    assert s_eth101.classification == "MINOR"
    assert s_pe10.classification == "MINOR"

    # 1st/2nd year Department -> MAJOR
    assert s_mee101.classification == "MAJOR"

    # 3rd & 4th year -> MAJOR
    assert s_mee300.classification == "MAJOR"
    assert s_mee400.classification == "MAJOR"


def test_api_subjects_classification_filtering(client):
    """Test filtering by classification (MAJOR vs MINOR) on /api/subjects."""
    # All subjects
    res_all = client.get("/api/subjects")
    assert res_all.status_code == 200
    assert res_all.get_json()["count"] == 7

    # Major subjects: COE 100, MEE 101, COE 201, MEE 300, MEE 400 = 5
    res_majors = client.get("/api/subjects?classification=MAJOR")
    assert res_majors.status_code == 200
    majors_data = res_majors.get_json()
    assert majors_data["count"] == 5
    major_codes = {s["code"] for s in majors_data["data"]}
    assert major_codes == {"COE 100", "MEE 101", "COE 201", "MEE 300", "MEE 400"}

    # Minor subjects: ETH 101, PE 10 = 2
    res_minors = client.get("/api/subjects?classification=MINOR")
    assert res_minors.status_code == 200
    minors_data = res_minors.get_json()
    assert minors_data["count"] == 2
    minor_codes = {s["code"] for s in minors_data["data"]}
    assert minor_codes == {"ETH 101", "PE 10"}


def test_minor_subjects_cannot_be_assigned_to_faculty(client):
    """Test that minor subjects are excluded from assignable options and rejected on assignment."""
    from models import Section, Room

    # Setup faculty, section, and room
    fac = Faculty(name="Engr. John Smith", email="jsmith@bulsu.edu.ph", program="MEE", max_units=21)
    sec = Section(name="MEE-1A", program="MEE", year_level=1)
    rm = Room(room_code="COE-201", room_type="LECTURE", capacity=40, is_available=True)
    admin_user = User(username="admin_test", role="ADMIN")
    admin_user.set_password("Admin@123")

    db.session.add_all([fac, sec, rm, admin_user])
    db.session.commit()

    # Authenticate as ADMIN
    with client.session_transaction() as sess:
        sess["user_id"] = admin_user.id
        sess["username"] = admin_user.username
        sess["role"] = "ADMIN"
        sess["active_role"] = "ADMIN"

    # 1. Verify assignable options excludes Minor subjects
    res_opt = client.get(f"/api/faculty/{fac.id}/assignable-options")
    assert res_opt.status_code == 200
    opt_data = res_opt.get_json()["data"]
    assignable_subjects = opt_data["subjects"]
    for s in assignable_subjects:
        assert s["classification"] == "MAJOR"
    assignable_codes = {s["code"] for s in assignable_subjects}
    assert "ETH 101" not in assignable_codes
    assert "PE 10" not in assignable_codes
    assert "MEE 101" in assignable_codes

    # 2. Attempt assigning a Minor subject (ETH 101) -> Must fail with 400
    s_eth = Subject.query.filter_by(code="ETH 101").first()
    res_assign_minor = client.post(
        f"/api/faculty/{fac.id}/assign-subject",
        json={
            "subject_id": s_eth.id,
            "section_id": sec.id,
            "room_id": rm.id,
            "day_of_week": "MON",
            "start_time": "08:00",
            "end_time": "11:00",
        },
    )
    assert res_assign_minor.status_code == 400
    assert "Minor subject" in res_assign_minor.get_json()["error"]

    # 3. Assigning a Major subject (MEE 101) -> Must succeed
    s_mee = Subject.query.filter_by(code="MEE 101").first()
    res_assign_major = client.post(
        f"/api/faculty/{fac.id}/assign-subject",
        json={
            "subject_id": s_mee.id,
            "section_id": sec.id,
            "room_id": rm.id,
            "day_of_week": "MON",
            "start_time": "08:00",
            "end_time": "11:00",
        },
    )
    assert res_assign_major.status_code == 201
    assert res_assign_major.get_json()["status"] == "success"

