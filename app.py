import hmac
import os
import re
import secrets
import threading
from datetime import date, datetime, timezone
from functools import wraps
from uuid import uuid4
from urllib.parse import urlsplit

import click
from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import ALLOWED_EXTENSIONS, UPLOAD_FOLDER
from database.db import get_db_connection, get_db_session, init_db, seed_demo_data
from database.models import User
from modules.career_roadmap import generate_roadmap_for_goal, get_latest_roadmap_for_user, save_roadmap_for_user, update_roadmap_progress
from modules.opportunity import apply_for_opportunity, get_learning_programs_for_skill, get_recommended_opportunities
from modules.academician import get_academician_summary
from modules.admin import get_admin_summary
from modules.industry import (
    APPLICATION_STATUSES,
    ensure_company_profile,
    get_application_history,
    get_company_candidates,
    get_company_dashboard_data,
    get_company_opportunities,
    get_company_profile,
    get_industry_analytics,
    update_application_status,
)
from modules.institution import get_institution_summary
from modules.skill_analyzer import analyze_skills

app = Flask(__name__)
app.config.from_object('config')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
_database_initialization_lock = threading.Lock()

PUBLIC_ROLES = ['student', 'industry', 'academician', 'institution']
ALL_ROLES = ['student', 'industry', 'academician', 'institution', 'admin']
ASSESSMENT_QUESTIONS = [
    {
        'id': 'q1',
        'category': 'Technical',
        'question': 'Which language is widely used for Python backend web development?',
        'options': ['Flask', 'C', 'Assembly', 'Swift'],
        'answer': 'Flask',
    },
    {
        'id': 'q2',
        'category': 'Technical',
        'question': 'What is the purpose of SQL in application development?',
        'options': ['To manage relational data', 'To style web pages', 'To render graphics', 'To compress images'],
        'answer': 'To manage relational data',
    },
    {
        'id': 'q3',
        'category': 'Technical',
        'question': 'Which of the following best describes JavaScript?',
        'options': ['Client-side scripting for interactive web pages', 'A database query language', 'A static stylesheet language', 'A binary file format'],
        'answer': 'Client-side scripting for interactive web pages',
    },
    {
        'id': 'q4',
        'category': 'Soft Skill',
        'question': 'What is the most effective way to handle a team conflict in a project?',
        'options': ['Discuss concerns respectfully and align on a solution', 'Ignore the issue until deadlines pass', 'Blame the teammate publicly', 'Refuse to collaborate'],
        'answer': 'Discuss concerns respectfully and align on a solution',
    },
    {
        'id': 'q5',
        'category': 'Soft Skill',
        'question': 'Which practice best supports good time management?',
        'options': ['Prioritizing tasks and setting realistic deadlines', 'Waiting until the last minute', 'Skipping planning entirely', 'Ignoring task dependencies'],
        'answer': 'Prioritizing tasks and setting realistic deadlines',
    },
    {
        'id': 'q6',
        'category': 'Aptitude',
        'question': 'If 5 employees complete 5 tasks in 5 days, how many days would 10 employees need to complete 10 tasks?',
        'options': ['5 days', '10 days', '25 days', '2 days'],
        'answer': '5 days',
    },
]


def get_authenticated_user():
    if 'user_id' not in session:
        return None
    db = get_db_session()
    try:
        user = db.execute(select(User).where(User.id == session['user_id'])).scalar_one_or_none()
        if user is None or not user.is_active:
            session.clear()
            return None
        return user
    finally:
        db.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped


def role_required(*allowed_roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = get_authenticated_user()
            if user is None:
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('login'))
            if user.role not in allowed_roles:
                flash('You do not have access to that dashboard.', 'danger')
                return redirect(url_for('dashboard'))
            return view(*args, **kwargs)
        return wrapped
    return decorator


@app.cli.command('create-admin')
def create_admin():
    """Create an administrator account without a hard-coded password."""
    from database.seed import initialize_admin_account

    init_db()
    first_name = click.prompt('First name')
    last_name = click.prompt('Last name')
    email = click.prompt('Email').strip().lower()
    password = click.prompt('Password', hide_input=True, confirmation_prompt=True)
    if (
        not first_name or len(first_name) > 100 or not last_name or len(last_name) > 100
        or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email)
    ):
        raise click.ClickException('Enter valid names and email address.')
    if len(password) < 12 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
        raise click.ClickException('Password must be at least 12 characters and include a letter and a number.')
    try:
        initialize_admin_account(first_name, last_name, email, password)
    except ValueError as error:
        raise click.ClickException(str(error)) from error
    click.echo('Administrator account created.')


