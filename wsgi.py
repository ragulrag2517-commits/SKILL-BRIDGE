import os
import sys


PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(PROJECT_DIR, 'instance')

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.makedirs(INSTANCE_DIR, exist_ok=True)
os.environ.setdefault('SKILLBRIDGE_ENV', 'production')
os.environ.setdefault(
    'SKILLBRIDGE_DATABASE_PATH',
    os.path.join(INSTANCE_DIR, 'skillbridge.db'),
)
os.environ.setdefault(
    'SKILLBRIDGE_UPLOAD_FOLDER',
    os.path.join(INSTANCE_DIR, 'uploads'),
)
os.environ.setdefault('SKILLBRIDGE_DEMO_DATA', 'false')

from app import app as application
