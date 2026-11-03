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

## Deploy to PythonAnywhere

The repository includes [wsgi.py](./wsgi.py) as the WSGI entry point. It defaults to production mode, disables demo-data seeding, and stores the SQLite database and uploads under the ignored `instance/` directory. Set `SKILLBRIDGE_SECRET_KEY` in PythonAnywhere's WSGI configuration before importing the application; production startup intentionally fails if the key is missing.

1. Upload the project to your PythonAnywhere home directory (for example, `/home/YOUR_USERNAME/SkillBridge`) using the PythonAnywhere Files page or your own Git repository. Do not upload `.venv`, `.env`, `instance/`, or any database containing personal data.
2. In a PythonAnywhere Bash console, create the virtual environment and install dependencies:

   ```bash
   cd ~/SkillBridge
   python3.12 -m venv ~/.virtualenvs/skillbridge
   source ~/.virtualenvs/skillbridge/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   mkdir -p ~/var/skillbridge-uploads
   ```

3. In the PythonAnywhere **Web** tab, create a manual-config web app using the same Python version as the virtual environment. Set the virtualenv path to `/home/YOUR_USERNAME/.virtualenvs/skillbridge`.
4. Open the WSGI configuration file shown in the Web tab. Keep its existing file location, and replace its contents with the following after substituting your PythonAnywhere username and a newly generated secret:

   ```python
   import os
   import sys

   project_home = "/home/YOUR_USERNAME/SkillBridge"
   data_home = "/home/YOUR_USERNAME/var"

   if project_home not in sys.path:
       sys.path.insert(0, project_home)

   os.makedirs(data_home, exist_ok=True)
   os.environ["SKILLBRIDGE_ENV"] = "production"
   os.environ["SKILLBRIDGE_SECRET_KEY"] = "PASTE_A_PRIVATE_RANDOM_SECRET_HERE"
   os.environ["SKILLBRIDGE_DATABASE_PATH"] = os.path.join(data_home, "skillbridge.db")
   os.environ["SKILLBRIDGE_UPLOAD_FOLDER"] = os.path.join(data_home, "skillbridge-uploads")
   os.environ["SKILLBRIDGE_DEMO_DATA"] = "false"

   from wsgi import application
   ```

   Generate the secret in a Bash console with `python -c 'import secrets; print(secrets.token_hex(32))'`. Paste it only into the PythonAnywhere WSGI configuration; do not commit it, put it in a public repository, or share it. Because the SQLite file and uploads are stored outside the code directory, updating the application files will not overwrite runtime data.
5. In the Web tab, set the static files mapping from `/static/` to `/home/YOUR_USERNAME/SkillBridge/static/`, then click **Reload**. Visit your PythonAnywhere site and verify that the home page and `/health` return successfully.
6. Create the first administrator from a Bash console using the same production settings as the WSGI file:

   ```bash
   cd ~/SkillBridge
   source ~/.virtualenvs/skillbridge/bin/activate
   export SKILLBRIDGE_ENV=production
   export SKILLBRIDGE_DATABASE_PATH="$HOME/var/skillbridge.db"
   export SKILLBRIDGE_UPLOAD_FOLDER="$HOME/var/skillbridge-uploads"
   export SKILLBRIDGE_DEMO_DATA=false
   read -s -p "Paste the same secret used in the WSGI file: " SKILLBRIDGE_SECRET_KEY
   echo
   export SKILLBRIDGE_SECRET_KEY
   python -m flask --app app create-admin
   unset SKILLBRIDGE_SECRET_KEY
   ```

   The command prompts for administrator details and a password; it does not print or store the plaintext password. Do not use the development demo accounts in production.

Use the PythonAnywhere error log if the web app fails to import or start. Back up the production SQLite database and uploads regularly, restrict access to backups, and use HTTPS. SQLite is suitable for a small, low-traffic deployment; use a managed database and a migration plan before scaling or making schema changes to production data. Deployment is not complete until the Web tab has been reloaded and the live site has been verified.

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
