import shutil
from pathlib import Path

_DIST_DIR = Path(__file__).resolve().parent.parent / "dist"
_CREATED_BY_TESTS = not _DIST_DIR.exists()

if _CREATED_BY_TESTS:
    _DIST_DIR.mkdir(parents=True)
    (_DIST_DIR / "index.html").write_text("<html></html>")


def pytest_sessionfinish(session, exitstatus):
    if _CREATED_BY_TESTS:
        shutil.rmtree(_DIST_DIR, ignore_errors=True)
