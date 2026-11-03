PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('student','industry','academician','institution','admin')),
    phone TEXT,
    avatar TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    college TEXT,
    degree TEXT,
    branch TEXT,
    year_of_study INTEGER,
    cgpa REAL,
    bio TEXT,
    interest_area TEXT,
    resume_filename TEXT,
    resume_data BLOB,
    placement_readiness INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS industry_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    company_name TEXT,
    company_size TEXT,
    industry_sector TEXT,
    website TEXT,
    location TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    logo_filename TEXT,
    verification_status TEXT DEFAULT 'pending',
    verification_requested_at TEXT,
    company_description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS academician_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    institution_name TEXT,
    department TEXT,
    designation TEXT,
    research_area TEXT,
    experience_years INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS institution_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    institution_name TEXT,
    type TEXT,
    accreditation TEXT,
    location TEXT,
    established_year INTEGER,
    contact_email TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    description TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    proficiency INTEGER DEFAULT 0,
    source TEXT DEFAULT 'assessment',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, skill_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    category TEXT,
    score INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS assessment_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    selected_option TEXT,
    is_correct INTEGER DEFAULT 0,
    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS skill_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    matched_skills TEXT,
    missing_skills TEXT,
    compatibility INTEGER DEFAULT 0,
    recommendations TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    title TEXT NOT NULL,
    opportunity_type TEXT NOT NULL,
    description TEXT,
    location TEXT,
    mode TEXT,
    stipend TEXT,
    duration TEXT,
    deadline TEXT,
    qualification_requirements TEXT,
    minimum_cgpa REAL,
    openings INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'published',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    application_count INTEGER DEFAULT 0,
    is_approved INTEGER DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS opportunity_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id INTEGER NOT NULL,
    skill TEXT NOT NULL,
    skill_category TEXT NOT NULL DEFAULT 'technical',
    is_required INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    opportunity_id INTEGER NOT NULL,
    status TEXT DEFAULT 'Applied',
    applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, opportunity_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (opportunity_id) REFERENCES opportunities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS application_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    actor_id INTEGER,
    previous_status TEXT,
    new_status TEXT NOT NULL,
    changed_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS learning_programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    provider TEXT,
    description TEXT,
    duration TEXT,
    mode TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS program_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    program_id INTEGER NOT NULL,
    status TEXT DEFAULT 'registered',
    registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, program_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (program_id) REFERENCES learning_programs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS collaborations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    type TEXT,
    description TEXT,
    organizer_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS mentorships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    mentor_id INTEGER,
    student_id INTEGER,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (mentor_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS internships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company_id INTEGER,
    student_id INTEGER,
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS internship_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id INTEGER NOT NULL,
    task_name TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internship_id) REFERENCES internships(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mentor_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    internship_id INTEGER NOT NULL,
    mentor_id INTEGER,
    feedback TEXT,
    rating INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (internship_id) REFERENCES internships(id) ON DELETE CASCADE,
    FOREIGN KEY (mentor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS certificates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    issuer TEXT,
    issued_date TEXT,
    file_path TEXT,
    verification_status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS portfolios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    headline TEXT,
    summary TEXT,
    projects TEXT,
    achievements TEXT,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS career_roadmaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    career_goal TEXT NOT NULL,
    roadmap TEXT,
    progress INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_student_skills_user ON student_skills(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_opportunity ON applications(opportunity_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_company ON opportunities(company_id);
CREATE INDEX IF NOT EXISTS idx_application_history_application ON application_status_history(application_id);
