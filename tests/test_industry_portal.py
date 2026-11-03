from io import BytesIO
from uuid import uuid4

from app import app
from database.db import get_db_connection


def post_form(client, path, data=None, **kwargs):
    with client.session_transaction() as session_data:
        token = session_data.get('csrf_token')
    if not token:
        client.get('/login')
        with client.session_transaction() as session_data:
            token = session_data['csrf_token']
    form_data = dict(data or {})
    form_data['csrf_token'] = token
    return client.post(path, data=form_data, **kwargs)


def create_account(client, role, email):
    response = post_form(
        client,
        '/register',
        {
            'first_name': 'Phase',
            'last_name': role.title(),
            'email': email,
            'password': 'Password123',
            'role': role,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    return post_form(
        client,
        '/login',
        {'email': email, 'password': 'Password123'},
        follow_redirects=True,
    )


def add_test_student_skills(email):
    conn = get_db_connection()
    try:
        student = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        skills = conn.execute(
            "SELECT id, name FROM skills WHERE name IN ('Python', 'SQL', 'Communication')"
        ).fetchall()
        for skill in skills:
            conn.execute(
                """
                INSERT OR REPLACE INTO student_skills (user_id, skill_id, proficiency, source)
                VALUES (?, ?, 90, 'test')
                """,
                (student['id'], skill['id']),
            )
        conn.execute(
            """
            INSERT INTO student_profiles (user_id, college, degree, branch, cgpa)
            VALUES (?, 'Test College', 'BSc', 'Computer Science', 8.5)
            ON CONFLICT(user_id) DO UPDATE SET cgpa = 8.5
            """,
            (student['id'],),
        )
        conn.commit()
        return student['id']
    finally:
        conn.close()


def create_company_opportunity(client, title='AI Data Intern'):
    response = post_form(
        client,
        '/industry/opportunities/new',
        {
            'title': title,
            'opportunity_type': 'Internship',
            'description': 'Build useful data tools and support applied digital health research.',
            'technical_skills': 'Python, SQL',
            'soft_skills': 'Communication',
            'qualification_requirements': 'Relevant undergraduate degree or equivalent experience.',
            'minimum_cgpa': '7.5',
            'location': 'Remote',
            'mode': 'Remote',
            'stipend': 'INR 15000 per month',
            'duration': '6 months',
            'openings': '2',
            'deadline': '2026-12-31',
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    conn = get_db_connection()
    try:
        row = conn.execute(
            'SELECT id FROM opportunities WHERE title = ? ORDER BY id DESC LIMIT 1',
            (title,),
        ).fetchone()
        return row['id']
    finally:
        conn.close()


def test_industry_role_protection_and_csrf():
    client = app.test_client()
    response = client.get('/industry-dashboard', follow_redirects=True)
    assert response.status_code == 200
    assert b'Please log in' in response.data

    post_form(
        client,
        '/login',
        {'email': 'student@skillbridge.demo', 'password': 'student123'},
        follow_redirects=True,
    )
    restricted = client.get('/industry/opportunities')
    assert restricted.status_code == 302

    missing_token = client.post('/industry/opportunities/new', data={'title': 'No token'})
    assert missing_token.status_code == 400


def test_industry_recruitment_workflow_and_ownership(tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, 'UPLOAD_FOLDER', str(tmp_path))
    token = uuid4().hex
    company_email = f'recruiter-{token}@example.test'
    student_one_email = f'applicant-one-{token}@example.test'
    student_two_email = f'applicant-two-{token}@example.test'
    other_company_email = f'other-recruiter-{token}@example.test'

    company_client = app.test_client()
    create_account(company_client, 'industry', company_email)
    profile_page = company_client.get('/industry/company-profile')
    assert profile_page.status_code == 200
    profile_update = post_form(
        company_client,
        '/industry/company-profile',
        {
            'company_name': 'Test Health Systems',
            'industry_sector': 'Digital Health',
            'company_description': 'A test organization building data products for healthcare research.',
            'website': 'https://test-health.example',
            'location': 'Remote',
            'contact_email': 'recruiting@test-health.example',
            'contact_phone': '1234567890',
            'logo': (BytesIO(b'\x89PNG\r\n\x1a\nlogo'), 'logo.png', 'image/png'),
        },
        follow_redirects=True,
    )
    assert profile_update.status_code == 200
    assert b'Company profile updated successfully' in profile_update.data

    request_verification = post_form(
        company_client,
        '/industry/company-profile/verification',
        follow_redirects=True,
    )
    assert b'pending until reviewed' in request_verification.data
    conn = get_db_connection()
    try:
        company = conn.execute('SELECT id FROM users WHERE email = ?', (company_email,)).fetchone()
        profile = conn.execute(
            'SELECT verification_status FROM industry_profiles WHERE user_id = ?',
            (company['id'],),
        ).fetchone()
    finally:
        conn.close()
    assert profile['verification_status'] == 'pending'
    conn = get_db_connection()
    try:
        company_profile = conn.execute(
            'SELECT logo_filename FROM industry_profiles WHERE user_id = ?',
            (company['id'],),
        ).fetchone()
    finally:
        conn.close()
    logo_response = company_client.get(
        f"/industry/company-logo/{company_profile['logo_filename']}"
    )
    assert logo_response.status_code == 200

    opportunity_id = create_company_opportunity(company_client, f'AI Data Intern {token}')
    edit_page = company_client.get(f'/industry/opportunities/{opportunity_id}/edit')
    assert edit_page.status_code == 200
    edit_response = post_form(
        company_client,
        f'/industry/opportunities/{opportunity_id}/edit',
        {
            'title': f'AI Data Intern Updated {token}',
            'opportunity_type': 'Internship',
            'description': 'Build useful data tools and support applied digital health research.',
            'technical_skills': 'Python, SQL',
            'soft_skills': 'Communication',
            'qualification_requirements': 'Relevant undergraduate degree or equivalent experience.',
            'minimum_cgpa': '7.5',
            'location': 'Hybrid',
            'mode': 'Hybrid',
            'stipend': 'INR 18000 per month',
            'duration': '6 months',
            'openings': '3',
            'deadline': '2026-12-31',
        },
        follow_redirects=True,
    )
    assert b'Opportunity updated successfully' in edit_response.data
    publish_response = post_form(
        company_client,
        f'/industry/opportunities/{opportunity_id}/status',
        {'status': 'published'},
        follow_redirects=True,
    )
    assert b'Opportunity published' in publish_response.data

    conn = get_db_connection()
    try:
        company = conn.execute('SELECT id FROM users WHERE email = ?', (company_email,)).fetchone()
        opportunity = conn.execute(
            'SELECT * FROM opportunities WHERE id = ?',
            (opportunity_id,),
        ).fetchone()
    finally:
        conn.close()
    assert opportunity['company_id'] == company['id']
    assert opportunity['status'] == 'published'

    other_company_client = app.test_client()
    create_account(other_company_client, 'industry', other_company_email)
    foreign_edit = other_company_client.get(f'/industry/opportunities/{opportunity_id}/edit')
    assert foreign_edit.status_code == 404
    foreign_status = post_form(
        other_company_client,
        f'/industry/opportunities/{opportunity_id}/status',
        {'status': 'closed'},
    )
    assert foreign_status.status_code == 404

    student_one = app.test_client()
    create_account(student_one, 'student', student_one_email)
    student_one_id = add_test_student_skills(student_one_email)
    profile_response = post_form(
        student_one,
        '/student-profile',
        {
            'college': 'Test College',
            'degree': 'BSc',
            'branch': 'Computer Science',
            'year_of_study': '3',
            'cgpa': '8.5',
            'interest_area': 'Digital health',
            'bio': 'Student candidate profile for the test recruitment workflow.',
            'resume': (BytesIO(b'%PDF-1.4 test resume'), 'resume.pdf', 'application/pdf'),
        },
        follow_redirects=True,
    )
    assert profile_response.status_code == 200
    student_two = app.test_client()
    create_account(student_two, 'student', student_two_email)
    student_two_id = add_test_student_skills(student_two_email)

    student_opportunities = student_one.get('/opportunities')
    assert student_opportunities.status_code == 200
    assert f'AI Data Intern Updated {token}'.encode() in student_opportunities.data
    assert b'Test Health Systems' in student_opportunities.data
    conn = get_db_connection()
    try:
        expired_titles = [
            row['title'] for row in conn.execute(
                "SELECT title FROM opportunities WHERE deadline < date('now') AND status = 'published'"
            ).fetchall()
        ]
    finally:
        conn.close()
    for expired_title in expired_titles:
        assert expired_title.encode() not in student_opportunities.data
    application_one = post_form(
        student_one,
        f'/opportunities/{opportunity_id}/apply',
        follow_redirects=True,
    )
    assert b'Application submitted successfully' in application_one.data
    application_two = post_form(
        student_two,
        f'/opportunities/{opportunity_id}/apply',
        follow_redirects=True,
    )
    assert b'Application submitted successfully' in application_two.data
    duplicate_application = post_form(
        student_one,
        f'/opportunities/{opportunity_id}/apply',
        follow_redirects=True,
    )
    assert b'already applied' in duplicate_application.data.lower()

    candidates = company_client.get('/industry/candidates?q=applicant-one')
    assert candidates.status_code == 200
    assert student_one_email.encode() in candidates.data
    assert b'AI skill compatibility' in candidates.data
    assert b'90%' in candidates.data
    resume_response = company_client.get(f'/private-resume/{student_one_id}')
    assert resume_response.status_code == 200
    assert resume_response.data.startswith(b'%PDF-')
    private_resume = other_company_client.get(f'/private-resume/{student_one_id}')
    assert private_resume.status_code == 404

    conn = get_db_connection()
    try:
        applications = conn.execute(
            'SELECT id, user_id FROM applications WHERE opportunity_id = ? ORDER BY id',
            (opportunity_id,),
        ).fetchall()
    finally:
        conn.close()
    application_by_student = {row['user_id']: row['id'] for row in applications}

    shortlist = post_form(
        company_client,
        f"/industry/applications/{application_by_student[student_one_id]}/status",
        {'status': 'Shortlisted'},
        follow_redirects=True,
    )
    assert b'Application marked shortlisted' in shortlist.data
    select_candidate = post_form(
        company_client,
        f"/industry/applications/{application_by_student[student_one_id]}/status",
        {'status': 'Selected'},
        follow_redirects=True,
    )
    assert b'Application marked selected' in select_candidate.data
    reject_candidate = post_form(
        company_client,
        f"/industry/applications/{application_by_student[student_two_id]}/status",
        {'status': 'Rejected'},
        follow_redirects=True,
    )
    assert b'Application marked rejected' in reject_candidate.data

    filtered_candidates = company_client.get('/industry/candidates?status=Rejected&sort=compatibility')
    assert filtered_candidates.status_code == 200
    assert student_two_email.encode() in filtered_candidates.data
    assert student_one_email.encode() not in filtered_candidates.data

    conn = get_db_connection()
    try:
        notification_count = conn.execute(
            'SELECT COUNT(*) FROM notifications WHERE user_id = ?',
            (student_one_id,),
        ).fetchone()[0]
        history_count = conn.execute(
            """
            SELECT COUNT(*) FROM application_status_history
            WHERE application_id = ?
            """,
            (application_by_student[student_one_id],),
        ).fetchone()[0]
    finally:
        conn.close()
    assert notification_count >= 2
    assert history_count >= 3
    student_dashboard = student_one.get('/student-dashboard')
    assert student_dashboard.status_code == 200
    assert f'AI Data Intern Updated {token}'.encode() in student_dashboard.data
    assert b'now Selected' in student_dashboard.data

    analytics = company_client.get('/industry/analytics')
    assert analytics.status_code == 200
    assert b'Application status distribution' in analytics.data
    dashboard = company_client.get('/industry-dashboard')
    assert dashboard.status_code == 200
    assert b'Total applications' in dashboard.data

    close_response = post_form(
        company_client,
        f'/industry/opportunities/{opportunity_id}/status',
        {'status': 'closed'},
        follow_redirects=True,
    )
    assert b'Opportunity closed' in close_response.data
    third_student_email = f'applicant-three-{token}@example.test'
    student_three = app.test_client()
    create_account(student_three, 'student', third_student_email)
    add_test_student_skills(third_student_email)
    closed_application = post_form(
        student_three,
        f'/opportunities/{opportunity_id}/apply',
        follow_redirects=True,
    )
    assert b'closed, expired, or unavailable' in closed_application.data

    other_company_status = post_form(
        other_company_client,
        f"/industry/applications/{application_by_student[student_one_id]}/status",
        {'status': 'Rejected'},
        follow_redirects=True,
    )
    assert b'Application not found for your company' in other_company_status.data
