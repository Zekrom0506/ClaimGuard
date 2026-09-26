"""Shared test setup: a separate test database, a fake Redis and sample PDFs."""

import os

# Must be set before any app module is imported, because the database engine
# is created from settings at import time.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://claimguard:claimguard@localhost:5432/claimguard_test",
)

from collections.abc import Generator  # noqa: E402
from pathlib import Path  # noqa: E402

import fakeredis  # noqa: E402
import pymupdf  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.models  # noqa: E402, F401
from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.rate_limiter import get_redis_client  # noqa: E402
from app.main import app  # noqa: E402
from app.services.pipeline import PipelineDependencies  # noqa: E402
from app.services.policy_ingestion import ingest_policy_pdf  # noqa: E402
from tests.fakes import FakeEmbedder, default_recorded_responses, make_fake_pipeline  # noqa: E402

PROJECT_ROOT = get_settings().project_root
EVALUATION_CASES_DIRECTORY = PROJECT_ROOT / "data" / "evaluation" / "cases"
SAMPLE_POLICY_PDF = PROJECT_ROOT / "data" / "policies" / "sample_lumbar_mri_policy.pdf"


@pytest.fixture(scope="session", autouse=True)
def database_tables() -> Generator[None, None, None]:
    """Create all tables once for the whole test run."""
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def empty_tables() -> None:
    """Start every test with empty tables."""
    table_names = []
    for table in Base.metadata.sorted_tables:
        table_names.append(table.name)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(table_names)} CASCADE"))


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    """An in-memory Redis replacement."""
    return fakeredis.FakeRedis()


@pytest.fixture
def fake_pipeline() -> PipelineDependencies:
    """A pipeline that never calls a real language model."""
    return make_fake_pipeline(default_recorded_responses())


@pytest.fixture
def sample_policy_loaded() -> int:
    """Load the synthetic sample policy into policy_chunks (with the fake embedder)."""
    with SessionLocal() as database_session:
        return ingest_policy_pdf(database_session, SAMPLE_POLICY_PDF, FakeEmbedder())


@pytest.fixture
def client(
    fake_redis: fakeredis.FakeRedis,
    fake_pipeline: PipelineDependencies,
    sample_policy_loaded: int,
) -> Generator[TestClient, None, None]:
    """A test client that uses the fake Redis and the fake pipeline."""
    app.dependency_overrides[get_redis_client] = lambda: fake_redis
    with TestClient(app) as test_client:
        app.state.pipeline = fake_pipeline
        yield test_client
    app.dependency_overrides.clear()


def make_pdf_bytes(text_content: str) -> bytes:
    """Build a small one-page PDF containing the given text."""
    document = pymupdf.open()
    page = document.new_page()
    page.insert_textbox(pymupdf.Rect(50, 50, 550, 800), text_content, fontsize=10)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def evaluation_case_path(case_id: str) -> Path:
    """Path to one of the synthetic evaluation PDFs."""
    return EVALUATION_CASES_DIRECTORY / f"{case_id}.pdf"
