from uuid import uuid4

from app import app, get_student_skill_set
from database.db import get_db_session
from database.db import get_db_connection
from database.models import User
from database.seed import initialize_admin_account
from werkzeug.security import generate_password_hash


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


def test_home_page_loads():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    assert b'SkillBridge' in response.data


def test_login_page_loads():
    client = app.test_client()
    response = client.get('/login')
    assert response.status_code == 200
    assert b'Login' in response.data


def test_register_page_loads():
    client = app.test_client()
    response = client.get('/register')
    assert response.status_code == 200
    assert b'Register' in response.data


def test_demo_login_redirects_to_dashboard():
    client = app.test_client()
    response = post_form(client, '/login', {'email': 'student@skillbridge.demo', 'password': 'student123'}, follow_redirects=True)
    assert response.status_code == 200
    assert b'Welcome back' in response.data


def test_registration_for_public_roles_and_duplicate_email():
    client = app.test_client()
    roles = ['student', 'industry', 'academician', 'institution']
    random_email = f'{uuid4().hex}@test.com'
    for role in roles:
        email = f'{role}+{random_email}'
        response = post_form(client, '/register', data={
            'first_name': 'Phase',
            'last_name': role.title(),
            'email': email,
            'password': 'Password123',
            'role': role,
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Registration successful' in response.data

    duplicate_response = post_form(client, '/register', data={
        'first_name': 'Another',
        'last_name': 'User',
        'email': f'student+{random_email}',
        'password': 'Password123',
        'role': 'student',
    }, follow_redirects=True)
    assert duplicate_response.status_code == 200
    assert b'already exists' in duplicate_response.data.lower()

    admin_blocked = post_form(client, '/register', data={
        'first_name': 'Admin',
        'last_name': 'Attempt',
        'email': f'admin+{uuid4().hex}@test.com',
        'password': 'Password123',
        'role': 'admin',
    }, follow_redirects=True)
    assert admin_blocked.status_code == 200
    assert b'invalid role selected' in admin_blocked.data.lower()


def test_invalid_login_and_unauthorized_access():
    client = app.test_client()
    bad_login = post_form(client, '/login', {'email': 'student@skillbridge.demo', 'password': 'wrongpass'}, follow_redirects=True)
    assert bad_login.status_code == 200
    assert b'Invalid email or password' in bad_login.data

    login = post_form(client, '/login', {'email': 'student@skillbridge.demo', 'password': 'student123'}, follow_redirects=True)
    assert login.status_code == 200
    assert b'Welcome back' in login.data

    restricted = client.get('/industry-dashboard', follow_redirects=True)
    assert restricted.status_code == 200
    assert b'You do not have access' in restricted.data


def test_student_assessment_and_skill_analysis():
    client = app.test_client()
    post_form(client, '/login', {'email': 'student@skillbridge.demo', 'password': 'student123'}, follow_redirects=True)

    assessment_response = client.get('/skill-assessment')
    assert assessment_response.status_code == 200
    assert b'Skill readiness evaluation' in assessment_response.data

    submission = post_form(client, '/skill-assessment', data={
        'q1': 'Flask',
        'q2': 'To manage relational data',
        'q3': 'Client-side scripting for interactive web pages',
        'q4': 'Discuss concerns respectfully and align on a solution',
        'q5': 'Prioritizing tasks and setting realistic deadlines',
        'q6': '5 days',
    }, follow_redirects=True)
    assert submission.status_code == 200
    assert b'Assessment complete' in submission.data

    analysis = client.get('/skill-analysis')
    assert analysis.status_code == 200
    assert b'AI skill analysis' in analysis.data
    assert b'Compatibility score' in analysis.data


def test_weighted_skill_analysis_and_opportunity_matching():
    client = app.test_client()
    post_form(client, '/login', {'email': 'student@skillbridge.demo', 'password': 'student123'}, follow_redirects=True)

    analysis = client.get('/skill-analysis')
    assert analysis.status_code == 200
    assert b'Weighted compatibility' in analysis.data
    assert b'Recommended career roles' in analysis.data

    opportunities = client.get('/opportunities')
    assert opportunities.status_code == 200
    assert b'AI-driven opportunity recommendations' in opportunities.data
    assert b'Healthcare Data Analyst Intern' in opportunities.data
    assert b'Development demo record' in opportunities.data


def test_user_application_and_career_roadmap_progress():
    client = app.test_client()
    post_form(client, '/login', {'email': 'student@skillbridge.demo', 'password': 'student123'}, follow_redirects=True)

    conn = get_db_connection()
    conn.execute('DELETE FROM applications WHERE user_id = (SELECT id FROM users WHERE email = ?)', ('student@skillbridge.demo',))
    conn.commit()
    conn.close()

    apply_response = post_form(client, '/opportunities/1/apply', follow_redirects=True)
    assert apply_response.status_code == 200
    assert b'Application submitted successfully' in apply_response.data

    duplicate_response = post_form(client, '/opportunities/1/apply', follow_redirects=True)
    assert duplicate_response.status_code == 200
    assert b'already applied' in duplicate_response.data.lower()

    roadmap_page = client.get('/career-roadmap')
    assert roadmap_page.status_code == 200
    assert b'Career roadmap' in roadmap_page.data

    generate_response = post_form(client, '/career-roadmap', {'career_goal': 'Python Developer'}, follow_redirects=True)
    assert generate_response.status_code == 200
    assert b'Career roadmap' in generate_response.data

    conn = get_db_connection()
    try:
        latest = conn.execute(
            'SELECT id FROM career_roadmaps WHERE user_id = (SELECT id FROM users WHERE email = ?) ORDER BY created_at DESC LIMIT 1',
            ('student@skillbridge.demo',),
        ).fetchone()
    finally:
        conn.close()

    if latest is not None:
        update_response = post_form(client, '/career-roadmap', data={
            'action': 'update-progress',
            'roadmap_id': latest['id'],
            'step_index': 0,
            'progress': 70,
        }, follow_redirects=True)
        assert update_response.status_code == 200
        assert b'Roadmap progress updated successfully' in update_response.data


def test_logout_and_session_protection():
    client = app.test_client()
    post_form(client, '/login', {'email': 'industry@skillbridge.demo', 'password': 'industry123'}, follow_redirects=True)
    logout_response = post_form(client, '/logout', follow_redirects=True)
    assert logout_response.status_code == 200
    assert b'logged out successfully' in logout_response.data.lower()

    protected_dashboard = client.get('/industry-dashboard', follow_redirects=True)
    assert protected_dashboard.status_code == 200
    assert b'Please log in' in protected_dashboard.data
    assert client.get('/logout').status_code == 405


def test_role_dashboards_render_database_backed_pages():
    dashboards = {
        'student': ('student@skillbridge.demo', 'student123', '/student-dashboard'),
        'industry': ('industry@skillbridge.demo', 'industry123', '/industry-dashboard'),
        'academician': ('academician@skillbridge.demo', 'academician123', '/academician-dashboard'),
        'institution': ('institution@skillbridge.demo', 'institution123', '/institution-dashboard'),
    }
    admin_email = f'{uuid4().hex}@test.com'
    admin_password = f'Admin{uuid4().hex[:12]}1!'
    app.test_client().get('/health')
    admin = initialize_admin_account('Test', 'Admin', admin_email, admin_password)
    dashboards['admin'] = (admin_email, admin_password, '/admin-dashboard')
    try:
        for email, password, path in dashboards.values():
            client = app.test_client()
            login = post_form(
                client,
                '/login',
                {'email': email, 'password': password},
                follow_redirects=True,
            )
            assert login.status_code == 200
            response = client.get(path)
            assert response.status_code == 200
            assert b'4,200' not in response.data
            assert b'128' not in response.data
    finally:
        conn = get_db_connection()
        try:
            conn.execute('DELETE FROM users WHERE email = ?', (admin_email,))
            conn.commit()
        finally:
            conn.close()


def test_inactive_users_cannot_login_or_keep_an_existing_session():
    conn = get_db_connection()
    try:
        user = conn.execute(
            'SELECT id, is_active FROM users WHERE email = ?',
            ('student@skillbridge.demo',),
        ).fetchone()
        original_status = user['is_active']
        conn.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user['id'],))
        conn.commit()
    finally:
        conn.close()

    try:
        client = app.test_client()
        login = post_form(
            client,
            '/login',
            {'email': 'student@skillbridge.demo', 'password': 'student123'},
            follow_redirects=True,
        )
        assert login.status_code == 200
        assert b'Invalid email or password' in login.data

        with client.session_transaction() as session_data:
            session_data['user_id'] = user['id']
        protected = client.get('/student-dashboard', follow_redirects=True)
        assert protected.status_code == 200
        assert b'Please log in' in protected.data
    finally:
        conn = get_db_connection()
        try:
            conn.execute('UPDATE users SET is_active = ? WHERE id = ?', (original_status, user['id']))
            conn.commit()
        finally:
            conn.close()


def test_users_without_recorded_skills_get_no_synthetic_skills():
    email = f'{uuid4().hex}@test.com'
    db = get_db_session()
    user = User(
        first_name='Temporary',
        last_name='Student',
        email=email,
        password_hash=generate_password_hash('Temporary123'),
        role='student',
        is_active=True,
    )
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    conn = get_db_connection()
    try:
        assert get_student_skill_set(user_id) == []
    finally:
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
