import os
import re
from datetime import datetime
from uuid import uuid4

import streamlit as st


def _load_streamlit_secrets():
    try:
        configured = st.secrets
        for key in (
            'SKILLBRIDGE_ENV',
            'SKILLBRIDGE_SECRET_KEY',
            'SKILLBRIDGE_DATABASE_URL',
            'SKILLBRIDGE_DEMO_DATA',
            'SKILLBRIDGE_UPLOAD_FOLDER',
        ):
            if key in configured:
                os.environ[key] = str(configured[key])
    except st.errors.StreamlitSecretNotFoundError:
        return


_load_streamlit_secrets()
os.environ.setdefault('SKILLBRIDGE_DEMO_DATA', 'false')

from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db_connection, get_db_session, init_db, seed_demo_data
from database.models import User
from modules.academician import get_academician_summary
from modules.admin import get_admin_summary
from modules.career_roadmap import (
    generate_roadmap_for_goal,
    get_latest_roadmap_for_user,
    save_roadmap_for_user,
    update_roadmap_progress,
)
from modules.industry import (
    APPLICATION_STATUSES,
    ensure_company_profile,
    get_company_candidates,
    get_company_dashboard_data,
    get_company_opportunities,
    get_industry_analytics,
    update_application_status,
)
from modules.institution import get_institution_summary
from modules.opportunity import (
    apply_for_opportunity,
    get_opportunity_catalog,
    get_recommended_opportunities,
)
from modules.skill_analyzer import analyze_skills
from app import ASSESSMENT_QUESTIONS


st.set_page_config(
    page_title='SkillBridge',
    page_icon=':material/hub:',
    layout='wide',
)

@st.cache_resource
def initialize_database():
    init_db()
    if os.environ.get('SKILLBRIDGE_DEMO_DATA', 'false').strip().lower() == 'true':
        seed_demo_data()


initialize_database()


def _query(sql, parameters=()):
    conn = get_db_connection()
    try:
        return [dict(row) for row in conn.execute(sql, parameters).fetchall()]
    finally:
        conn.close()


def _execute(sql, parameters=()):
    conn = get_db_connection()
    try:
        conn.execute(sql, parameters)
        conn.commit()
    finally:
        conn.close()


def _current_user():
    user_id = st.session_state.get('user_id')
    if not user_id:
        return None
    db = get_db_session()
    try:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if user is None or not user.is_active:
            st.session_state.pop('user_id', None)
            return None
        return user.to_dict()
    finally:
        db.close()


def _skill_rows(user_id):
    return _query(
        """
        SELECT s.id, s.name, s.category, ss.proficiency, ss.source
        FROM student_skills ss JOIN skills s ON s.id = ss.skill_id
        WHERE ss.user_id = ? ORDER BY s.name
        """,
        (user_id,),
    )


def _notifications(user_id):
    rows = _query(
        """
        SELECT title, message, created_at, is_read FROM notifications
        WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 10
        """,
        (user_id,),
    )
    if not rows:
        st.info('No notifications yet.')
        return
    for item in rows:
        with st.container(border=True):
            st.markdown(f"**{item['title']}**")
            st.write(item['message'])
            st.caption(item['created_at'])


