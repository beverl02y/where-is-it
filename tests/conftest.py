import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import load_settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.search import SearchEngine  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    s = load_settings(ROOT / "config.yaml")
    s.db_path = str(tmp_path / "test.db")
    s.model_type = "none"
    s.api_key = "test-key"
    return s


@pytest.fixture
def db(settings):
    return Database(settings.db_path)


@pytest.fixture
def engine(settings, db):
    return SearchEngine(settings, db)


def det(obj, conf, zone="desk", label="on the desk"):
    return {"object": obj, "location": zone, "location_label": label, "confidence": conf,
            "box": (0.1, 0.6, 0.2, 0.7)}
