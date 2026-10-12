"""`python -m krinea_api.worker` — runs queued jobs (dedup, AI batches, extraction) and,
hourly, purges sign-in tokens older than a day and expired sessions."""
from krinea_api.db import create_all
from krinea_api.services.jobs import worker_loop

if __name__ == "__main__":
    create_all()
    worker_loop()