def _login_page():
    st.title('SkillBridge')
    st.subheader('Sign in to your collaboration portal')
    login_tab, register_tab = st.tabs(['Log in', 'Create account'])

    with login_tab:
        with st.form('login_form'):
            email = st.text_input('Email', max_chars=255).strip().lower()
            password = st.text_input('Password', type='password')
            submitted = st.form_submit_button('Log in', type='primary')
        if submitted:
            if not email or not password:
                st.error('Enter both email and password.')
            else:
                db = get_db_session()
                try:
                    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
                    if user and user.is_active and check_password_hash(user.password_hash, password):
                        st.session_state.user_id = user.id
                        st.rerun()
                    st.error('Invalid email or password.')
                finally:
                    db.close()

    with register_tab:
        with st.form('register_form'):
            first_name = st.text_input('First name', max_chars=100).strip()
            last_name = st.text_input('Last name', max_chars=100).strip()
            email = st.text_input('Email address', max_chars=255).strip().lower()
            role = st.selectbox('Account type', ['student', 'industry', 'academician', 'institution'])
            password = st.text_input('Password', type='password')
            confirmation = st.text_input('Confirm password', type='password')
            submitted = st.form_submit_button('Create account', type='primary')
        if submitted:
            valid_email = bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email))
            valid_password = (
                len(password) >= 8
                and re.search(r'[A-Za-z]', password)
                and re.search(r'\d', password)
            )
            if not first_name or not last_name or not valid_email:
                st.error('Enter a first name, last name, and valid email address.')
            elif password != confirmation or not valid_password:
                st.error('Passwords must match and include at least 8 characters, a letter, and a number.')
            else:
                db = get_db_session()
                try:
                    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
                    if existing:
                        st.error('An account with this email already exists.')
                    else:
                        user = User(
                            first_name=first_name,
                            last_name=last_name,
                            email=email,
                            password_hash=generate_password_hash(password),
                            role=role,
                            is_active=True,
                        )
                        db.add(user)
                        db.commit()
                        if role == 'industry':
                            ensure_company_profile(user.id)
                        st.success('Account created. Log in to continue.')
                finally:
                    db.close()


def _student_dashboard(user):
    st.title(f"Welcome, {user['first_name']}")
    skills = _skill_rows(user['id'])
    analysis = analyze_skills(skills)
    applications = _query(
        'SELECT COUNT(*) AS total FROM applications WHERE user_id = ?',
        (user['id'],),
    )[0]['total']
    first, second, third = st.columns(3)
    first.metric('Skills in profile', len(skills), border=True)
    second.metric('Skill compatibility', f"{analysis['compatibility']}%", border=True)
    third.metric('Applications', applications, border=True)
    st.subheader('Skill analysis')
    if analysis['chart_labels']:
        st.bar_chart(
            [
                {'Skill': label, 'Proficiency': value}
                for label, value in zip(analysis['chart_labels'], analysis['chart_values'])
            ],
            x='Skill',
            y='Proficiency',
            alt='Current proficiency by skill',
        )
    if analysis['missing']:
        st.caption('Skills to strengthen: ' + ', '.join(analysis['missing']))
    st.subheader('Recent notifications')
    _notifications(user['id'])


