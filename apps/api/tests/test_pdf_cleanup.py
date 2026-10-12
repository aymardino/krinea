"""Deleting records, an import or a review also deletes their stored PDFs."""
import pytest

from krinea_api.config import get_settings
from krinea_api.services import storage
from tests.conftest import register

RIS = "".join(
    f"TY  - JOUR\nAU  - Author {i}\nTI  - Distinct paper number {i} on solar mini-grids\nPY  - 2020\n"
    f"DO  - 10.1000/cleanup.{i}\nER  - \n\n" for i in range(4))


def _pdf_folder(rid: str):
    return get_settings().data_dir / "pdfs" / rid


def _new_review(client, title: str) -> str:
    r = client.post("/reviews", json={"title": title})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _import(client, rid: str) -> tuple[str, list[int]]:
    r = client.post(f"/reviews/{rid}/imports", files={"files": ("cleanup.ris", RIS.encode(), "text/plain")})
    assert r.status_code == 201 and r.json()[0]["n_records"] == 4, r.text
    imp_id = r.json()[0]["id"]
    items = client.get(f"/reviews/{rid}/records", params={"view": "all", "limit": 100}).json()["items"]
    return imp_id, sorted(i["id"] for i in items)


def _upload(client, rid: str, record_id: int, pdf_bytes: bytes) -> None:
    r = client.post(f"/reviews/{rid}/records/{record_id}/pdf",
                    files={"file": (f"paper-{record_id}.pdf", pdf_bytes, "application/pdf")})
    assert r.status_code == 200 and r.json()["has_pdf"], r.text


def _stored(rid: str) -> set[str]:
    folder = _pdf_folder(rid)
    return {p.name for p in folder.iterdir()} if folder.exists() else set()


def test_pdfs_go_with_records_imports_and_reviews(client, pdf_bytes):
    assert not get_settings().s3_bucket                 # local storage backend
    register(client, "cleanup@example.org", "Clea")
    rid = _new_review(client, "PDF cleanup")
    imp_id, ids = _import(client, rid)
    for record_id in ids[:3]:
        _upload(client, rid, record_id, pdf_bytes)
    assert len(_stored(rid)) == 3

    # Deleting records removes their PDFs only
    r = client.post(f"/reviews/{rid}/records/delete", json=[ids[0], ids[3]])
    assert r.json()["deleted"] == 2
    assert {n.split("_", 1)[0] for n in _stored(rid)} == {str(ids[1]), str(ids[2])}

    # Deleting the import removes the PDFs of its remaining records
    assert client.delete(f"/reviews/{rid}/imports/{imp_id}").json()["deleted"] == 2
    assert _stored(rid) == set()

    # Deleting the review removes its whole folder, leaving other reviews' PDFs alone
    other = _new_review(client, "Other review")
    _, other_ids = _import(client, other)
    _upload(client, other, other_ids[0], pdf_bytes)
    _, ids = _import(client, rid)
    _upload(client, rid, ids[0], pdf_bytes)
    assert _pdf_folder(rid).is_dir()
    assert client.delete(f"/reviews/{rid}").status_code == 200
    assert not _pdf_folder(rid).exists()
    assert len(_stored(other)) == 1
    assert client.get(f"/reviews/{other}/records/{other_ids[0]}/pdf").status_code == 200


def test_review_pdf_deletion_refuses_a_bad_review_id():
    for bad in ("", ".", "..", "../x", "a/b"):
        with pytest.raises(ValueError):
            storage.delete_review_pdfs(bad)
    storage.delete_pdfs(["../outside.pdf", ""])          # ignored, never escapes the storage folder


class FakeS3:
    """Enough of a boto3 S3 client for the deletion helpers."""

    def __init__(self, keys, batch_fails=False):
        self.keys, self.batch_fails, self.calls = set(keys), batch_fails, []

    def get_paginator(self, name):
        assert name == "list_objects_v2"
        fake = self

        class Paginator:
            def paginate(self, Bucket, Prefix):
                matching = sorted(k for k in fake.keys if k.startswith(Prefix))
                for i in range(0, max(len(matching), 1), 2):            # small pages
                    yield {"Contents": [{"Key": k} for k in matching[i:i + 2]]} if matching else {}

        return Paginator()

    def delete_objects(self, Bucket, Delete):
        self.calls.append(("delete_objects", len(Delete["Objects"])))
        if self.batch_fails:
            raise RuntimeError("DeleteObjects not supported")
        for o in Delete["Objects"]:
            self.keys.discard(o["Key"])
        return {}

    def delete_object(self, Bucket, Key):
        self.calls.append(("delete_object", Key))
        self.keys.discard(Key)


@pytest.mark.parametrize("batch_fails", [False, True])
def test_s3_deletion(monkeypatch, batch_fails):
    rid, other = "11111111-aaaa-bbbb-cccc-000000000001", "11111111-aaaa-bbbb-cccc-000000000002"
    fake = FakeS3({f"pdfs/{rid}/1_a.pdf", f"pdfs/{rid}/2_b.pdf", f"pdfs/{rid}/3_c.pdf",
                   f"pdfs/{other}/1_a.pdf"}, batch_fails=batch_fails)
    monkeypatch.setattr(get_settings(), "s3_bucket", "bucket")
    monkeypatch.setattr(storage, "_s3", lambda: fake)

    storage.delete_pdfs([f"{rid}/1_a.pdf", ""])
    assert fake.keys == {f"pdfs/{rid}/2_b.pdf", f"pdfs/{rid}/3_c.pdf", f"pdfs/{other}/1_a.pdf"}
    storage.delete_review_pdfs(rid)
    assert fake.keys == {f"pdfs/{other}/1_a.pdf"}
    assert any(c[0] == "delete_object" for c in fake.calls) == batch_fails
