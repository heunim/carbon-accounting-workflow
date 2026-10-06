from pathlib import Path
import pytest
from carbonflow.catalog import Catalog
from carbonflow.models import Project
from carbonflow.io import load_activities

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def catalog():
    return Catalog.load(ROOT / "data/carbon_data.xlsx")

@pytest.fixture
def project():
    return Project()

@pytest.fixture
def demo():
    return load_activities(ROOT / "examples/demo_activities.xlsx")