def _student_profile(user):
    st.title('Student profile')
    existing = _query('SELECT * FROM student_profiles WHERE user_id = ?', (user['id'],))
    profile = existing[0] if existing else {}
    with st.form('student_profile'):
        college = st.text_input('Institution', value=profile.get('college') or '', max_chars=250)
        degree = st.text_input('Degree', value=profile.get('degree') or '', max_chars=250)
        branch = st.text_input('Department / branch', value=profile.get('branch') or '', max_chars=250)
        year = st.number_input('Year of study', min_value=1, max_value=10, value=int(profile.get('year_of_study') or 1))
        cgpa = st.number_input('CGPA (0–10)', min_value=0.0, max_value=10.0, value=float(profile.get('cgpa') or 0.0), step=0.1)
        interest = st.text_input('Career interests', value=profile.get('interest_area') or '', max_chars=250)
        bio = st.text_area('About you', value=profile.get('bio') or '', max_chars=3000)
        resume = st.file_uploader('Resume (PDF, max 8 MB)', type=['pdf'])
        submitted = st.form_submit_button('Save profile', type='primary')
    if submitted:
        resume_name = profile.get('resume_filename')
        resume_data = profile.get('resume_data')
        if resume is not None:
            data = resume.getvalue()
            if len(data) > 8 * 1024 * 1024:
                st.error('Resume exceeds the 8 MB file size limit.')
                return
            if not data.startswith(b'%PDF-'):
                st.error('Resume file is not a valid PDF.')
                return
            resume_name = f'{uuid4().hex}.pdf'
            resume_data = data
        if any(len(value) > 250 for value in (college, degree, branch, interest)) or len(bio) > 3000:
            st.error('Profile fields exceed the allowed length.')
            return
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO student_profiles
                    (user_id, college, degree, branch, year_of_study, cgpa, bio, interest_area,
                     resume_filename, resume_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET college=excluded.college,
                    degree=excluded.degree, branch=excluded.branch,
                    year_of_study=excluded.year_of_study, cgpa=excluded.cgpa,
                    bio=excluded.bio, interest_area=excluded.interest_area,
                    resume_filename=excluded.resume_filename, resume_data=excluded.resume_data
                """,
                (user['id'], college.strip(), degree.strip(), branch.strip(), int(year), float(cgpa), bio.strip(), interest.strip(), resume_name, resume_data),
            )
            conn.commit()
        finally:
            conn.close()
        st.success('Profile saved.')
    if profile.get('resume_data'):
        st.download_button(
            'Download my resume',
            bytes(profile['resume_data']),
            file_name='resume.pdf',
            mime='application/pdf',
        )
    skills = _skill_rows(user['id'])
    st.subheader('Skills')
    if skills:
        st.dataframe(skills, hide_index=True, alt='Your skills and proficiency')
    available = _query('SELECT id, name FROM skills ORDER BY name')
    if available:
        skill_options = {row['name']: row['id'] for row in available}
        with st.form('add_skill'):
            skill_name = st.selectbox('Add a skill', list(skill_options))
            proficiency = st.slider('Proficiency', 0, 100, 50)
            skill_saved = st.form_submit_button('Save skill')
        if skill_saved:
            _execute(
                """
                INSERT INTO student_skills (user_id, skill_id, proficiency, source)
                VALUES (?, ?, ?, 'self-reported')
                ON CONFLICT(user_id, skill_id) DO UPDATE SET proficiency=excluded.proficiency,
                    source=excluded.source
                """,
                (user['id'], skill_options[skill_name], proficiency),
            )
            st.success('Skill saved.')
            st.rerun()
    with st.expander('Add a skill not listed'):
        with st.form('custom_skill'):
            custom_name = st.text_input('Skill name', max_chars=100).strip()
            custom_category = st.selectbox('Category', ['Technical', 'Soft', 'Research', 'Healthcare'])
            custom_proficiency = st.slider('Proficiency level', 0, 100, 50)
            custom_saved = st.form_submit_button('Add skill')
        if custom_saved:
            if not custom_name:
                st.error('Enter a skill name.')
            else:
                conn = get_db_connection()
                try:
                    conn.execute(
                        'INSERT INTO skills (name, category) VALUES (?, ?) ON CONFLICT(name) DO NOTHING',
                        (custom_name, custom_category),
                    )
                    skill_id = conn.execute('SELECT id FROM skills WHERE name = ?', (custom_name,)).fetchone()['id']
                    conn.execute(
                        """
                        INSERT INTO student_skills (user_id, skill_id, proficiency, source)
                        VALUES (?, ?, ?, 'self-reported')
                        ON CONFLICT(user_id, skill_id) DO UPDATE SET proficiency=excluded.proficiency
                        """,
                        (user['id'], skill_id, custom_proficiency),
                    )
                    conn.commit()
                finally:
                    conn.close()
                st.success('Skill added.')
                st.rerun()


def _student_opportunities(user):
    st.title('Industry opportunities')
    skills = _skill_rows(user['id'])
    rows = get_recommended_opportunities(skills, user['id'])
    query = st.text_input('Search opportunities', type='search')
    type_filter = st.selectbox('Opportunity type', ['All'] + sorted({row['type'] for row in rows}))
    visible = [
        row for row in rows
        if (not query or query.casefold() in row['title'].casefold() or query.casefold() in row['company'].casefold())
        and (type_filter == 'All' or row['type'] == type_filter)
    ]
    if not visible:
        st.info('No opportunities match these filters.')
    for item in visible:
        with st.container(border=True):
            st.subheader(item['title'])
            st.caption(f"{item['company']} · {item['type']} · {item['location']} · Deadline: {item['deadline']}")
            st.write(item['description'] or 'No description provided.')
            st.metric('Skill compatibility', f"{item['compatibility']}%")
            st.caption('Required skills: ' + (', '.join(item['required_skills']) or 'Not specified'))
            if item.get('is_sample'):
                st.caption('Development sample record')
            if st.button('Apply', key=f"apply_{item['id']}", disabled=item.get('is_sample', False)):
                outcome = apply_for_opportunity(user['id'], item['id'])
                (st.success if outcome['success'] else st.warning)(outcome['message'])


def _student_applications(user):
    st.title('My applications')
    rows = _query(
        """
        SELECT a.id, o.title, o.opportunity_type, ip.company_name, a.status, a.applied_at
        FROM applications a JOIN opportunities o ON o.id = a.opportunity_id
        LEFT JOIN industry_profiles ip ON ip.user_id = o.company_id
        WHERE a.user_id = ? ORDER BY a.applied_at DESC
        """,
        (user['id'],),
    )
    if rows:
        st.dataframe(rows, hide_index=True, alt='Application history')
    else:
        st.info('You have not applied to any opportunities yet.')


def _student_assessment(user):
    st.title('Skill assessment')
    with st.form('skill_assessment'):
        answers = {}
        for question in ASSESSMENT_QUESTIONS:
            answers[question['id']] = st.radio(
                question['question'],
                question['options'],
                key=f"assessment_{question['id']}",
            )
        submitted = st.form_submit_button('Submit assessment', type='primary')
    if submitted:
        score = sum(
            answers[item['id']] == item['answer']
            for item in ASSESSMENT_QUESTIONS
        )
        conn = get_db_connection()
        try:
            assessment = conn.execute(
                'INSERT INTO assessments (user_id, title, category, score) VALUES (?, ?, ?, ?)',
                (user['id'], 'Student Skill Assessment', 'technical', score),
            )
            for question in ASSESSMENT_QUESTIONS:
                conn.execute(
                    """
                    INSERT INTO assessment_answers
                        (assessment_id, question, selected_option, is_correct)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        assessment.lastrowid,
                        question['question'],
                        answers[question['id']],
                        int(answers[question['id']] == question['answer']),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        st.success(f'Assessment complete: {score}/{len(ASSESSMENT_QUESTIONS)}.')
        st.rerun()
    history = _query(
        'SELECT title, category, score, created_at FROM assessments WHERE user_id = ? ORDER BY created_at DESC',
        (user['id'],),
    )
    if history:
        st.subheader('Assessment history')
        st.dataframe(history, hide_index=True, alt='Past assessment results')


def _student_roadmap(user):
    st.title('Career roadmap')
    roles = [
        'Full Stack Developer', 'Python Developer', 'AI/ML Engineer', 'Data Analyst',
        'Healthcare Data Analyst', 'Medical AI Developer', 'Biomedical Software Developer',
        'Digital Health Specialist', 'Clinical Research Data Analyst',
    ]
    current = get_latest_roadmap_for_user(user['id'])
    with st.form('roadmap_form'):
        goal = st.selectbox('Career goal', roles, index=roles.index(current['career_goal']) if current and current['career_goal'] in roles else 0)
        create = st.form_submit_button('Create roadmap', type='primary')
    if create:
        skills = _skill_rows(user['id'])
        analysis = analyze_skills(skills)
        steps = generate_roadmap_for_goal(
            goal,
            [row['name'] for row in skills],
            analysis['missing'],
        )
        save_roadmap_for_user(user['id'], goal, steps)
        st.rerun()
    current = get_latest_roadmap_for_user(user['id'])
    if not current:
        st.info('Create a roadmap to see your learning steps.')
        return
    st.progress(current['progress'] / 100, text=f"Overall progress: {current['progress']}%")
    for index, step in enumerate(current['roadmap']):
        with st.container(border=True):
            st.markdown(f"**{step['learning_step']}** · {step['skill_to_develop']}")
            st.write(step['recommended_activity'])
            progress = st.slider('Step progress', 0, 100, int(step.get('progress', 0)), key=f"roadmap_{current['id']}_{index}")
            if st.button('Save progress', key=f"save_roadmap_{index}"):
                if update_roadmap_progress(user['id'], current['id'], index, progress):
                    st.success('Progress saved.')
                    st.rerun()


def _industry_dashboard(user):
    ensure_company_profile(user['id'])
    dashboard = get_company_dashboard_data(user['id'])
    st.title(f"Industry dashboard · {user['first_name']}")
    if dashboard['profile']:
        st.caption(f"Verification: {dashboard['summary']['verification_status']}")
    metric_names = [
        ('Opportunities', 'total_opportunities'),
        ('Active internships', 'active_internships'),
        ('Applications', 'total_applications'),
        ('Selected', 'selected'),
    ]
    for label, key in metric_names:
        st.metric(label, dashboard['summary'][key], border=True)
    st.subheader('Recent applications')
    if dashboard['recent_applications']:
        st.dataframe(dashboard['recent_applications'], hide_index=True, alt='Recent candidate applications')
    else:
        st.info('No applications received yet.')
    st.subheader('Notifications')
    _notifications(user['id'])


def _industry_profile(user):
    st.title('Company profile')
    ensure_company_profile(user['id'])
    profile = _query('SELECT * FROM industry_profiles WHERE user_id = ?', (user['id'],))[0]
    with st.form('company_profile'):
        company = st.text_input('Company name', value=profile.get('company_name') or '', max_chars=150)
        sector = st.text_input('Industry sector', value=profile.get('industry_sector') or '', max_chars=100)
        website = st.text_input('Website', value=profile.get('website') or '', max_chars=255)
        location = st.text_input('Location', value=profile.get('location') or '', max_chars=150)
        email = st.text_input('Contact email', value=profile.get('contact_email') or '', max_chars=255)
        phone = st.text_input('Contact phone', value=profile.get('contact_phone') or '', max_chars=30)
        description = st.text_area('Company description', value=profile.get('company_description') or '', max_chars=3000)
        saved = st.form_submit_button('Save company profile', type='primary')
    if saved:
        if not company.strip() or len(description) > 3000:
            st.error('Company name is required and description must be within 3000 characters.')
        elif email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email.strip()):
            st.error('Enter a valid contact email.')
        else:
            _execute(
                """
                UPDATE industry_profiles SET company_name=?, industry_sector=?, website=?,
                    location=?, contact_email=?, contact_phone=?, company_description=?
                WHERE user_id=?
                """,
                (company.strip(), sector.strip(), website.strip(), location.strip(), email.strip(), phone.strip(), description.strip(), user['id']),
            )
            st.success('Company profile updated.')
            st.rerun()
    st.write('Verification status:', profile['verification_status'])
    if st.button('Request company verification', disabled=profile['verification_status'] == 'verified'):
        _execute(
            "UPDATE industry_profiles SET verification_status='pending', verification_requested_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (user['id'],),
        )
        _execute(
            "INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)",
            (user['id'], 'Verification request submitted', 'Your company verification request is pending review.'),
        )
        st.success('Verification request submitted.')


