"""Long operations run as jobs that the pages follow until they end: the thresholds of the
last duplicate detection stay with the review, detection reports its progress, and jobs left
running by a stopped worker are marked failed instead of running forever."""
from krinea_api import models
from krinea_api.db import session_factory
from krinea_api.services import dedup, jobs
from tests.conftest import register
from tests.test_dedup_choice import PUBMED, SCOPUS, _import


def test_last_thresholds_stay_with_the_review(client):
    register(client, "jobs-owner@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Thresholds"}).json()["id"]
    settings = client.get(f"/reviews/{rid}").json()["settings"]
    assert (settings["dedup_auto_threshold"], settings["dedup_review_threshold"]) == (95, 85)
    _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    _import(client, rid, "pubmed.ris", PUBMED, "PubMed")

    job = client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 92, "review_threshold": 80}).json()
    assert job["status"] == "done" and job["progress"] == 1.0 and job["result"]["removed"] >= 1
    settings = client.get(f"/reviews/{rid}").json()["settings"]
    assert (settings["dedup_auto_threshold"], settings["dedup_review_threshold"]) == (92, 80)

    # The job can be followed by id, and is listed with the review's jobs.
    assert client.get(f"/jobs/{job['id']}").json()["status"] == "done"
    assert any(j["id"] == job["id"] and j["kind"] == "dedup" for j in client.get(f"/reviews/{rid}/jobs").json())

    # Out of range: refused for a run, brought back within 50-100 when saved as a setting.
    assert client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 10}).status_code == 422
    r = client.patch(f"/reviews/{rid}", json={"settings": {"dedup_auto_threshold": 120, "dedup_review_threshold": "x"}})
    assert (r.json()["settings"]["dedup_auto_threshold"], r.json()["settings"]["dedup_review_threshold"]) == (100, 85)


def test_detection_reports_its_progress(client):
    register(client, "jobs-progress@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Progress"}).json()["id"]
    _import(client, rid, "scopus.ris", SCOPUS, "Scopus")
    _import(client, rid, "pubmed.ris", PUBMED, "PubMed")
    db = session_factory()()
    try:
        for _ in range(2):                       # the second run first undoes the merges of the first
            shares: list[float] = []
            result = dedup.run(db, db.get(models.Review, rid), progress=shares.append)
            assert result["removed"] >= 1
            assert shares[0] <= 0.15 and shares[-1] == 0.95
            assert shares == sorted(shares) and all(0 < s < 1 for s in shares)
        # SQLite takes one writer at a time: there the job reports no intermediate step.
        assert jobs._side_progress(db, models.Job(id="x", kind="dedup")) is None
    finally:
        db.close()


def test_jobs_left_running_by_a_stopped_worker_are_failed(client):
    register(client, "jobs-sweep@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Sweep"}).json()["id"]
    db = session_factory()()
    try:
        stuck = models.Job(kind="dedup", review_id=rid, status="running")
        waiting = models.Job(kind="dedup", review_id=rid, status="queued")
        finished = models.Job(kind="dedup", review_id=rid, status="done", progress=1.0)
        db.add_all([stuck, waiting, finished])
        db.commit()
        assert jobs.fail_interrupted(db) == 1
        for j in (stuck, waiting, finished):
            db.refresh(j)
        assert stuck.status == "failed" and stuck.error == jobs.INTERRUPTED and stuck.finished_at
        assert (waiting.status, finished.status) == ("queued", "done")
        db.delete(waiting)                       # nothing else should pick it up
        db.commit()
    finally:
        db.close()
