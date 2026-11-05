import os

# This file is used to set up the test environment for pytest.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")