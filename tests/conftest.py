import atexit
import os
import tempfile


_test_database_handle, _test_database_path = tempfile.mkstemp(
    prefix='skillbridge-tests-',
    suffix='.db',
)
os.close(_test_database_handle)
os.environ['SKILLBRIDGE_DATABASE_PATH'] = _test_database_path
os.environ['SKILLBRIDGE_ENV'] = 'development'
os.environ['SKILLBRIDGE_DEMO_DATA'] = 'true'
os.environ['SKILLBRIDGE_SECRET_KEY'] = 'test-only-secret-key'


def _remove_test_database():
    from database.db import engine

    engine.dispose()
    if os.path.exists(_test_database_path):
        os.remove(_test_database_path)


atexit.register(_remove_test_database)
