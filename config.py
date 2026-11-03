import os
import secrets

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_PATH = os.environ.get(
    'SKILLBRIDGE_DATABASE_PATH',
    os.path.join(BASE_DIR, 'database', 'skillbridge.db'),
)
UPLOAD_FOLDER = os.environ.get(
    'SKILLBRIDGE_UPLOAD_FOLDER',
    os.path.join(BASE_DIR, 'uploads'),
)
APP_ENV = os.environ.get('SKILLBRIDGE_ENV', 'development').strip().lower()
if APP_ENV not in {'development', 'test', 'production'}:
    raise RuntimeError('SKILLBRIDGE_ENV must be development, test, or production.')
SECRET_KEY = (os.environ.get('SKILLBRIDGE_SECRET_KEY') or '').strip()
if APP_ENV == 'production' and not SECRET_KEY:
    raise RuntimeError('SKILLBRIDGE_SECRET_KEY must be configured in production.')
SECRET_KEY = SECRET_KEY or secrets.token_hex(32)
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024
SESSION_COOKIE_SECURE = APP_ENV == 'production'
DEMO_DATA_ENABLED = APP_ENV != 'production' and os.environ.get(
    'SKILLBRIDGE_DEMO_DATA',
    'true',
).strip().lower() == 'true'
