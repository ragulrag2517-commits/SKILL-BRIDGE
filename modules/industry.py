"""Database-backed company, recruitment, and candidate operations."""

from __future__ import annotations

from database.db import get_db_connection

APPLICATION_STATUSES = ('Applied', 'Shortlisted', 'Rejected', 'Selected')
STATUS_TRANSITIONS = {
    'Applied': {'Shortlisted', 'Rejected', 'Selected'},
    'Shortlisted': {'Rejected', 'Selected'},
    'Rejected': set(),
    'Selected': set(),
}


def ensure_company_profile(user_id):
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO industry_profiles (user_id, verification_status)
            VALUES (?, 'pending')
            """,
            (user_id,),
        )
        conn.commit()
        return conn.execute(
            'SELECT * FROM industry_profiles WHERE user_id = ?',
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def get_company_profile(user_id):
    conn = get_db_connection()
    try:
        return conn.execute(
            'SELECT * FROM industry_profiles WHERE user_id = ?',
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def get_company_dashboard_data(user_id):
    conn = get_db_connection()
    try:
        profile = conn.execute(
            'SELECT * FROM industry_profiles WHERE user_id = ?',
            (user_id,),
        ).fetchone()

        counts = conn.execute(
            """
            SELECT
              COUNT(DISTINCT o.id) AS total_opportunities,
              SUM(CASE WHEN o.status = 'published'
                    AND LOWER(o.opportunity_type) = 'internship'
                    AND (o.deadline IS NULL OR o.deadline >= date('now')) THEN 1 ELSE 0 END) AS active_internships,
              SUM(CASE WHEN o.status = 'published'
                    AND LOWER(o.opportunity_type) IN ('full-time job', 'job')
                    AND (o.deadline IS NULL OR o.deadline >= date('now')) THEN 1 ELSE 0 END) AS active_jobs,
              COUNT(DISTINCT a.id) AS total_applications,
              SUM(CASE WHEN a.status = 'Shortlisted' THEN 1 ELSE 0 END) AS shortlisted,
              SUM(CASE WHEN a.status = 'Selected' THEN 1 ELSE 0 END) AS selected,
              SUM(CASE WHEN a.status = 'Rejected' THEN 1 ELSE 0 END) AS rejected
            FROM opportunities o
            LEFT JOIN applications a ON a.opportunity_id = o.id
            WHERE o.company_id = ?
            """,
            (user_id,),
        ).fetchone()

        recent_applications = conn.execute(
            """
            SELECT a.id AS application_id, a.status, a.applied_at,
                   u.first_name, u.last_name, o.id AS opportunity_id, o.title
            FROM applications a
            JOIN opportunities o ON o.id = a.opportunity_id
            JOIN users u ON u.id = a.user_id
            WHERE o.company_id = ?
            ORDER BY a.applied_at DESC, a.id DESC
            LIMIT 8
            """,
            (user_id,),
        ).fetchall()
        notifications = conn.execute(
            """
            SELECT title, message, created_at, is_read
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 5
            """,
            (user_id,),
        ).fetchall()

        summary = {key: int(counts[key] or 0) for key in (
            'total_opportunities', 'active_internships', 'active_jobs',
            'total_applications', 'shortlisted', 'selected', 'rejected',
        )}
        summary['verification_status'] = profile['verification_status'] if profile else 'pending'
        summary['company_name'] = profile['company_name'] if profile and profile['company_name'] else 'Company profile not completed'
        return {
            'profile': profile,
            'summary': summary,
            'recent_applications': [dict(row) for row in recent_applications],
            'notifications': [dict(row) for row in notifications],
        }
    finally:
        conn.close()


def get_company_opportunities(user_id):
    conn = get_db_connection()
    try:
        opportunities = conn.execute(
            """
            SELECT o.*,
                   (SELECT COUNT(*) FROM applications a WHERE a.opportunity_id = o.id) AS application_total
            FROM opportunities o
            WHERE o.company_id = ?
            ORDER BY o.created_at DESC, o.id DESC
            """,
            (user_id,),
        ).fetchall()
        result = []
        for opportunity in opportunities:
            row = dict(opportunity)
            row['technical_skills'] = [
                skill['skill'] for skill in conn.execute(
                    """
                    SELECT skill FROM opportunity_skills
                    WHERE opportunity_id = ? AND LOWER(skill_category) = 'technical'
                    ORDER BY skill
                    """,
                    (opportunity['id'],),
                ).fetchall()
            ]
            row['soft_skills'] = [
                skill['skill'] for skill in conn.execute(
                    """
                    SELECT skill FROM opportunity_skills
                    WHERE opportunity_id = ? AND LOWER(skill_category) = 'soft'
                    ORDER BY skill
                    """,
                    (opportunity['id'],),
                ).fetchall()
            ]
            result.append(row)
        return result
    finally:
        conn.close()


def get_industry_analytics(user_id):
    conn = get_db_connection()
    try:
        applications_by_opportunity = conn.execute(
            """
            SELECT o.title, COUNT(a.id) AS total
            FROM opportunities o
            LEFT JOIN applications a ON a.opportunity_id = o.id
            WHERE o.company_id = ?
            GROUP BY o.id, o.title
            ORDER BY total DESC, o.title
            """,
            (user_id,),
        ).fetchall()
        status_counts = conn.execute(
            """
            SELECT a.status, COUNT(*) AS total
            FROM applications a
            JOIN opportunities o ON o.id = a.opportunity_id
            WHERE o.company_id = ?
            GROUP BY a.status
            """,
            (user_id,),
        ).fetchall()
        demanded_skills = conn.execute(
            """
            SELECT MIN(os.skill) AS skill, COUNT(DISTINCT os.opportunity_id) AS demand
            FROM opportunity_skills os
            JOIN opportunities o ON o.id = os.opportunity_id
            WHERE o.company_id = ? AND os.is_required = 1
            GROUP BY LOWER(os.skill)
            ORDER BY demand DESC, os.skill
            LIMIT 10
            """,
            (user_id,),
        ).fetchall()
        return {
            'applications_by_opportunity': [dict(row) for row in applications_by_opportunity],
            'status_counts': {row['status']: row['total'] for row in status_counts},
            'demanded_skills': [dict(row) for row in demanded_skills],
        }
    finally:
        conn.close()


def get_company_candidates(user_id, search='', status='', opportunity_id=None):
    clauses = ['o.company_id = ?']
    params = [user_id]
    if status in APPLICATION_STATUSES:
        clauses.append('a.status = ?')
        params.append(status)
    if opportunity_id:
        clauses.append('o.id = ?')
        params.append(opportunity_id)
    if search:
        search_pattern = f'%{search}%'
        clauses.append(
            """
            (u.first_name LIKE ? OR u.last_name LIKE ? OR u.email LIKE ?
             OR o.title LIKE ? OR COALESCE(sp.college, '') LIKE ?
             OR COALESCE(sp.degree, '') LIKE ? OR COALESCE(sp.branch, '') LIKE ?)
            """
        )
        params.extend([search_pattern] * 7)

    conn = get_db_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT a.id AS application_id, a.user_id AS student_id, a.status, a.applied_at,
                   u.first_name, u.last_name, u.email, o.id AS opportunity_id,
                   o.title AS opportunity_title, o.minimum_cgpa, o.qualification_requirements,
                   sp.college, sp.degree, sp.branch, sp.year_of_study, sp.cgpa,
                   sp.resume_filename, p.headline AS portfolio_headline,
                   p.summary AS portfolio_summary, p.projects AS portfolio_projects
            FROM applications a
            JOIN opportunities o ON o.id = a.opportunity_id
            JOIN users u ON u.id = a.user_id
            LEFT JOIN student_profiles sp ON sp.user_id = u.id
            LEFT JOIN portfolios p ON p.user_id = u.id
            WHERE {' AND '.join(clauses)}
            ORDER BY a.applied_at DESC, a.id DESC
            """,
            params,
        ).fetchall()

        candidates = []
        for row in rows:
            candidate = dict(row)
            candidate['skills'] = [
                dict(skill) for skill in conn.execute(
                    """
                    SELECT s.name, s.category, ss.proficiency
                    FROM student_skills ss
                    JOIN skills s ON s.id = ss.skill_id
                    WHERE ss.user_id = ?
                    ORDER BY LOWER(s.category), s.name
                    """,
                    (row['student_id'],),
                ).fetchall()
            ]
            candidate['skill_requirements'] = [
                {
                    'name': requirement['skill'],
                    'category': requirement['skill_category'],
                    'weight': 10 if requirement['is_required'] else 3,
                    'required': bool(requirement['is_required']),
                }
                for requirement in conn.execute(
                    """
                    SELECT skill, skill_category, is_required
                    FROM opportunity_skills
                    WHERE opportunity_id = ?
                    ORDER BY skill_category, skill
                    """,
                    (row['opportunity_id'],),
                ).fetchall()
            ]
            candidates.append(candidate)
        return candidates
    finally:
        conn.close()