def get_student_skill_set(user_id):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT s.name, s.category, ss.proficiency
            FROM student_skills ss
            JOIN skills s ON s.id = ss.skill_id
            WHERE ss.user_id = ?
            ORDER BY s.name ASC
            """,
            (user_id,),
        ).fetchall()
        return [
            {'name': row['name'], 'category': row['category'], 'proficiency': row['proficiency']}
            for row in rows
        ]
    finally:
        conn.close()


def get_industry_requirements():
    from modules.skill_analyzer import INDUSTRY_REQUIREMENTS
    return INDUSTRY_REQUIREMENTS


def calculate_skill_match(student_skills):
    return analyze_skills(student_skills, get_industry_requirements())


def save_skill_analysis(user_id, payload):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO skill_analysis (user_id, matched_skills, missing_skills, compatibility, recommendations) VALUES (?, ?, ?, ?, ?)",
            (
                user_id,
                ', '.join(payload.get('matched', [])),
                ', '.join(payload.get('missing', [])),
                payload.get('compatibility', 0),
                ' | '.join(payload.get('recommendations', [])),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _validate_company_profile(form):
    profile = {
        'company_name': form.get('company_name', '').strip(),
        'industry_sector': form.get('industry_sector', '').strip(),
        'company_description': form.get('company_description', '').strip(),
        'website': form.get('website', '').strip(),
        'location': form.get('location', '').strip(),
        'contact_email': form.get('contact_email', '').strip().lower(),
        'contact_phone': form.get('contact_phone', '').strip(),
    }
    if not profile['company_name'] or len(profile['company_name']) > 150:
        return None, 'Company name is required and must be 150 characters or fewer.'
    if not profile['industry_sector'] or len(profile['industry_sector']) > 100:
        return None, 'Industry sector is required and must be 100 characters or fewer.'
    if len(profile['company_description']) < 20 or len(profile['company_description']) > 3000:
        return None, 'Company description must be between 20 and 3,000 characters.'
    if not profile['location'] or len(profile['location']) > 150:
        return None, 'Company location is required and must be 150 characters or fewer.'
    if profile['website']:
        try:
            parsed_website = urlsplit(profile['website'])
        except ValueError:
            return None, 'Enter a valid website URL beginning with http:// or https://.'
        if parsed_website.scheme not in {'http', 'https'} or not parsed_website.netloc:
            return None, 'Enter a valid website URL beginning with http:// or https://.'
    if profile['contact_email'] and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', profile['contact_email']):
        return None, 'Enter a valid company contact email.'
    if len(profile['contact_phone']) > 30:
        return None, 'Contact phone must be 30 characters or fewer.'
    if profile['contact_phone'] and not re.fullmatch(r'[+()\d\s.-]{6,30}', profile['contact_phone']):
        return None, 'Enter a valid contact phone number.'
    return profile, None


def _split_skill_input(value):
    skills = []
    seen = set()
    for raw_skill in value.split(','):
        skill = raw_skill.strip()
        normalized = skill.casefold()
        if skill and normalized not in seen:
            if len(skill) > 80:
                raise ValueError('Each skill must be 80 characters or fewer.')
            if len(skills) >= 50:
                raise ValueError('Enter no more than 50 skills in each category.')
            skills.append(skill)
            seen.add(normalized)
    return skills


def _validate_opportunity_form(form):
    allowed_types = {
        'Internship', 'Full-time job', 'Apprenticeship', 'Live project',
        'Research opportunity', 'Industrial training',
    }
    allowed_modes = {'Remote', 'On-site', 'Hybrid'}
    fields = {
        'title': form.get('title', '').strip(),
        'opportunity_type': form.get('opportunity_type', '').strip(),
        'description': form.get('description', '').strip(),
        'qualification_requirements': form.get('qualification_requirements', '').strip(),
        'location': form.get('location', '').strip(),
        'mode': form.get('mode', '').strip(),
        'stipend': form.get('stipend', '').strip(),
        'duration': form.get('duration', '').strip(),
        'deadline': form.get('deadline', '').strip(),
    }
    if not fields['title'] or len(fields['title']) > 150:
        return None, 'Opportunity title is required and must be 150 characters or fewer.'
    if fields['opportunity_type'] not in allowed_types:
        return None, 'Choose a valid opportunity category.'
    if len(fields['description']) < 30 or len(fields['description']) > 5000:
        return None, 'Description must be between 30 and 5,000 characters.'
    if not fields['qualification_requirements'] or len(fields['qualification_requirements']) > 1000:
        return None, 'Required qualifications are required and must be 1,000 characters or fewer.'
    if not fields['location'] or len(fields['location']) > 150:
        return None, 'Location is required and must be 150 characters or fewer.'
    if fields['mode'] not in allowed_modes:
        return None, 'Choose Remote, On-site, or Hybrid for the work mode.'
    if not fields['stipend'] or len(fields['stipend']) > 100:
        return None, 'Stipend or salary details are required and must be 100 characters or fewer.'
    if not fields['duration'] or len(fields['duration']) > 100:
        return None, 'Duration is required and must be 100 characters or fewer.'
    try:
        deadline = date.fromisoformat(fields['deadline'])
    except ValueError:
        return None, 'Enter a valid application deadline.'
    if deadline < date.today():
        return None, 'Application deadline must be today or later.'
    try:
        openings = int(form.get('openings', ''))
    except ValueError:
        return None, 'Number of openings must be a whole number.'
    if openings < 1 or openings > 1000:
        return None, 'Number of openings must be between 1 and 1,000.'
    raw_cgpa = form.get('minimum_cgpa', '').strip()
    try:
        minimum_cgpa = float(raw_cgpa) if raw_cgpa else None
    except ValueError:
        return None, 'Minimum CGPA must be a number between 0 and 10.'
    if minimum_cgpa is not None and not 0 <= minimum_cgpa <= 10:
        return None, 'Minimum CGPA must be between 0 and 10.'
    try:
        technical_skills = _split_skill_input(form.get('technical_skills', ''))
        soft_skills = _split_skill_input(form.get('soft_skills', ''))
    except ValueError as error:
        return None, str(error)
    if not technical_skills:
        return None, 'Enter at least one required technical skill.'
    fields.update({
        'openings': openings,
        'minimum_cgpa': minimum_cgpa,
        'technical_skills': technical_skills,
        'soft_skills': soft_skills,
    })
    return fields, None


def _save_validated_upload(upload, kind):
    if upload is None or not upload.filename:
        return None, None
    original_name = secure_filename(upload.filename)
    extension = os.path.splitext(original_name)[1].lower()
    if kind == 'logo':
        valid_extensions = {'.png', '.jpg', '.jpeg'}
        max_bytes = 2 * 1024 * 1024
        allowed_signatures = {
            '.png': lambda data: data.startswith(b'\x89PNG\r\n\x1a\n'),
            '.jpg': lambda data: data.startswith(b'\xff\xd8\xff'),
            '.jpeg': lambda data: data.startswith(b'\xff\xd8\xff'),
        }
    else:
        valid_extensions = {'.pdf'}
        max_bytes = 8 * 1024 * 1024
        allowed_signatures = {'.pdf': lambda data: data.startswith(b'%PDF-')}
    if extension not in valid_extensions:
        return None, f'Upload a supported {kind} file.'

    content = upload.stream.read(max_bytes + 1)
    if len(content) > max_bytes:
        return None, f'The {kind} file exceeds the {max_bytes // (1024 * 1024)} MB limit.'
    if not allowed_signatures[extension](content):
        return None, f'The uploaded {kind} file does not match its file type.'
    filename = f'{uuid4().hex}{extension}'
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    with open(filepath, 'wb') as stored_file:
        stored_file.write(content)
    return filename, None


def _insert_opportunity_skills(conn, opportunity_id, technical_skills, soft_skills):
    for category, skills in (('technical', technical_skills), ('soft', soft_skills)):
        for skill in skills:
            conn.execute(
                """
                INSERT INTO opportunity_skills (opportunity_id, skill, skill_category, is_required)
                VALUES (?, ?, ?, 1)
                """,
                (opportunity_id, skill, category),
            )


@app.before_request
def ensure_application_setup():
    if not app.extensions.get('skillbridge_database_initialized'):
        with _database_initialization_lock:
            if not app.extensions.get('skillbridge_database_initialized'):
                init_db()
                if app.config['DEMO_DATA_ENABLED']:
                    conn = get_db_connection()
                    try:
                        counts = conn.execute(
                            """
                            SELECT
                              (SELECT COUNT(*) FROM users) AS users,
                              (SELECT COUNT(*) FROM skills) AS skills,
                              (SELECT COUNT(*) FROM opportunities) AS opportunities,
                              (SELECT COUNT(*) FROM learning_programs) AS learning_programs,
                              (
                                SELECT COUNT(*) FROM opportunities o
                                WHERE o.company_id = (SELECT id FROM users WHERE email = 'student@skillbridge.demo')
                                  AND o.title IN (
                                    'Healthcare Data Analyst Intern', 'Biomedical Software Developer',
                                    'Clinical Research Data Associate', 'Digital Health Product Engineer'
                                  )
                              ) AS misowned_demo_opportunities
                            """
                        ).fetchone()
                    finally:
                        conn.close()
                    if (
                        counts['users'] == 0 or counts['skills'] == 0 or counts['opportunities'] < 4
                        or counts['learning_programs'] < 7 or counts['misowned_demo_opportunities'] > 0
                    ):
                        seed_demo_data()
                app.extensions['skillbridge_database_initialized'] = True

    session.setdefault('csrf_token', secrets.token_urlsafe(32))
    if request.method == 'POST':
        submitted_token = request.form.get('csrf_token', '')
        if not submitted_token or not hmac.compare_digest(session['csrf_token'], submitted_token):
            abort(400, description='Invalid or missing CSRF token.')


@app.context_processor
def inject_csrf_token():
    return {
        'csrf_token': lambda: session.get('csrf_token', ''),
        'today': date.today().isoformat(),
        'demo_data_enabled': app.config['DEMO_DATA_ENABLED'],
    }


@app.route('/')
def home():
    conn = get_db_connection()
    try:
        platform_counts = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM users WHERE role = 'student') AS students,
              (SELECT COUNT(*) FROM opportunities
               WHERE status = 'published' AND (deadline IS NULL OR date(deadline) >= date('now'))) AS opportunities,
              (SELECT COUNT(DISTINCT role) FROM users) AS roles
            """
        ).fetchone()
    finally:
        conn.close()
    return render_template('index.html', platform_counts=platform_counts)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html')

        db = get_db_session()
        try:
            user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user and user.is_active and check_password_hash(user.password_hash, password):
                session.clear()
                session['user_id'] = user.id
                session['user_email'] = user.email
                session['role'] = user.role
                flash(f'Welcome back, {user.first_name}.', 'success')
                return redirect(url_for(f'{user.role}_dashboard'))

            flash('Invalid email or password.', 'danger')
        finally:
            db.close()

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        role = request.form.get('role', 'student').strip().lower()

        if not all([first_name, last_name, email, password]):
            flash('Please complete all required fields.', 'danger')
            return render_template('register.html')

        if (
            len(first_name) > 100 or len(last_name) > 100 or len(email) > 255
            or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email)
        ):
            flash('Enter a valid name and email address within the allowed length.', 'danger')
            return render_template('register.html')

        if role not in PUBLIC_ROLES:
            flash('Invalid role selected for public registration.', 'danger')
            return render_template('register.html')

        if len(password) < 8 or not re.search(r'[A-Za-z]', password) or not re.search(r'\d', password):
            flash('Password must contain at least 8 characters, one letter and one number.', 'danger')
            return render_template('register.html')

        db = get_db_session()
        try:
            existing_user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing_user:
                flash('An account with this email already exists.', 'warning')
                return render_template('register.html')

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
                conn = get_db_connection()
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO industry_profiles (user_id, verification_status) VALUES (?, 'pending')",
                        (user.id,),
                    )
                    conn.commit()
                finally:
                    conn.close()
            flash('Registration successful. Please log in to continue.', 'success')
            return redirect(url_for('login'))
        finally:
            db.close()

    return render_template('register.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('home'))


@app.route('/dashboard')
@login_required
def dashboard():
    user = get_authenticated_user()
    if user is None:
        return redirect(url_for('login'))
    if user.role not in ALL_ROLES:
        flash('Unknown user role detected.', 'danger')
        return redirect(url_for('home'))
    return redirect(url_for(f'{user.role}_dashboard'))


@app.route('/student-dashboard')
@login_required
@role_required('student')
def student_dashboard():
    user = get_authenticated_user()
    student_skills = get_student_skill_set(user.id)
    payload = calculate_skill_match(student_skills)
    conn = get_db_connection()
    try:
        notifications = conn.execute(
            """
            SELECT title, message, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 5
            """,
            (user.id,),
        ).fetchall()
    finally:
        conn.close()
    return render_template(
        'student_dashboard.html',
        user=user,
        skills=student_skills,
        analytics=payload,
        notifications=notifications,
    )


@app.route('/student-profile', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_profile():
    user = get_authenticated_user()
    if request.method == 'POST':
        college = request.form.get('college', '').strip()
        degree = request.form.get('degree', '').strip()
        branch = request.form.get('branch', '').strip()
        bio = request.form.get('bio', '').strip()
        interest_area = request.form.get('interest_area', '').strip()
        if any(len(value) > 250 for value in (college, degree, branch, interest_area)) or len(bio) > 3000:
            flash('Academic profile fields exceed the allowed length.', 'danger')
            return redirect(url_for('student_profile'))
        try:
            year_of_study = int(request.form.get('year_of_study', '') or 0) or None
            cgpa = float(request.form.get('cgpa', '') or 0) or None
        except ValueError:
            flash('Year of study and CGPA must be valid numbers.', 'danger')
            return redirect(url_for('student_profile'))
        if year_of_study is not None and not 1 <= year_of_study <= 10:
            flash('Year of study must be between 1 and 10.', 'danger')
            return redirect(url_for('student_profile'))
        if cgpa is not None and not 0 <= cgpa <= 10:
            flash('CGPA must be between 0 and 10.', 'danger')
            return redirect(url_for('student_profile'))

        conn = get_db_connection()
        existing = conn.execute(
            'SELECT resume_filename FROM student_profiles WHERE user_id = ?',
            (user.id,),
        ).fetchone()
        conn.close()
        resume_filename, upload_error = _save_validated_upload(request.files.get('resume'), 'resume')
        if upload_error:
            flash(upload_error, 'danger')
            return redirect(url_for('student_profile'))
        if not resume_filename and existing:
            resume_filename = existing['resume_filename']
        conn = get_db_connection()
        try:
            conn.execute(
                """
                INSERT INTO student_profiles
                    (user_id, college, degree, branch, year_of_study, cgpa, bio, interest_area, resume_filename)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    college = excluded.college,
                    degree = excluded.degree,
                    branch = excluded.branch,
                    year_of_study = excluded.year_of_study,
                    cgpa = excluded.cgpa,
                    bio = excluded.bio,
                    interest_area = excluded.interest_area,
                    resume_filename = excluded.resume_filename
                """,
                (user.id, college, degree, branch, year_of_study, cgpa, bio, interest_area, resume_filename),
            )
            conn.commit()
        finally:
            conn.close()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('student_profile'))

    conn = get_db_connection()
    try:
        profile = conn.execute(
            'SELECT * FROM student_profiles WHERE user_id = ?',
            (user.id,),
        ).fetchone()
    finally:
        conn.close()
    return render_template('student_profile.html', user=user, profile=profile)


@app.route('/skill-assessment', methods=['GET', 'POST'])
@login_required
@role_required('student')
def skill_assessment():
    if request.method == 'POST':
        total_score = 0
        answers = []
        for question in ASSESSMENT_QUESTIONS:
            selected = request.form.get(question['id'])
            is_correct = selected == question['answer']
            if is_correct:
                total_score += 1
            answers.append({
                'category': question['category'],
                'question': question['question'],
                'selected': selected,
                'correct_answer': question['answer'],
                'is_correct': is_correct,
            })

        conn = get_db_connection()
        try:
            assessment_cursor = conn.execute(
                'INSERT INTO assessments (user_id, title, category, score) VALUES (?, ?, ?, ?)',
                (session['user_id'], 'Student Skill Assessment', 'technical', total_score),
            )
            assessment_id = assessment_cursor.lastrowid
            for answer in answers:
                conn.execute(
                    'INSERT INTO assessment_answers (assessment_id, question, selected_option, is_correct) VALUES (?, ?, ?, ?)',
                    (assessment_id, answer['question'], answer['selected'], 1 if answer['is_correct'] else 0),
                )
            conn.commit()
        finally:
            conn.close()

        flash(f'Assessment complete. Your score is {total_score}/{len(ASSESSMENT_QUESTIONS)}.', 'success')
        return redirect(url_for('skill_analysis'))

    return render_template('student_assessment.html', questions=ASSESSMENT_QUESTIONS)


@app.route('/skill-analysis')
@login_required
@role_required('student')
def skill_analysis():
    user = get_authenticated_user()
    student_skills = get_student_skill_set(user.id)
    payload = calculate_skill_match(student_skills)
    save_skill_analysis(user.id, payload)
    for recommendation in payload.get('learning_recommendations', []):
        skill_name = recommendation.get('skill')
        if skill_name:
            recommendation['programs'] = get_learning_programs_for_skill(skill_name)
    return render_template('skill_analysis.html', user=user, skills=student_skills, analytics=payload)


@app.route('/opportunities')
@login_required
@role_required('student')
def student_opportunities():
    user = get_authenticated_user()
    student_skills = get_student_skill_set(user.id)
    payload = calculate_skill_match(student_skills)
    opportunities = get_recommended_opportunities(student_skills, user.id)
    return render_template('opportunities.html', user=user, analytics=payload, opportunities=opportunities)


@app.route('/opportunities/<int:opportunity_id>/apply', methods=['POST'])
@login_required
@role_required('student')
def apply_opportunity(opportunity_id):
    user = get_authenticated_user()
    result = apply_for_opportunity(user.id, opportunity_id)
    if result['success']:
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'warning')
    return redirect(url_for('student_opportunities'))


