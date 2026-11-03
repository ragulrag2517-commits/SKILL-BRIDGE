"""Weighted skill compatibility and gap analysis for SkillBridge."""

from __future__ import annotations

from typing import Any, Iterable

INDUSTRY_REQUIREMENTS = [
    {'name': 'Python', 'category': 'Technical', 'weight': 18, 'required': True},
    {'name': 'JavaScript', 'category': 'Technical', 'weight': 15, 'required': True},
    {'name': 'SQL', 'category': 'Technical', 'weight': 16, 'required': True},
    {'name': 'Web Development', 'category': 'Technical', 'weight': 14, 'required': True},
    {'name': 'Data Science', 'category': 'Technical', 'weight': 15, 'required': True},
    {'name': 'Machine Learning', 'category': 'Technical', 'weight': 12, 'required': False},
    {'name': 'Communication', 'category': 'Soft', 'weight': 10, 'required': True},
    {'name': 'Problem Solving', 'category': 'Soft', 'weight': 12, 'required': True},
    {'name': 'Research Methodology', 'category': 'Research', 'weight': 10, 'required': False},
    {'name': 'Healthcare Data Analytics', 'category': 'Healthcare', 'weight': 12, 'required': False},
]

CAREER_ROLES = {
    'Full Stack Developer': ['Python', 'JavaScript', 'Web Development', 'SQL', 'Communication'],
    'Python Developer': ['Python', 'SQL', 'Problem Solving', 'Web Development'],
    'AI/ML Engineer': ['Python', 'Data Science', 'Machine Learning', 'SQL', 'Problem Solving'],
    'Data Analyst': ['SQL', 'Data Science', 'Communication', 'Problem Solving'],
    'Healthcare Data Analyst': ['SQL', 'Healthcare Data Analytics', 'Communication', 'Data Science'],
    'Medical AI Developer': ['Python', 'Machine Learning', 'Healthcare Data Analytics', 'Research Methodology'],
    'Biomedical Software Developer': ['Python', 'Web Development', 'Research Methodology', 'Problem Solving'],
    'Digital Health Specialist': ['Python', 'Communication', 'Web Development', 'Healthcare Data Analytics'],
    'Clinical Research Data Analyst': ['SQL', 'Research Methodology', 'Communication', 'Healthcare Data Analytics'],
}

INDUSTRY_SECTORS = {
    'Healthcare': ['Healthcare Data Analytics', 'Research Methodology', 'Communication'],
    'Technology': ['Python', 'JavaScript', 'Web Development', 'SQL'],
    'Research': ['Research Methodology', 'Data Science', 'Problem Solving'],
    'Digital Health': ['Healthcare Data Analytics', 'Python', 'Communication', 'Web Development'],
}


def _normalize_skill_map(student_skills: Iterable[Any]) -> dict[str, int]:
    skills: dict[str, int] = {}
    for skill in student_skills:
        if isinstance(skill, dict):
            name = (skill.get('name') or skill.get('skill') or '').strip()
            proficiency = int(skill.get('proficiency', 0) or 0)
        else:
            name = str(skill).strip()
            proficiency = 100

        if not name:
            continue
        skills[name] = max(skills.get(name, 0), proficiency)
    return skills


def _skill_status(proficiency: int) -> str:
    if proficiency >= 80:
        return 'matched'
    if proficiency >= 35:
        return 'partial'
    return 'missing'


