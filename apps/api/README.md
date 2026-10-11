# Krinea API

FastAPI + SQLAlchemy. PostgreSQL in production, SQLite by default locally.

```bash
pip install -e packages/core -e "apps/api[dev]"
cd apps/api
uvicorn krinea_api.main:app --reload          # http://localhost:8000/docs
python -m krinea_api.worker                   # only needed when INLINE_JOBS=0 (production)
pytest -q
```

Environment: see `.env.example` at the repository root (`DATABASE_URL`, `SECRET_KEY`,
`BASE_URL`, `CORS_ORIGINS`, `DATA_DIR` or `S3_BUCKET`, `EMAIL_PROVIDER`, provider keys for
included AI credits, `INLINE_JOBS`).

Authentication is a session cookie (`krinea_session`, HttpOnly) or `Authorization: Bearer`.
All review endpoints check membership and role (viewer < reviewer < admin < owner).
