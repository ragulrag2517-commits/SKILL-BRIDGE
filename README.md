# SkillBridge

SkillBridge is a Flask application for academia-industry collaboration, student skill assessment, and opportunity management. It uses SQLite for persistence and provides role-based access for students, industries, academicians, institutions, and administrators.

## Current implementation

- Registration and login with hashed passwords, CSRF protection, and role-based routes.
- Student profiles, skill assessment, database-backed skill analysis, career roadmaps, opportunity recommendations, and applications.
- Industry company profiles, verification requests, opportunity management, candidate review, application status updates, and recruitment analytics.
- Academician, institution, and administrator dashboards with counts and activity read from the database.
- Private student resume downloads for the student and industries that received that student's application.
- SQLite schema initialization with additive column migrations.

The database schema also contains tables reserved for faculty programmes, collaborations, internships, portfolios, and certificates. Not all of those workflows have complete user-facing routes yet; see [Known limitations](#known-limitations). Dashboard counts do not imply those workflows are fully implemented.

## Roles

| Role | Main capabilities |
|---|---|
| Student | Profile, assessment, skill analysis, career roadmap, opportunity browsing and applications |
| Industry | Company profile, verification request, opportunities, applicants, recruitment status, analytics |
| Academician | Dashboard and account-specific activity summaries |
| Institution | Dashboard with student totals based on matching institution names in student profiles |
| Administrator | Database-backed platform summary |

Admin account creation is a separate CLI action and public registration cannot assign the admin role.

## Technology

- Python 3.10+
- Flask 3.0
- SQLAlchemy 2.0 for user authentication
- SQLite for the application data
- Jinja templates, Bootstrap 5, CSS, and JavaScript
- Werkzeug password hashing and file upload validation
- Rule-based skill matching; no paid AI API is used
- Seeded development opportunities and learning programmes are labeled as demo records

## Project layout

```text
SkillBridge/
├── app.py
├── config.py
├── requirements.txt
├── database/
│   ├── db.py
│   ├── models.py
│   ├── schema.sql
│   └── seed.py
├── modules/
├── static/
├── templates/
├── tests/
└── uploads/                 # Runtime uploads; not committed
```

## Install and run in VS Code PowerShell

From the project directory:

```powershell
cd C:\Users\ADMIN\Desktop\SkillBridge
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:SKILLBRIDGE_ENV = "development"
$env:SKILLBRIDGE_SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python app.py
```

Open <http://127.0.0.1:5000>. The bundled server binds to loopback and runs with debug mode disabled. Keep the same secret key in the same PowerShell session while using the app.

For local development, demo data is enabled by default. To disable automatic demo seeding, set:

```powershell
$env:SKILLBRIDGE_DEMO_DATA = "false"
```

Demo account credentials are shown only in development mode on the login page. Demo accounts and seeded records are for local testing, not production use.

## Administrator account

Create an admin interactively after installing dependencies:

```powershell
.\.venv\Scripts\Activate.ps1
$env:SKILLBRIDGE_ENV = "development"
python -m flask --app app create-admin
```

The command prompts for a name, email, and a password of at least 12 characters. It does not print or store a plaintext password.

## Configuration

The app loads a local `.env` file when present. `.env` is ignored by Git. See [.env.example](./.env.example) for supported settings.

| Variable | Purpose |
|---|---|
| `SKILLBRIDGE_ENV` | `development` or `production`; production requires an explicit secret and enables secure session cookies |
| `SKILLBRIDGE_SECRET_KEY` | Flask session-signing key; use a random private value |
| `SKILLBRIDGE_DATABASE_PATH` | SQLite file path; defaults to `database/skillbridge.db` |
| `SKILLBRIDGE_UPLOAD_FOLDER` | Upload storage path; defaults to `uploads/` |
| `SKILLBRIDGE_DEMO_DATA` | Enable demo seeding in non-production environments; defaults to `true` |

Generate a secret without committing it:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

For production, set `SKILLBRIDGE_ENV=production`, `SKILLBRIDGE_SECRET_KEY`, `SKILLBRIDGE_DATABASE_PATH`, and `SKILLBRIDGE_DEMO_DATA=false`. Use a separate production database path and back it up. Startup does not delete database records, but schema changes are currently applied through safe `CREATE TABLE IF NOT EXISTS` and additive column checks rather than a versioned migration framework.

`python app.py` is for local development only. No production deployment has been performed or claimed; deploy behind a production WSGI server and HTTPS reverse proxy before exposing the service publicly.

## Database and uploads

The schema is in `database/schema.sql`. The application initializes tables and applies the additive migrations in `database/db.py` on first request. Existing database records are not dropped. Uploads are stored under `uploads/`, limited by configured request size and file type/signature checks, and are excluded from Git. Configure persistent storage and backups for a deployment.

## Tests

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest -q
```

The current suite covers smoke pages, registration, login, student assessment and analysis, opportunity applications, career roadmap progress, industry route protection, and logout.

## Known limitations

- Academician, institution, and admin areas are database-backed summary dashboards, not complete management modules.
- Faculty profile editing, FDP lifecycle/registration, research applications, collaboration proposals, institution verification and reporting, full admin moderation/audit, student portfolio editing, placement management, and internship progress/mentor workflows still need end-to-end implementation and tests.
- Institution-to-student association currently depends on matching the institution name with the student's `college` field; there is no institution foreign key or verification workflow yet.
- Skill matching is deterministic/rule-based and is not an AI hiring decision. Demo records can affect development totals.
- Production deployment, database migration execution on a production copy, and mobile/browser visual testing have not been performed.