def analyze_skills(student_skills, industry_requirements=None):
    requirements = industry_requirements or INDUSTRY_REQUIREMENTS
    skills_map = _normalize_skill_map(student_skills)

    has_required_skills = any(item.get('required', True) for item in requirements)
    required_weight_total = sum(item['weight'] for item in requirements if item.get('required', True))
    if not has_required_skills:
        required_weight_total = sum(item['weight'] for item in requirements)

    matched = []
    partial = []
    missing = []
    strong_skills = []
    improvement_skills = []
    weighted_match_total = 0
    weighted_proficiency_total = 0
    chart_labels = []
    chart_values = []

    for item in requirements:
        name = item['name']
        weight = item['weight']
        proficiency = skills_map.get(name, 0)
        contributes_to_score = item.get('required', True) or not has_required_skills
        chart_labels.append(name)
        chart_values.append(proficiency)

        status = _skill_status(proficiency)
        if status == 'matched':
            matched.append(name)
            if contributes_to_score:
                weighted_match_total += weight
            strong_skills.append(name) if proficiency >= 80 else None
            if contributes_to_score:
                weighted_proficiency_total += weight * (proficiency / 100)
        elif status == 'partial':
            partial.append(name)
            if contributes_to_score:
                weighted_proficiency_total += weight * (proficiency / 100)
            improvement_skills.append(name)
        else:
            missing.append(name)
            improvement_skills.append(name)

    compatibility = round((weighted_match_total / required_weight_total) * 100) if required_weight_total else 0
    proficiency_compatibility = round((weighted_proficiency_total / required_weight_total) * 100) if required_weight_total else 0

    if compatibility >= 75:
        eligibility = 'Eligible'
    elif compatibility >= 50:
        eligibility = 'Conditional'
    else:
        eligibility = 'Not yet eligible'

    role_matches = []
    for role, role_skills in CAREER_ROLES.items():
        overlap = set(role_skills) & set(skills_map)
        score = round((len(overlap) / len(role_skills)) * 100) if role_skills else 0
        if score >= 40:
            role_matches.append({'role': role, 'match': score})
    role_matches = sorted(role_matches, key=lambda entry: entry['match'], reverse=True)[:5]

    industries = []
    for industry, industry_skills in INDUSTRY_SECTORS.items():
        overlap = set(industry_skills) & set(skills_map)
        score = round((len(overlap) / len(industry_skills)) * 100) if industry_skills else 0
        if score > 0:
            industries.append({'industry': industry, 'match': score})
    industries = sorted(industries, key=lambda entry: entry['match'], reverse=True)[:5]

    recommendations = [
        'Strengthen SQL and analytical workflows to improve role readiness.',
        'Prioritize learning tracks aligned to your weakest required skills.',
        'Build a portfolio project that demonstrates your strongest technical skills.',
    ]

    learning_recommendations = []
    for skill in missing[:4]:
        if skill == 'Python':
            learning_recommendations.append({'skill': skill, 'topic': 'Python fundamentals', 'activity': 'Complete a hands-on Python module and build a small automation project.'})
        elif skill == 'SQL':
            learning_recommendations.append({'skill': skill, 'topic': 'SQL and database management', 'activity': 'Practice joins, aggregations, and query optimization using realistic datasets.'})
        elif skill == 'JavaScript':
            learning_recommendations.append({'skill': skill, 'topic': 'JavaScript and frontend development', 'activity': 'Build interactive UI components and state-driven workflows.'})
        elif skill == 'Data Science':
            learning_recommendations.append({'skill': skill, 'topic': 'Data science fundamentals', 'activity': 'Explore data cleaning, exploratory analysis, and metrics dashboards.'})
        elif skill == 'Machine Learning':
            learning_recommendations.append({'skill': skill, 'topic': 'Machine learning fundamentals', 'activity': 'Work through classification and regression exercises on public datasets.'})
        elif skill == 'Research Methodology':
            learning_recommendations.append({'skill': skill, 'topic': 'Research methodology', 'activity': 'Design a small research workflow with literature review and structured metrics.'})
        elif skill == 'Healthcare Data Analytics':
            learning_recommendations.append({'skill': skill, 'topic': 'Healthcare data analytics', 'activity': 'Study patient datasets, cohort analysis, and outcome reporting tasks.'})
        else:
            learning_recommendations.append({'skill': skill, 'topic': skill, 'activity': 'Practice guided projects and validate progress with measurable outcomes.'})

    if not learning_recommendations and partial:
        for skill in partial[:2]:
            learning_recommendations.append({'skill': skill, 'topic': skill, 'activity': 'Increase proficiency through targeted practice and portfolio evidence.'})

    return {
        'matched': matched,
        'missing': missing,
        'partial': partial,
        'strong_skills': strong_skills,
        'skills_needing_improvement': improvement_skills,
        'compatibility': compatibility,
        'proficiency_compatibility': proficiency_compatibility,
        'eligibility': eligibility,
        'career_roles': role_matches,
        'recommended_industries': industries,
        'recommendations': recommendations,
        'learning_recommendations': learning_recommendations,
        'chart_labels': chart_labels,
        'chart_values': chart_values,
        'required_skills': [item['name'] for item in requirements],
        'skill_gap_summary': {
            'matched_count': len(matched),
            'missing_count': len(missing),
            'partial_count': len(partial),
        },
    }
