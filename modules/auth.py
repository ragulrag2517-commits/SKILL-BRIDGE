"""Authentication helpers for SkillBridge."""


def login_user(email, password):
    return {'email': email, 'password': password}


def register_user(first_name, last_name, email, role):
    return {'first_name': first_name, 'last_name': last_name, 'email': email, 'role': role}
