"""Database-backed administrative dashboard data."""

from database.db import get_db_connection


def get_admin_summary():
    conn = get_db_connection()
    try:
        users_by_role = {
            row['role']: row['total']
            for row in conn.execute(
                'SELECT role, COUNT(*) AS total FROM users GROUP BY role'
            ).fetchall()
        }
        counts = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM users) AS total_users,
              (SELECT COUNT(*) FROM industry_profiles WHERE verification_status = 'pending') AS pending_industries,
              (SELECT COUNT(*) FROM opportunities) AS total_opportunities,
              (SELECT COUNT(*) FROM applications) AS total_applications,
              (SELECT COUNT(*) FROM collaborations) AS total_collaborations
            """
        ).fetchone()
        recent_users = conn.execute(
            """
            SELECT first_name, last_name, role, created_at
            FROM users ORDER BY created_at DESC, id DESC LIMIT 8
            """
        ).fetchall()
        return {
            'users_by_role': users_by_role,
            'counts': counts,
            'recent_users': recent_users,
        }
    finally:
        conn.close()
