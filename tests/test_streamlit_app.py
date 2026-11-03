from pathlib import Path

from streamlit.testing.v1 import AppTest
from werkzeug.security import generate_password_hash

from database.db import get_db_session
from database.models import User


STREAMLIT_APP = Path(__file__).resolve().parents[1] / 'streamlit_app.py'


def test_streamlit_student_dashboard_uses_authenticated_database_user():
    db = get_db_session()
    user = User(
        first_name='Streamlit',
        last_name='Student',
        email='streamlit-student@example.com',
        password_hash=generate_password_hash('test-password-123'),
        role='student',
        is_active=True,
    )
    db.add(user)
    db.commit()
    user_id = user.id
    db.close()

    app = AppTest.from_file(str(STREAMLIT_APP))
    app.session_state['user_id'] = user_id
    app.run(timeout=20)

    assert not app.exception
    assert [title.value for title in app.title] == ['Welcome, Streamlit']
