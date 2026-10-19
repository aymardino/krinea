"""Krinea API application."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from krinea_api import __version__
from krinea_api.config import get_settings
from krinea_api.db import create_all
from krinea_api.routers import admin, ai, auth, exports, records, reviews
from krinea_api.services.ai import AIUnavailable
from krinea_api.services.email import EmailError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("krinea")


def create_app() -> FastAPI:
    s = get_settings()               # refuses a weak SECRET_KEY in production (config.check_secret_key)
    if s.env == "production" and not s.base_url_explicit:
        log.warning("BASE_URL is not set: links in e-mails and the Google redirect fall back to the origin "
                    "reported by the web proxy. Set BASE_URL to the public https address in production.")
    app = FastAPI(title="Krinea API", version=__version__, docs_url="/docs" if s.debug else None,
                  redoc_url=None, openapi_url="/openapi.json" if s.debug else None)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    for r in (auth.router, reviews.router, records.router, ai.router, exports.router, admin.router):
        app.include_router(r)

    @app.exception_handler(AIUnavailable)
    async def _ai_unavailable(_: Request, exc: AIUnavailable):
        return JSONResponse({"detail": str(exc)}, status_code=402)

    @app.exception_handler(EmailError)
    async def _email_error(_: Request, exc: EmailError):
        return JSONResponse({"detail": str(exc)}, status_code=502)

    @app.get("/health")
    def health():
        return {"ok": True, "version": __version__}

    @app.on_event("startup")
    def _startup():
        create_all()          # idempotent; Alembic migrations take over once the schema stabilises

    return app


app = create_app()
