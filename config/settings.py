import os


BASE_URL = os.environ.get("AUTOTEST_BASE_URL", "http://localhost:8888")
TEST_USERNAME = os.environ.get("AUTOTEST_USERNAME", "admin")
TEST_PASSWORD = os.environ.get("AUTOTEST_PASSWORD", "123456")
TEST_USER_PASSWORD = os.environ.get("AUTOTEST_USER_PASSWORD", "Auto@12345")

DEFAULT_TIMEOUT = int(os.environ.get("AUTOTEST_TIMEOUT", "5"))
DEFAULT_PAGE_SIZE = 100

TEST_DATA_PREFIX = "autotest_"