def update_application_status(company_user_id, actor_id, application_id, new_status):
    if new_status not in APPLICATION_STATUSES:
        return False, 'Invalid application status.'

    conn = get_db_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        application = conn.execute(
            """
            SELECT a.id, a.user_id, a.status, o.title
            FROM applications a
            JOIN opportunities o ON o.id = a.opportunity_id
            WHERE a.id = ? AND o.company_id = ?
            """,
            (application_id, company_user_id),
        ).fetchone()
        if application is None:
            conn.rollback()
            return False, 'Application not found for your company.'
        old_status = application['status']
        if new_status == old_status:
            conn.rollback()
            return False, 'Application already has that status.'
        if new_status not in STATUS_TRANSITIONS.get(old_status, set()):
            conn.rollback()
            return False, f'Cannot change application from {old_status} to {new_status}.'

        conn.execute(
            'UPDATE applications SET status = ? WHERE id = ?',
            (new_status, application_id),
        )
        conn.execute(
            """
            INSERT INTO application_status_history
                (application_id, actor_id, previous_status, new_status)
            VALUES (?, ?, ?, ?)
            """,
            (application_id, actor_id, old_status, new_status),
        )
        conn.execute(
            """
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, ?, ?)
            """,
            (
                application['user_id'],
                'Application status updated',
                f'Your application for {application["title"]} is now {new_status}.',
            ),
        )
        conn.commit()
        return True, f'Application marked {new_status.lower()}.'
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_application_history(company_user_id, application_id):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT h.previous_status, h.new_status, h.changed_at,
                   u.first_name, u.last_name
            FROM application_status_history h
            JOIN applications a ON a.id = h.application_id
            JOIN opportunities o ON o.id = a.opportunity_id
            LEFT JOIN users u ON u.id = h.actor_id
            WHERE h.application_id = ? AND o.company_id = ?
            ORDER BY h.changed_at DESC, h.id DESC
            """,
            (application_id, company_user_id),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