@app.route('/career-roadmap', methods=['GET', 'POST'])
@login_required
@role_required('student')
def student_career_roadmap():
    user = get_authenticated_user()
    student_skills = get_student_skill_set(user.id)
    analysis = calculate_skill_match(student_skills)

    if request.method == 'POST':
        if request.form.get('action') == 'update-progress':
            roadmap_id = request.form.get('roadmap_id', type=int)
            step_index = request.form.get('step_index', type=int)
            progress_value = request.form.get('progress', type=int)
            if roadmap_id and step_index is not None and progress_value is not None:
                updated = update_roadmap_progress(user.id, roadmap_id, step_index, progress_value)
                if updated:
                    flash('Roadmap progress updated successfully.', 'success')
                else:
                    flash('Unable to update roadmap progress.', 'warning')
            return redirect(url_for('student_career_roadmap'))

        goal = request.form.get('career_goal') or 'Full Stack Developer'
        roadmap_steps = generate_roadmap_for_goal(goal, [skill['name'] for skill in student_skills], analysis.get('missing', []))
        save_roadmap_for_user(user.id, goal, roadmap_steps)
        flash(f'Career roadmap for {goal} has been generated.', 'success')
        return redirect(url_for('student_career_roadmap'))

    latest_roadmap = get_latest_roadmap_for_user(user.id)
    if latest_roadmap is None:
        goal = 'Full Stack Developer'
        latest_roadmap = {
            'career_goal': goal,
            'roadmap': generate_roadmap_for_goal(goal, [skill['name'] for skill in student_skills], analysis.get('missing', [])),
            'progress': 0,
        }
    return render_template('career_roadmap.html', user=user, analytics=analysis, roadmap=latest_roadmap)


