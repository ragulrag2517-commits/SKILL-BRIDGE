"""Generate student-specific, data-driven career roadmaps."""

from __future__ import annotations

import json

ROADMAP_LIBRARY = {
    'Full Stack Developer': [
        {'learning_step': 'Frontend fundamentals', 'skill_to_develop': 'JavaScript', 'recommended_activity': 'Build responsive UI components and forms.', 'suggested_project': 'Responsive portfolio website', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Backend integration', 'skill_to_develop': 'Python', 'recommended_activity': 'Create a Flask API and integrate database operations.', 'suggested_project': 'Task management API', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Database discipline', 'skill_to_develop': 'SQL', 'recommended_activity': 'Practice joins, relationships, and query design.', 'suggested_project': 'Student dashboard data model', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Capstone delivery', 'skill_to_develop': 'Web Development', 'recommended_activity': 'Combine frontend and backend in a complete product.', 'suggested_project': 'End-to-end SkillBridge clone', 'status': 'Pending', 'progress': 0},
    ],
    'Python Developer': [
        {'learning_step': 'Python fundamentals', 'skill_to_develop': 'Python', 'recommended_activity': 'Practice data structures and API development.', 'suggested_project': 'Python automation script', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Problem solving', 'skill_to_develop': 'Problem Solving', 'recommended_activity': 'Solve algorithmic coding exercises weekly.', 'suggested_project': 'Debugging challenge set', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Data access design', 'skill_to_develop': 'SQL', 'recommended_activity': 'Design normalized data schemas and queries.', 'suggested_project': 'Inventory or student record app', 'status': 'Pending', 'progress': 0},
    ],
    'AI/ML Engineer': [
        {'learning_step': 'Machine learning foundations', 'skill_to_develop': 'Machine Learning', 'recommended_activity': 'Train and evaluate baseline models on structured data.', 'suggested_project': 'Prediction dashboard', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Data science workflow', 'skill_to_develop': 'Data Science', 'recommended_activity': 'Clean, shape, and visualize real-world datasets.', 'suggested_project': 'Customer analytics dashboard', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Research-driven model validation', 'skill_to_develop': 'Research Methodology', 'recommended_activity': 'Document experiments and interpret metrics clearly.', 'suggested_project': 'Model evaluation report', 'status': 'Pending', 'progress': 0},
    ],
    'Data Analyst': [
        {'learning_step': 'Data analysis foundations', 'skill_to_develop': 'Data Science', 'recommended_activity': 'Perform exploratory analysis with dashboards and metrics.', 'suggested_project': 'Public data dashboard', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Query fluency', 'skill_to_develop': 'SQL', 'recommended_activity': 'Master joins, aggregations, and performance metrics.', 'suggested_project': 'Business reporting database', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Communication', 'skill_to_develop': 'Communication', 'recommended_activity': 'Turn analysis into stakeholder-ready summaries.', 'suggested_project': 'Executive insights brief', 'status': 'Pending', 'progress': 0},
    ],
    'Healthcare Data Analyst': [
        {'learning_step': 'Healthcare datasets', 'skill_to_develop': 'Healthcare Data Analytics', 'recommended_activity': 'Analyze patient and public health record structures.', 'suggested_project': 'Healthcare KPI dashboard', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Clinical reporting', 'skill_to_develop': 'Research Methodology', 'recommended_activity': 'Map evidence to outcomes and treatment metrics.', 'suggested_project': 'Clinical insight case study', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Stakeholder communication', 'skill_to_develop': 'Communication', 'recommended_activity': 'Present findings with clarity and context for teams.', 'suggested_project': 'Digital health briefing deck', 'status': 'Pending', 'progress': 0},
    ],
    'Medical AI Developer': [
        {'learning_step': 'AI in healthcare', 'skill_to_develop': 'Healthcare Data Analytics', 'recommended_activity': 'Investigate machine learning use cases in public health and diagnostics.', 'suggested_project': 'Healthcare prediction dashboard', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Model validation', 'skill_to_develop': 'Machine Learning', 'recommended_activity': 'Compare model baselines and interpret patient-level metrics.', 'suggested_project': 'AI model evaluation notebook', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Clinical evidence', 'skill_to_develop': 'Research Methodology', 'recommended_activity': 'Translate results into reproducible clinical research artifacts.', 'suggested_project': 'Clinical ML protocol', 'status': 'Pending', 'progress': 0},
    ],
    'Biomedical Software Developer': [
        {'learning_step': 'Digital health product design', 'skill_to_develop': 'Web Development', 'recommended_activity': 'Create dashboards and interfaces for biomedical workflows.', 'suggested_project': 'Digital health portal mockup', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Research-backed engineering', 'skill_to_develop': 'Research Methodology', 'recommended_activity': 'Turn research findings into usable technical features.', 'suggested_project': 'Evidence-driven app feature', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Problem solving', 'skill_to_develop': 'Problem Solving', 'recommended_activity': 'Solve technical challenges grounded in healthcare use cases.', 'suggested_project': 'Healthcare problem casebook', 'status': 'Pending', 'progress': 0},
    ],
    'Digital Health Specialist': [
        {'learning_step': 'Digital care design', 'skill_to_develop': 'Communication', 'recommended_activity': 'Map health workflows to patient-friendly interfaces.', 'suggested_project': 'Digital health journey map', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Platform implementation', 'skill_to_develop': 'Web Development', 'recommended_activity': 'Prototype dashboards and product journeys.', 'suggested_project': 'Healthcare dashboard prototype', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Analytics with impact', 'skill_to_develop': 'Healthcare Data Analytics', 'recommended_activity': 'Connect analytics to treatment and patient outcomes.', 'suggested_project': 'Digital health analytics case study', 'status': 'Pending', 'progress': 0},
    ],
    'Clinical Research Data Analyst': [
        {'learning_step': 'Research data operations', 'skill_to_develop': 'Research Methodology', 'recommended_activity': 'Plan data collection and evidence reporting methods.', 'suggested_project': 'Research protocol summary', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Analytics governance', 'skill_to_develop': 'SQL', 'recommended_activity': 'Apply structured analysis methods to clinical datasets.', 'suggested_project': 'Clinical data query workbook', 'status': 'Pending', 'progress': 0},
        {'learning_step': 'Reporting', 'skill_to_develop': 'Communication', 'recommended_activity': 'Present outcome narratives and data-backed insights.', 'suggested_project': 'Research communication brief', 'status': 'Pending', 'progress': 0},
    ],
}


def generate_roadmap_for_goal(career_goal, student_skills=None, missing_skills=None):
    goal = career_goal or 'Full Stack Developer'
    steps = ROADMAP_LIBRARY.get(goal, ROADMAP_LIBRARY['Full Stack Developer'])
    student_skill_set = set(student_skills or [])
    missing_set = set(missing_skills or [])

    final_steps = []
    for step in steps:
        skill_name = step['skill_to_develop']
        if skill_name in student_skill_set:
            step['status'] = 'Completed'
            step['progress'] = 100
        elif skill_name in missing_set:
            step['status'] = 'Pending'
            step['progress'] = 20
        else:
            step['status'] = 'In Progress'
            step['progress'] = 50
        final_steps.append(step)
    return final_steps


def create_roadmap(goal):
    return {'career_goal': goal, 'steps': ROADMAP_LIBRARY.get(goal, ROADMAP_LIBRARY['Full Stack Developer'])}


def save_roadmap_for_user(user_id, goal, roadmap_steps):
    from database.db import get_db_connection

    conn = get_db_connection()
    try:
        average_progress = round(sum(step.get('progress', 0) for step in roadmap_steps) / len(roadmap_steps)) if roadmap_steps else 0
        conn.execute(
            'INSERT INTO career_roadmaps (user_id, career_goal, roadmap, progress) VALUES (?, ?, ?, ?)',
            (user_id, goal, json.dumps(roadmap_steps), average_progress),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_latest_roadmap_for_user(user_id):
    from database.db import get_db_connection

    conn = get_db_connection()
    try:
        row = conn.execute(
            'SELECT id, career_goal, roadmap, progress FROM career_roadmaps WHERE user_id = ? ORDER BY created_at DESC LIMIT 1',
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            'id': row['id'],
            'career_goal': row['career_goal'],
            'roadmap': json.loads(row['roadmap']) if row['roadmap'] else [],
            'progress': row['progress'],
        }
    finally:
        conn.close()


def update_roadmap_progress(user_id, roadmap_id, step_index, progress_value):
    from database.db import get_db_connection

    conn = get_db_connection()
    try:
        row = conn.execute(
            'SELECT roadmap FROM career_roadmaps WHERE id = ? AND user_id = ?',
            (roadmap_id, user_id),
        ).fetchone()
        if not row:
            return False

        roadmap = json.loads(row['roadmap']) if row['roadmap'] else []
        if step_index < 0 or step_index >= len(roadmap):
            return False

        roadmap[step_index]['progress'] = int(progress_value)
        if roadmap[step_index]['progress'] >= 100:
            roadmap[step_index]['status'] = 'Completed'
        elif roadmap[step_index]['progress'] > 0:
            roadmap[step_index]['status'] = 'In Progress'

        average_progress = round(sum(step.get('progress', 0) for step in roadmap) / len(roadmap)) if roadmap else 0
        conn.execute(
            'UPDATE career_roadmaps SET roadmap = ?, progress = ? WHERE id = ?',
            (json.dumps(roadmap), average_progress, roadmap_id),
        )
        conn.commit()
        return True
    finally:
        conn.close()