def _industry_opportunities(user):
    st.title('Manage opportunities')
    opportunities = get_company_opportunities(user['id'])
    if opportunities:
        st.dataframe(opportunities, hide_index=True, alt='Your published and draft opportunities')
    with st.expander('Create opportunity'):
        with st.form('new_opportunity'):
            title = st.text_input('Title', max_chars=150)
            kind = st.selectbox('Type', ['Internship', 'Full-time job', 'Apprenticeship', 'Live project', 'Training'])
            description = st.text_area('Description', max_chars=5000)
            location = st.text_input('Location', max_chars=150)
            mode = st.selectbox('Mode', ['On-site', 'Remote', 'Hybrid'])
            duration = st.text_input('Duration', max_chars=100)
            stipend = st.text_input('Stipend', max_chars=100)
            deadline = st.date_input('Application deadline')
            skills = st.text_input('Required skills (comma separated)', max_chars=500)
            submitted = st.form_submit_button('Save as draft', type='primary')
        if submitted:
            if not title.strip() or not description.strip():
                st.error('Title and description are required.')
            elif deadline < datetime.now().date():
                st.error('Deadline must be today or later.')
            else:
                conn = get_db_connection()
                try:
                    cursor = conn.execute(
                        """
                        INSERT INTO opportunities
                            (company_id, title, opportunity_type, description, location, mode,
                             duration, stipend, deadline, status, is_approved)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0)
                        """,
                        (user['id'], title.strip(), kind, description.strip(), location.strip(), mode, duration.strip(), stipend.strip(), deadline.isoformat()),
                    )
                    opportunity_id = cursor.lastrowid
                    for skill in {value.strip() for value in skills.split(',') if value.strip()}:
                        conn.execute(
                            "INSERT INTO opportunity_skills (opportunity_id, skill, skill_category, is_required) VALUES (?, ?, 'technical', 1)",
                            (opportunity_id, skill),
                        )
                    conn.commit()
                finally:
                    conn.close()
                st.success('Opportunity saved as a draft.')
                st.rerun()
    for item in opportunities:
        if item['status'] == 'draft' and st.button('Publish', key=f"publish_{item['id']}"):
            _execute("UPDATE opportunities SET status='published', is_approved=1 WHERE id=? AND company_id=?", (item['id'], user['id']))
            st.success('Opportunity published.')
            st.rerun()
        if item['status'] == 'published' and st.button('Close', key=f"close_{item['id']}"):
            _execute("UPDATE opportunities SET status='closed' WHERE id=? AND company_id=?", (item['id'], user['id']))
            st.rerun()


