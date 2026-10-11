import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="krinea-test-"))
os.environ.update({
    "KRINEA_ENV": "test", "SECRET_KEY": "test-secret", "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
    "DATA_DIR": str(_TMP / "data"), "BASE_URL": "http://web.test", "INLINE_JOBS": "1",
    "EMAIL_PROVIDER": "console", "ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "", "DEEPSEEK_API_KEY": "",
    "PRO_AI_TOKENS_PER_MONTH": "1000",
})

from fastapi.testclient import TestClient  # noqa: E402

from krinea_api import db as dbmod  # noqa: E402
from krinea_api.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    dbmod.create_all()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client2():
    with TestClient(app) as c:
        yield c


def register(client: TestClient, email: str, name: str = "", password: str = "password123") -> dict:
    r = client.post("/auth/register", json={"email": email, "password": password, "name": name})
    if r.status_code == 409:
        r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.fixture
def pdf_bytes() -> bytes:
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    text = ("Techno-economic assessment of solar mini-grids in Kenya. We model 120 villages with HOMER "
            "and compute the levelised cost of electricity. Results show mini-grids are least cost. ") * 12
    page.insert_textbox(fitz.Rect(50, 50, 550, 780), text, fontsize=9)
    return doc.tobytes()
