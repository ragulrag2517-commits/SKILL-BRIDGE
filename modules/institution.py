"""Database-backed institution dashboard data."""

from database.db import get_db_connection


def get_institution_summary(user_id):
    conn = get_db_connection()
    try:
        profile = conn.execute(
            'SELECT * FROM institution_profiles WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        institution_name = profile['institution_name'] if profile else None
        associated_students = 0
        internship_students = 0
        student_applications = 0
        selected_students = 0
        departments = []
        if institution_name:
            student_filter = 'LOWER(TRIM(sp.college)) = LOWER(TRIM(?))'
            associated_students = conn.execute(
                f"""
                SELECT COUNT(DISTINCT u.id)
                FROM users u JOIN student_profiles sp ON sp.user_id = u.id
                WHERE u.role = 'student' AND {student_filter}
                """,
                (institution_name,),
            ).fetchone()[0]
            internship_students = conn.execute(
                f"""
                SELECT COUNT(DISTINCT i.student_id)
                FROM internships i JOIN student_profiles sp ON sp.user_id = i.student_id
                WHERE i.student_id IS NOT NULL AND {student_filter}
                  AND LOWER(i.status) IN ('active', 'in progress')
                """,
                (institution_name,),
            ).fetchone()[0]
            student_applications = conn.execute(
                f"""
                SELECT COUNT(*) FROM applications a
                JOIN student_profiles sp ON sp.user_id = a.user_id
                WHERE {student_filter}
                """,
                (institution_name,),
            ).fetchone()[0]
            selected_students = conn.execute(
                f"""
                SELECT COUNT(DISTINCT a.user_id) FROM applications a
                JOIN student_profiles sp ON sp.user_id = a.user_id
                WHERE {student_filter} AND a.status = 'Selected'
                """,
                (institution_name,),
            ).fetchone()[0]
            departments = conn.execute(
                f"""
                SELECT COALESCE(NULLIF(TRIM(sp.branch), ''), 'Not specified') AS department,
                       COUNT(DISTINCT u.id) AS students
                FROM users u JOIN student_profiles sp ON sp.user_id = u.id
                WHERE u.role = 'student' AND {student_filter}
                GROUP BY department ORDER BY students DESC, department
                """,
                (institution_name,),
            ).fetchall()
        faculty_count = conn.execute(
            """
            SELECT COUNT(*) FROM users u
            JOIN academician_profiles ap ON ap.user_id = u.id
            WHERE u.role = 'academician' AND LOWER(TRIM(ap.institution_name)) = LOWER(TRIM(?))
            """,
            (institution_name or '',),
        ).fetchone()[0]
        collaboration_count = conn.execute(
            """
            SELECT COUNT(*) FROM collaborations c
            JOIN academician_profiles ap ON ap.user_id = c.organizer_id
            WHERE LOWER(TRIM(ap.institution_name)) = LOWER(TRIM(?))
            """,
            (institution_name or '',),
        ).fetchone()[0]
        activities = conn.execute(
            """
            SELECT title, message, created_at FROM notifications
            WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 5
            """,
            (user_id,),
        ).fetchall()
        return {
            'profile': profile,
            'counts': {
                'students': associated_students,
                'academicians': faculty_count,
                'internship_students': internship_students,
                'applications': student_applications,
                'selected': selected_students,
                'collaborations': collaboration_count,
            },
            'departments': departments,
            'recent_activities': activities,
        }
    finally:
        conn.close()