def _industry_applications(user):
    st.title('Candidate applications')
    search = st.text_input('Search candidates', type='search')
    status = st.selectbox('Application status', ['All', *APPLICATION_STATUSES])
    rows = get_company_candidates(
        user['id'],
        search=search.strip(),
        status='' if status == 'All' else status,
    )
    if not rows:
        st.info('No applications match this search.')
        return
    for item in rows:
        with st.container(border=True):
            st.subheader(f"{item['first_name']} {item['last_name']}")
            st.caption(f"{item['title']} · {item['status']} · Applied {item['applied_at']}")
            if item.get('skills'):
                st.write('Skills: ' + ', '.join(item['skills']))
            allowed = {
                'Applied': ['Shortlisted', 'Rejected', 'Selected'],
                'Shortlisted': ['Rejected', 'Selected'],
                'Rejected': [],
                'Selected': [],
            }.get(item['status'], [])
            if allowed:
                new_status = st.selectbox('Update status', allowed, key=f"status_{item['application_id']}")
                if st.button('Save status', key=f"save_status_{item['application_id']}"):
                    changed, message = update_application_status(user['id'], user['id'], item['application_id'], new_status)
                    (st.success if changed else st.warning)(message)


def _industry_analytics(user):
    st.title('Industry analytics')
    data = get_industry_analytics(user['id'])
    status_data = [{'status': status, 'applications': total} for status, total in data['status_counts'].items()]
    if status_data:
        st.bar_chart(status_data, x='status', y='applications', alt='Applications by recruitment status')
    else:
        st.info('Application analytics will appear when candidates apply.')
    if data['applications_by_opportunity']:
        st.dataframe(data['applications_by_opportunity'], hide_index=True, alt='Applications by opportunity')
    if data['demanded_skills']:
        st.subheader('Most requested skills')
        st.bar_chart(data['demanded_skills'], x='skill', y='demand', alt='Most requested skills')


