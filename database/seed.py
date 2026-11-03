from sqlalchemy import select
from werkzeug.security import generate_password_hash

from database.db import get_db_connection, get_db_session
from database.models import User


def initialize_admin_account(first_name, last_name, email, password):
    session = get_db_session()
    try:
        existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing is not None:
            raise ValueError('An account with this email already exists.')

        admin = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=generate_password_hash(password),
            role='admin',
            is_active=True,
        )
        session.add(admin)
        session.commit()
        return admin
    finally:
        session.close()


def seed_database():
    session = get_db_session()
    try:
        existing_users = session.execute(select(User)).scalars().all()
        if not existing_users:
            demo_users = [
                User(first_name='Student', last_name='Demo', email='student@skillbridge.demo', password_hash=generate_password_hash('student123'), role='student', is_active=True),
                User(first_name='Industry', last_name='Demo', email='industry@skillbridge.demo', password_hash=generate_password_hash('industry123'), role='industry', is_active=True),
                User(first_name='Academician', last_name='Demo', email='academician@skillbridge.demo', password_hash=generate_password_hash('academician123'), role='academician', is_active=True),
                User(first_name='Institution', last_name='Demo', email='institution@skillbridge.demo', password_hash=generate_password_hash('institution123'), role='institution', is_active=True),
            ]
            session.add_all(demo_users)
            session.commit()

        demo_skill_names = [
            'Python', 'JavaScript', 'SQL', 'Web Development', 'Data Science',
            'Machine Learning', 'Communication', 'Problem Solving',
            'Research Methodology', 'Healthcare Data Analytics',
        ]
        conn = get_db_connection()
        try:
            existing_skills = conn.execute('SELECT name FROM skills').fetchall()
            existing_names = {row['name'] for row in existing_skills}
            for skill_name in demo_skill_names:
                if skill_name not in existing_names:
                    category = 'Technical' if skill_name not in ['Communication', 'Problem Solving', 'Research Methodology', 'Healthcare Data Analytics'] else ('Soft' if skill_name in ['Communication', 'Problem Solving'] else 'Research')
                    conn.execute('INSERT INTO skills (name, category, description) VALUES (?, ?, ?)', (skill_name, category, 'Demo skill for assessment and AI matching'))
            conn.commit()

            student_user = conn.execute("SELECT id FROM users WHERE email = ?", ('student@skillbridge.demo',)).fetchone()
            if student_user:
                existing_student_skills = conn.execute(
                    'SELECT skill_id FROM student_skills WHERE user_id = ?',
                    (student_user['id'],),
                ).fetchall()
                existing_ids = {row['skill_id'] for row in existing_student_skills}
                proficiency_map = {
                    'Python': 85,
                    'JavaScript': 72,
                    'SQL': 80,
                    'Web Development': 68,
                    'Data Science': 74,
                    'Machine Learning': 45,
                    'Communication': 88,
                    'Problem Solving': 82,
                    'Research Methodology': 52,
                    'Healthcare Data Analytics': 41,
                }
                for skill_name in demo_skill_names:
                    skill_row = conn.execute('SELECT id FROM skills WHERE name = ?', (skill_name,)).fetchone()
                    if skill_row and skill_row['id'] not in existing_ids:
                        conn.execute(
                            'INSERT INTO student_skills (user_id, skill_id, proficiency, source) VALUES (?, ?, ?, ?)',
                            (student_user['id'], skill_row['id'], proficiency_map.get(skill_name, 60), 'demo'),
                        )
                conn.commit()

            industry_user = conn.execute(
                "SELECT id FROM users WHERE email = ? AND role = 'industry'",
                ('industry@skillbridge.demo',),
            ).fetchone()
            industry_user_id = industry_user['id'] if industry_user else None
            if industry_user_id is not None:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO industry_profiles
                        (user_id, company_name, industry_sector, verification_status)
                    VALUES (?, 'SkillNova Labs', 'Technology', 'pending')
                    """,
                    (industry_user_id,),
                )
                conn.commit()
            existing_opportunity_titles = {row['title'] for row in conn.execute('SELECT title FROM opportunities').fetchall()}
            sample_opportunities = [
                ('Healthcare Data Analyst Intern', 'Internship', 'Analyze AYUSH and healthcare datasets to support digital health innovation.', 'Bengaluru', 'Hybrid', '2026-12-31', 1),
                ('Biomedical Software Developer', 'Full-time job', 'Create digital health tools and evidence-based biomedical platforms.', 'Remote', 'Remote', '2026-11-20', 1),
                ('Clinical Research Data Associate', 'Apprenticeship', 'Support research analytics and evidence synthesis for clinical projects.', 'Pune', 'On-site', '2026-10-29', 1),
                ('Digital Health Product Engineer', 'Live project', 'Prototype digital health dashboards and patient-facing experiences.', 'Remote', 'Remote', '2026-12-15', 1),
            ]
            for title, kind, description, location, mode, deadline, approved in sample_opportunities:
                if title not in existing_opportunity_titles:
                    conn.execute(
                        'INSERT INTO opportunities (company_id, title, opportunity_type, description, location, mode, deadline, is_approved, is_demo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)',
                        (industry_user_id, title, kind, description, location, mode, deadline, approved),
                    )
            conn.commit()
            if industry_user_id is not None:
                student_user = conn.execute(
                    "SELECT id FROM users WHERE email = ? AND role = 'student'",
                    ('student@skillbridge.demo',),
                ).fetchone()
                if student_user:
                    conn.execute(
                        """
                        UPDATE opportunities
                        SET company_id = ?
                        WHERE company_id = ?
                          AND title IN (
                            'Healthcare Data Analyst Intern',
                            'Biomedical Software Developer',
                            'Clinical Research Data Associate',
                            'Digital Health Product Engineer'
                          )
                        """,
                        (industry_user_id, student_user['id']),
                    )
                    conn.commit()
            opportunity_id_map = {row['title']: row['id'] for row in conn.execute('SELECT id, title FROM opportunities').fetchall()}
            opportunity_skill_rows = conn.execute('SELECT opportunity_id, skill FROM opportunity_skills').fetchall()
            existing_skill_mapping = {(row['opportunity_id'], row['skill']) for row in opportunity_skill_rows}
            opportunity_skills = {
                'Python Software Intern': ['Python', 'SQL', 'Communication', 'Problem Solving'],
                'Healthcare Data Analyst Intern': ['SQL', 'Data Science', 'Healthcare Data Analytics', 'Communication'],
                'Biomedical Software Developer': ['Python', 'Web Development', 'Research Methodology', 'Problem Solving'],
                'Clinical Research Data Associate': ['SQL', 'Research Methodology', 'Communication', 'Healthcare Data Analytics'],
                'Digital Health Product Engineer': ['JavaScript', 'Python', 'Web Development', 'Communication'],
            }
            for title, skills in opportunity_skills.items():
                opportunity_id = opportunity_id_map.get(title)
                if opportunity_id is None:
                    continue
                for skill_name in skills:
                    if (opportunity_id, skill_name) not in existing_skill_mapping:
                        conn.execute('INSERT INTO opportunity_skills (opportunity_id, skill) VALUES (?, ?)', (opportunity_id, skill_name))
            conn.commit()

            existing_learning_titles = {row['title'] for row in conn.execute('SELECT title FROM learning_programs').fetchall()}
            programs = [
                ('Python fundamentals', 'SkillBridge Academy', 'Learn core Python programming and applied scripting.', '4 weeks', 'Online'),
                ('SQL and database management', 'SkillBridge Academy', 'Practice SQL joins, aggregation, normalization, and relational logic.', '3 weeks', 'Online'),
                ('React development', 'SkillBridge Academy', 'Create UI interactions and modern frontend workflows.', '4 weeks', 'Hybrid'),
                ('Machine learning fundamentals', 'SkillBridge Academy', 'Build and evaluate a baseline ML pipeline.', '5 weeks', 'Online'),
                ('Data visualization', 'SkillBridge Academy', 'Turn raw data into executive-ready visual insights.', '2 weeks', 'Online'),
                ('Healthcare data analytics', 'SkillBridge Academy', 'Study healthcare metrics, cohorts, and reporting workflows.', '3 weeks', 'Hybrid'),
                ('Research methodology', 'SkillBridge Academy', 'Design evidence workflows and reporting frameworks.', '3 weeks', 'Online'),
            ]
            for title, provider, description, duration, mode in programs:
                if title not in existing_learning_titles:
                    conn.execute(
                        'INSERT INTO learning_programs (title, provider, description, duration, mode, is_demo) VALUES (?, ?, ?, ?, ?, 1)',
                        (title, provider, description, duration, mode),
                    )
            conn.commit()
        finally:
            conn.close()
    finally:
        session.close()


if __name__ == '__main__':
    seed_database()
