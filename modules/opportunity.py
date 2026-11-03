"""Student opportunity discovery and application logic."""

from __future__ import annotations

from database.db import get_db_connection
from modules.skill_analyzer import analyze_skills


def _requirements_for_opportunity(conn, opportunity_id):
    rows = conn.execute(
        """
        SELECT skill, skill_category, is_required
        FROM opportunity_skills
        WHERE opportunity_id = ?
        ORDER BY skill_category, skill
        """,
        (opportunity_id,),
    ).fetchall()
    return [
        {
            'name': row['skill'],
            'category': row['skill_category'],
            'weight': 10 if row['is_required'] else 3,
            'required': bool(row['is_required']),
        }
        for row in rows
    ]


def get_opportunity_catalog():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT o.id, o.title, o.opportunity_type, o.description, o.location, o.mode,
                   o.stipend, o.duration, o.deadline, o.qualification_requirements,
                   o.minimum_cgpa, o.openings, o.status, o.is_approved, o.is_demo,
                   ip.company_name, u.first_name, u.last_name
            FROM opportunities o
            LEFT JOIN users u ON u.id = o.company_id
            LEFT JOIN industry_profiles ip ON ip.user_id = o.company_id
            WHERE o.status != 'closed'
              AND (o.status = 'published' OR o.is_approved = 1)
              AND (o.deadline IS NULL OR date(o.deadline) >= date('now'))
            ORDER BY o.created_at DESC, o.id DESC
            """
        ).fetchall()
        opportunities = []
        for row in rows:
            requirements = _requirements_for_opportunity(conn, row['id'])
            required_skills = [item['name'] for item in requirements if item['required']]
            opportunities.append({
                'id': row['id'],
                'title': row['title'],
                'type': row['opportunity_type'],
                'company': row['company_name'] or f"{row['first_name'] or ''} {row['last_name'] or ''}".strip() or 'Industry employer',
                'location': row['location'] or 'Not specified',
                'mode': row['mode'] or 'Not specified',
                'deadline': row['deadline'] or 'Ongoing',
                'required_skills': required_skills,
                'skill_requirements': requirements,
                'minimum_cgpa': row['minimum_cgpa'],
                'qualification_requirements': row['qualification_requirements'],
                'description': row['description'],
                'status': row['status'],
                'is_sample': bool(row['is_demo']),
            })
        return opportunities
    finally:
        conn.close()


def _score_opportunity(conn, opportunity, student_skills, student_id):
    requirements = opportunity['skill_requirements']
    if requirements:
        analysis = analyze_skills(student_skills, requirements)
        compatibility = analysis['proficiency_compatibility']
        matched = analysis['matched']
        partial = analysis['partial']
        missing = analysis['missing']
    else:
        compatibility = 0
        matched = []
        partial = []
        missing = []

    profile = conn.execute(
        'SELECT cgpa FROM student_profiles WHERE user_id = ?',
        (student_id,),
    ).fetchone()
    cgpa = profile['cgpa'] if profile else None
    academic_eligible = opportunity['minimum_cgpa'] is None or (
        cgpa is not None and float(cgpa) >= float(opportunity['minimum_cgpa'])
    )
    skill_fit = compatibility >= 50
    eligible = skill_fit and academic_eligible
    eligibility = (
        'No minimum CGPA specified' if opportunity['minimum_cgpa'] is None else
        'Meets minimum CGPA requirement' if academic_eligible else
        'Does not meet minimum CGPA requirement'
    )
    return {
        'compatibility': compatibility,
        'matched_skills': matched,
        'partial_skills': partial,
        'missing_skills': missing,
        'eligible': eligible,
        'eligibility': eligibility,
        'skill_fit': 'Meets skill threshold' if skill_fit else 'Skill development needed',
        'recommendation_explanation': (
            'Strong alignment with required skills and academic criteria.'
            if eligible else
            'Improve the listed skill gaps or meet the minimum academic requirement before applying.'
        ),
    }


def get_recommended_opportunities(student_skills, user_id=None):
    if user_id is None:
        return []
    conn = get_db_connection()
    try:
        recommendations = []
        for opportunity in get_opportunity_catalog():
            opportunity.update(_score_opportunity(conn, opportunity, student_skills, user_id))
            recommendations.append(opportunity)
        return sorted(
            recommendations,
            key=lambda item: (item['compatibility'], item['eligible'], item['title']),
            reverse=True,
        )
    finally:
        conn.close()


def apply_for_opportunity(user_id, opportunity_id):
    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        row = conn.execute(
            """
            SELECT o.id, o.title, o.minimum_cgpa, o.deadline, o.status, o.is_approved
            FROM opportunities o
            WHERE o.id = ?
              AND o.status != 'closed'
              AND (o.status = 'published' OR o.is_approved = 1)
              AND (o.deadline IS NULL OR date(o.deadline) >= date('now'))
            """,
            (opportunity_id,),
        ).fetchone()
        if not row:
            conn.rollback()
            return {'success': False, 'message': 'This opportunity is closed, expired, or unavailable.'}

        requirements = _requirements_for_opportunity(conn, opportunity_id)
        if not requirements:
            conn.rollback()
            return {'success': False, 'message': 'This opportunity has no published skill requirements.'}
        student_rows = conn.execute(
            """
            SELECT s.name, s.category, ss.proficiency
            FROM student_skills ss
            JOIN skills s ON s.id = ss.skill_id
            WHERE ss.user_id = ?
            """,
            (user_id,),
        ).fetchall()
        analysis = analyze_skills([dict(skill) for skill in student_rows], requirements)
        profile = conn.execute(
            'SELECT cgpa FROM student_profiles WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        if analysis['proficiency_compatibility'] < 50:
            conn.rollback()
            return {'success': False, 'message': 'This opportunity requires stronger skill alignment before application.'}
        if row['minimum_cgpa'] is not None and (
            profile is None or profile['cgpa'] is None or float(profile['cgpa']) < float(row['minimum_cgpa'])
        ):
            conn.rollback()
            return {'success': False, 'message': 'You do not meet the minimum academic requirement for this opportunity.'}

        existing = conn.execute(
            'SELECT id FROM applications WHERE user_id = ? AND opportunity_id = ?',
            (user_id, opportunity_id),
        ).fetchone()
        if existing:
            conn.rollback()
            return {'success': False, 'message': 'You have already applied for this opportunity.'}

        application_cursor = conn.execute(
            'INSERT INTO applications (user_id, opportunity_id, status) VALUES (?, ?, ?)',
            (user_id, opportunity_id, 'Applied'),
        )
        conn.execute(
            'UPDATE opportunities SET application_count = application_count + 1 WHERE id = ?',
            (opportunity_id,),
        )
        conn.execute(
            """
            INSERT INTO application_status_history
                (application_id, actor_id, previous_status, new_status)
            VALUES (?, ?, NULL, 'Applied')
            """,
            (application_cursor.lastrowid, user_id),
        )
        conn.commit()
        return {'success': True, 'message': 'Application submitted successfully.'}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_learning_programs_for_skill(skill_name):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            'SELECT title, provider, description, duration, mode, is_demo FROM learning_programs WHERE LOWER(title) LIKE ? LIMIT 3',
            (f'%{skill_name.lower()}%',),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