def _academician_dashboard(user):
    st.title(f"Academician dashboard · {user['first_name']}")
    summary = get_academician_summary(user['id'])
    if summary['profile']:
        profile = summary['profile']
        st.caption(' · '.join(filter(None, [profile['designation'], profile['department'], profile['institution_name']])))
    values = summary['counts']
    for label, value in (
        ('Research opportunities', values['research_opportunities']),
        ('Applications', values['applications']),
        ('Programmes', values['programmes']),
        ('Registrations', values['registrations']),
        ('Collaborations', values['collaborations']),
    ):
        st.metric(label, value, border=True)
    st.subheader('Notifications')
    _notifications(user['id'])
    st.info('Faculty profile editing, FDP registration, research applications, and collaboration proposals are not implemented in the existing Flask application.')


def _institution_dashboard(user):
    st.title(f"Institution dashboard · {user['first_name']}")
    summary = get_institution_summary(user['id'])
    if summary['profile']:
        st.caption(summary['profile']['institution_name'] or 'Institution profile not completed')
    for label, key in (
        ('Students', 'students'), ('Academicians', 'academicians'),
        ('Students in internships', 'internship_students'), ('Applications', 'applications'),
        ('Selected students', 'selected'), ('Collaborations', 'collaborations'),
    ):
        st.metric(label, summary['counts'][key], border=True)
    if summary['departments']:
        st.subheader('Students by department')
        st.bar_chart(summary['departments'], x='department', y='students', alt='Students by department')
    st.subheader('Recent activities')
    _notifications(user['id'])
    st.info('Institution profile editing, verification workflows, and report exports are not implemented in the existing Flask application.')