@app.route('/industry-dashboard')
@login_required
@role_required('industry')
def industry_dashboard():
    user = get_authenticated_user()
    ensure_company_profile(user.id)
    dashboard_data = get_company_dashboard_data(user.id)
    analytics = get_industry_analytics(user.id)
    return render_template(
        'industry_dashboard.html',
        user=user,
        dashboard=dashboard_data,
        analytics=analytics,
    )


@app.route('/industry/company-profile', methods=['GET', 'POST'])
@login_required
@role_required('industry')
def industry_company_profile():
    user = get_authenticated_user()
    profile = ensure_company_profile(user.id)
    if request.method == 'POST':
        company_fields, validation_error = _validate_company_profile(request.form)
        if validation_error:
            flash(validation_error, 'danger')
            return redirect(url_for('industry_company_profile'))
        logo_filename, upload_error = _save_validated_upload(request.files.get('logo'), 'logo')
        if upload_error:
            flash(upload_error, 'danger')
            return redirect(url_for('industry_company_profile'))
        if not logo_filename:
            logo_filename = profile['logo_filename']
        conn = get_db_connection()
        try:
            conn.execute(
                """
                UPDATE industry_profiles
                SET company_name = ?, industry_sector = ?, company_description = ?,
                    website = ?, location = ?, contact_email = ?, contact_phone = ?,
                    logo_filename = ?
                WHERE user_id = ?
                """,
                (
                    company_fields['company_name'],
                    company_fields['industry_sector'],
                    company_fields['company_description'],
                    company_fields['website'],
                    company_fields['location'],
                    company_fields['contact_email'],
                    company_fields['contact_phone'],
                    logo_filename,
                    user.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        flash('Company profile updated successfully.', 'success')
        return redirect(url_for('industry_company_profile'))
    return render_template('industry_company_profile.html', user=user, profile=profile)


@app.route('/industry/company-profile/verification', methods=['POST'])
@login_required
@role_required('industry')
def request_company_verification():
    user = get_authenticated_user()
    profile = ensure_company_profile(user.id)
    if profile['verification_status'] == 'verified':
        flash('This company is already verified.', 'info')
        return redirect(url_for('industry_company_profile'))
    conn = get_db_connection()
    try:
        conn.execute(
            """
            UPDATE industry_profiles
            SET verification_status = 'pending', verification_requested_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            (user.id,),
        )
        conn.execute(
            """
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, 'Verification request submitted', 'Your company verification request is pending review.')
            """,
            (user.id,),
        )
        conn.commit()
    finally:
        conn.close()
    flash('Verification request submitted. Your status remains pending until reviewed.', 'success')
    return redirect(url_for('industry_company_profile'))


@app.route('/industry/company-logo/<filename>')
@login_required
@role_required('industry')
def industry_company_logo(filename):
    user = get_authenticated_user()
    profile = get_company_profile(user.id)
    safe_filename = secure_filename(filename)
    if not profile or not safe_filename or profile['logo_filename'] != safe_filename:
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], safe_filename, as_attachment=False)


@app.route('/industry/opportunities')
@login_required
@role_required('industry')
def industry_opportunities():
    user = get_authenticated_user()
    ensure_company_profile(user.id)
    opportunities = get_company_opportunities(user.id)
    return render_template('industry_opportunities.html', user=user, opportunities=opportunities)


@app.route('/industry/opportunities/new', methods=['GET', 'POST'])
@login_required
@role_required('industry')
def create_industry_opportunity():
    user = get_authenticated_user()
    if request.method == 'POST':
        fields, validation_error = _validate_opportunity_form(request.form)
        if validation_error:
            flash(validation_error, 'danger')
            return render_template(
                'industry_opportunity_form.html',
                user=user,
                opportunity=None,
                form_data=request.form,
            )
        conn = get_db_connection()
        try:
            cursor = conn.execute(
                """
                INSERT INTO opportunities
                    (company_id, title, opportunity_type, description, location, mode,
                     stipend, duration, deadline, qualification_requirements, minimum_cgpa,
                     openings, status, is_approved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0)
                """,
                (
                    user.id, fields['title'], fields['opportunity_type'], fields['description'],
                    fields['location'], fields['mode'], fields['stipend'], fields['duration'],
                    fields['deadline'], fields['qualification_requirements'],
                    fields['minimum_cgpa'], fields['openings'],
                ),
            )
            _insert_opportunity_skills(
                conn, cursor.lastrowid, fields['technical_skills'], fields['soft_skills'],
            )
            conn.commit()
        finally:
            conn.close()
        flash('Opportunity saved as a draft. Publish it when it is ready.', 'success')
        return redirect(url_for('industry_opportunities'))
    return render_template('industry_opportunity_form.html', user=user, opportunity=None)


@app.route('/industry/opportunities/<int:opportunity_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('industry')
def edit_industry_opportunity(opportunity_id):
    user = get_authenticated_user()
    conn = get_db_connection()
    try:
        opportunity = conn.execute(
            'SELECT * FROM opportunities WHERE id = ? AND company_id = ?',
            (opportunity_id, user.id),
        ).fetchone()
        if opportunity is None:
            abort(404)
        if request.method == 'POST':
            fields, validation_error = _validate_opportunity_form(request.form)
            if validation_error:
                flash(validation_error, 'danger')
                return render_template(
                    'industry_opportunity_form.html',
                    user=user,
                    opportunity=dict(opportunity),
                    form_data=request.form,
                )
            conn.execute(
                """
                UPDATE opportunities
                SET title = ?, opportunity_type = ?, description = ?, location = ?, mode = ?,
                    stipend = ?, duration = ?, deadline = ?, qualification_requirements = ?,
                    minimum_cgpa = ?, openings = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND company_id = ?
                """,
                (
                    fields['title'], fields['opportunity_type'], fields['description'],
                    fields['location'], fields['mode'], fields['stipend'], fields['duration'],
                    fields['deadline'], fields['qualification_requirements'],
                    fields['minimum_cgpa'], fields['openings'], opportunity_id, user.id,
                ),
            )
            conn.execute('DELETE FROM opportunity_skills WHERE opportunity_id = ?', (opportunity_id,))
            _insert_opportunity_skills(
                conn, opportunity_id, fields['technical_skills'], fields['soft_skills'],
            )
            conn.commit()
            flash('Opportunity updated successfully.', 'success')
            return redirect(url_for('industry_opportunities'))
        current = dict(opportunity)
        skills = conn.execute(
            """
            SELECT skill, skill_category FROM opportunity_skills
            WHERE opportunity_id = ? ORDER BY skill_category, skill
            """,
            (opportunity_id,),
        ).fetchall()
        current['technical_skills'] = ', '.join(
            item['skill'] for item in skills if item['skill_category'].lower() == 'technical'
        )
        current['soft_skills'] = ', '.join(
            item['skill'] for item in skills if item['skill_category'].lower() == 'soft'
        )
        return render_template('industry_opportunity_form.html', user=user, opportunity=current)
    finally:
        conn.close()


@app.route('/industry/opportunities/<int:opportunity_id>/status', methods=['POST'])
@login_required
@role_required('industry')
def update_industry_opportunity_status(opportunity_id):
    user = get_authenticated_user()
    new_status = request.form.get('status', '').strip().lower()
    if new_status not in {'draft', 'published', 'closed'}:
        flash('Choose a valid opportunity status.', 'danger')
        return redirect(url_for('industry_opportunities'))
    conn = get_db_connection()
    try:
        opportunity = conn.execute(
            'SELECT id, deadline FROM opportunities WHERE id = ? AND company_id = ?',
            (opportunity_id, user.id),
        ).fetchone()
        if opportunity is None:
            abort(404)
        if new_status == 'published' and opportunity['deadline'] and date.fromisoformat(opportunity['deadline']) < date.today():
            flash('An expired opportunity cannot be published.', 'danger')
            return redirect(url_for('industry_opportunities'))
        conn.execute(
            """
            UPDATE opportunities
            SET status = ?,
                is_approved = CASE WHEN ? = 'closed' THEN 0 ELSE is_approved END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND company_id = ?
            """,
            (new_status, new_status, opportunity_id, user.id),
        )
        conn.commit()
    finally:
        conn.close()
    flash(f'Opportunity {new_status}.', 'success')
    return redirect(url_for('industry_opportunities'))


@app.route('/industry/candidates')
@login_required
@role_required('industry')
def industry_candidates():
    user = get_authenticated_user()
    search = request.args.get('q', '').strip()[:100]
    status_filter = request.args.get('status', '').strip()
    if status_filter not in APPLICATION_STATUSES:
        status_filter = ''
    opportunity_id = request.args.get('opportunity_id', type=int)
    own_opportunities = get_company_opportunities(user.id)
    own_ids = {item['id'] for item in own_opportunities}
    if opportunity_id not in own_ids:
        opportunity_id = None
    candidates = get_company_candidates(user.id, search, status_filter, opportunity_id)
    for candidate in candidates:
        skill_analysis = analyze_skills(candidate['skills'], candidate['skill_requirements'])
        candidate['compatibility'] = skill_analysis['proficiency_compatibility'] if candidate['skill_requirements'] else 0
        candidate['matched_skills'] = skill_analysis['matched']
        candidate['partial_skills'] = skill_analysis['partial']
        candidate['missing_skills'] = skill_analysis['missing']
        minimum_cgpa = candidate['minimum_cgpa']
        cgpa = candidate['cgpa']
        if minimum_cgpa is None:
            candidate['eligibility'] = 'Academic review required'
        elif cgpa is None:
            candidate['eligibility'] = 'Academic details not provided'
        elif float(cgpa) >= float(minimum_cgpa):
            candidate['eligibility'] = 'Meets CGPA requirement'
        else:
            candidate['eligibility'] = 'Below minimum CGPA'
        candidate['history'] = get_application_history(user.id, candidate['application_id'])

    sort_by = request.args.get('sort', 'recent')
    sort_keys = {
        'recent': lambda item: item['applied_at'] or '',
        'name': lambda item: f"{item['first_name']} {item['last_name']}".casefold(),
        'compatibility': lambda item: item['compatibility'],
    }
    candidates.sort(key=sort_keys.get(sort_by, sort_keys['recent']), reverse=sort_by != 'name')
    return render_template(
        'industry_candidates.html',
        user=user,
        candidates=candidates,
        opportunities=own_opportunities,
        filters={'q': search, 'status': status_filter, 'opportunity_id': opportunity_id, 'sort': sort_by},
        statuses=APPLICATION_STATUSES,
    )


@app.route('/industry/applications/<int:application_id>/status', methods=['POST'])
@login_required
@role_required('industry')
def industry_application_status(application_id):
    user = get_authenticated_user()
    new_status = request.form.get('status', '').strip()
    updated, message = update_application_status(user.id, user.id, application_id, new_status)
    flash(message, 'success' if updated else 'warning')
    return redirect(url_for('industry_candidates'))


@app.route('/industry/analytics')
@login_required
@role_required('industry')
def industry_analytics():
    user = get_authenticated_user()
    return render_template(
        'industry_analytics.html',
        user=user,
        dashboard=get_company_dashboard_data(user.id),
        analytics=get_industry_analytics(user.id),
    )


@app.route('/private-resume/<int:student_id>')
@login_required
def private_student_resume(student_id):
    user = get_authenticated_user()
    if user is None:
        abort(403)
    conn = get_db_connection()
    try:
        if user.role == 'student':
            allowed = user.id == student_id
        elif user.role == 'industry':
            allowed = conn.execute(
                """
                SELECT 1
                FROM applications a
                JOIN opportunities o ON o.id = a.opportunity_id
                WHERE a.user_id = ? AND o.company_id = ?
                LIMIT 1
                """,
                (student_id, user.id),
            ).fetchone() is not None
        else:
            allowed = False
        profile = conn.execute(
            'SELECT resume_filename FROM student_profiles WHERE user_id = ?',
            (student_id,),
        ).fetchone() if allowed else None
    finally:
        conn.close()
    filename = profile['resume_filename'] if profile else None
    if not filename or secure_filename(filename) != filename:
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.route('/academician-dashboard')
@login_required
@role_required('academician')
def academician_dashboard():
    user = get_authenticated_user()
    summary = get_academician_summary(user.id)
    return render_template(
        'academician_dashboard.html',
        user=user,
        profile=summary['profile'],
        counts=summary['counts'],
        notifications=summary['notifications'],
    )


@app.route('/institution-dashboard')
@login_required
@role_required('institution')
def institution_dashboard():
    user = get_authenticated_user()
    summary = get_institution_summary(user.id)
    return render_template(
        'institution_dashboard.html',
        user=user,
        profile=summary['profile'],
        counts=summary['counts'],
        departments=summary['departments'],
        recent_activities=summary['recent_activities'],
    )


@app.route('/admin-dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    user = get_authenticated_user()
    summary = get_admin_summary()
    return render_template(
        'admin_dashboard.html',
        user=user,
        users_by_role=summary['users_by_role'],
        counts=summary['counts'],
        recent_users=summary['recent_users'],
    )


@app.route('/health')
def health_check():
    return {'status': 'ok', 'timestamp': datetime.now(timezone.utc).isoformat()}, 200


if __name__ == '__main__':
    app.run(debug=False, host='127.0.0.1', port=5000)
