"""Database-backed academician dashboard data."""

from database.db import get_db_connection


def get_academician_summary(user_id):
    conn = get_db_connection()
    try:
        profile = conn.execute(
            'SELECT * FROM academician_profiles WHERE user_id = ?',
            (user_id,),
        ).fetchone()
        counts = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM opportunities
               WHERE status = 'published' AND LOWER(opportunity_type) LIKE '%research%'
                 AND (deadline IS NULL OR date(deadline) >= date('now'))) AS research_opportunities,
              (SELECT COUNT(*) FROM applications WHERE user_id = ?) AS applications,
              (SELECT COUNT(*) FROM learning_programs) AS programmes,
              (SELECT COUNT(*) FROM program_registrations WHERE user_id = ?) AS registrations,
              (SELECT COUNT(*) FROM collaborations WHERE organizer_id = ?) AS collaborations,
              (SELECT COUNT(*) FROM mentorships WHERE mentor_id = ?) AS mentorships
            """,
            (user_id, user_id, user_id, user_id),
        ).fetchone()
        notifications = conn.execute(
            """
            SELECT title, message, created_at FROM notifications
            WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 5
            """,
            (user_id,),
        ).fetchall()
        return {
            'profile': profile,
            'counts': counts,
            'notifications': notifications,
        }
    finally:
        conn.close()