def _admin_dashboard(user):
    st.title('Platform administration')
    summary = get_admin_summary()
    counts = summary['counts']
    for label, key in (
        ('Users', 'total_users'), ('Pending industries', 'pending_industries'),
        ('Opportunities', 'total_opportunities'), ('Applications', 'total_applications'),
        ('Collaborations', 'total_collaborations'),
    ):
        st.metric(label, counts[key], border=True)
    st.subheader('Users by role')
    role_counts = [{'role': role, 'users': total} for role, total in summary['users_by_role'].items()]
    if role_counts:
        st.bar_chart(role_counts, x='role', y='users', alt='Registered users by role')
    st.subheader('Recent registrations')
    if summary['recent_users']:
        st.dataframe([dict(row) for row in summary['recent_users']], hide_index=True, alt='Recent user registrations')
    st.warning('This application currently provides admin summary only; user management, verification decisions, moderation, and audit tools are not implemented.')


def _public_page():
    rows = _query(
        """
        SELECT
          (SELECT COUNT(*) FROM users WHERE role='student') AS students,
          (SELECT COUNT(*) FROM opportunities WHERE status='published') AS opportunities
        """
    )[0]
    st.title('SkillBridge')
    st.header('Bridge academic talent with industry opportunity.')
    st.write('Skill mapping, career preparation, industry opportunities, and collaboration dashboards.')
    first, second = st.columns(2)
    first.metric('Student accounts', rows['students'])
    second.metric('Published opportunities', rows['opportunities'])


user = _current_user()
if user is None:
    pages = [
        st.Page(_public_page, title='Home', url_path='home', icon=':material/home:'),
        st.Page(_login_page, title='Log in / Register', url_path='account', icon=':material/login:'),
    ]
else:
    with st.sidebar:
        st.markdown(f"**{user['first_name']} {user['last_name']}**")
        st.caption(f"{user['email']} · {user['role'].title()}")
        if st.button('Log out', icon=':material/logout:'):
            st.session_state.pop('user_id', None)
            st.rerun()

    page_specs = {
        'student': [
            (_student_dashboard, 'Dashboard', 'dashboard'),
            (_student_profile, 'Profile & skills', 'person'),
            (_student_assessment, 'Skill assessment', 'quiz'),
            (_student_opportunities, 'Opportunities', 'work'),
            (_student_applications, 'Applications', 'assignment'),
            (_student_roadmap, 'Career roadmap', 'route'),
        ],
        'industry': [
            (_industry_dashboard, 'Dashboard', 'dashboard'),
            (_industry_profile, 'Company profile', 'business'),
            (_industry_opportunities, 'Opportunities', 'work'),
            (_industry_applications, 'Applications', 'group'),
            (_industry_analytics, 'Analytics', 'analytics'),
        ],
        'academician': [(_academician_dashboard, 'Dashboard', 'school')],
        'institution': [(_institution_dashboard, 'Dashboard', 'account_balance')],
        'admin': [(_admin_dashboard, 'Dashboard', 'admin_panel_settings')],
    }
    specs = page_specs.get(user['role'])
    if not specs:
        st.session_state.pop('user_id', None)
        st.error('This account has an unsupported role.')
        st.stop()
    pages = [
        st.Page(
            lambda render=render: render(user),
            title=title,
            url_path=re.sub(r'[^a-z0-9]+', '-', title.casefold()).strip('-'),
            icon=f':material/{icon}:',
        )
        for render, title, icon in specs
    ]
    pages.append(
        st.Page(
            lambda: _notifications(user['id']),
            title='Notifications',
            url_path='notifications',
            icon=':material/notifications:',
        )
    )

page = st.navigation(pages, position='sidebar')
page.run()
