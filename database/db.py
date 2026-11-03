import os
import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from config import BASE_DIR, DATABASE_PATH
from database.models import Base


SCHEMA_FILE = os.path.join(BASE_DIR, 'database', 'schema.sql')

engine = create_engine(
    f'sqlite:///{DATABASE_PATH}',
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def get_db_session():
    return SessionLocal()


def init_db():
    Base.metadata.create_all(bind=engine)
    conn = get_db_connection()
    try:
        with open(SCHEMA_FILE, 'r', encoding='utf-8') as schema_file:
            schema_sql = schema_file.read()
        if schema_sql.strip():
            conn.executescript(schema_sql)

        migrations = {
            'industry_profiles': {
                'location': 'TEXT',
                'contact_email': 'TEXT',
                'contact_phone': 'TEXT',
                'logo_filename': 'TEXT',
                'verification_requested_at': 'TEXT',
            },
            'student_profiles': {
                'resume_filename': 'TEXT',
            },
            'opportunities': {
                'qualification_requirements': 'TEXT',
                'minimum_cgpa': 'REAL',
                'openings': 'INTEGER NOT NULL DEFAULT 1',
                'status': "TEXT NOT NULL DEFAULT 'published'",
                'updated_at': 'TEXT',
                'is_demo': 'INTEGER NOT NULL DEFAULT 0',
            },
            'learning_programs': {
                'is_demo': 'INTEGER NOT NULL DEFAULT 0',
            },
            'opportunity_skills': {
                'skill_category': "TEXT NOT NULL DEFAULT 'technical'",
                'is_required': 'INTEGER NOT NULL DEFAULT 1',
            },
        }
        for table_name, columns in migrations.items():
            existing_columns = {
                row['name'] for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall()
            }
            for column_name, column_definition in columns.items():
                if column_name not in existing_columns:
                    conn.execute(
                        f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}'
                    )
        conn.execute(
            """
            UPDATE opportunities SET is_demo = 1
            WHERE company_id = (
                SELECT id FROM users WHERE email = 'industry@skillbridge.demo'
            ) AND title IN (
                'Healthcare Data Analyst Intern', 'Biomedical Software Developer',
                'Clinical Research Data Associate', 'Digital Health Product Engineer'
            )
            """
        )
        conn.execute(
            """
            UPDATE learning_programs SET is_demo = 1
            WHERE provider = 'SkillBridge Academy' AND title IN (
                'Python fundamentals', 'SQL and database management', 'React development',
                'Machine learning fundamentals', 'Data visualization',
                'Healthcare data analytics', 'Research methodology'
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_demo_data():
    from database.seed import seed_database
    seed_database()


if __name__ == '__main__':
    init_db()
    seed_demo_data()
