"""`python -m tamis_api.worker` — runs queued jobs (dedup, AI batches, extraction)."""
from tamis_api.db import create_all
from tamis_api.services.jobs import worker_loop

if __name__ == "__main__":
    create_all()
    worker_loop()
