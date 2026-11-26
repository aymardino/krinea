"""The decision log, the PRISMA counts and the records export, for the whole review or for the
searches of the files chosen (D-57): identified are the records the files imported, screened
the unique records that count for them, and the duplicates removed the difference."""
import csv
import io

from tests.conftest import register


def _ris(*studies: tuple[str, str]) -> bytes:
    return "\n".join(f"TY  - JOUR\nTI  - {title}\nPY  - 2020\nDO  - {doi}\nER  -\n" for title, doi in studies).encode()


A = (("Alpha one: solar mini-grids in rural Kenya", "10.1000/a1"), ("Shared study of village electricity tariffs", "10.1000/s"))
B = (("Beta one: diesel generators and household demand", "10.1000/b1"), ("Shared study of village electricity tariffs", "10.1000/s"))


def _review(client, email: str, settings: dict | None = None):
    register(client, email, "Owner")
    rid = client.post("/reviews", json={"title": "Two searches"}).json()["id"]
    for name, db, studies in (("a.ris", "Scopus", A), ("b.ris", "PubMed", B)):
        r = client.post(f"/reviews/{rid}/imports", data={"source_db": db},
                        files={"files": (name, io.BytesIO(_ris(*studies)), "application/x-research-info-systems")})
        assert r.status_code == 201, r.text
    files = {i["filename"]: i["id"] for i in client.get(f"/reviews/{rid}/imports").json()}
    if settings:
        order = [files[name] for name in settings.pop("file_order")]
        client.patch(f"/reviews/{rid}", json={"settings": {**settings, "file_priority": order}})
    assert client.post(f"/reviews/{rid}/dedup/run", json={"auto_threshold": 95, "review_threshold": 85}).status_code == 200
    unique = {r["title"].split(":")[0].split(" of ")[0]: r["id"]
              for r in client.get(f"/reviews/{rid}/records", params={"stage": "ta", "view": "all"}).json()["items"]}
    assert set(unique) == {"Alpha one", "Beta one", "Shared study"}
    return rid, files, unique


def _decide(client, rid, rec, stage, decision, reason=""):
    r = client.post(f"/reviews/{rid}/records/{rec}/decision", json={"stage": stage, "decision": decision, "reason": reason})
    assert r.status_code == 200, r.text


def _csv(client, rid, path, *files):
    r = client.get(f"/reviews/{rid}/export/{path}", params={"import_id": list(files)})
    assert r.status_code == 200, r.text
    return list(csv.DictReader(io.StringIO(r.text)))


def _prisma(client, rid, *files):
    return {row["item"]: int(row["n"]) for row in _csv(client, rid, "prisma.csv", *files)}


def test_the_other_exports_follow_the_files_chosen(client):
    rid, files, rec = _review(client, "other-exports@example.org")
    a, b = files["a.ris"], files["b.ris"]
    _decide(client, rid, rec["Alpha one"], "ta", "exclude", "Wrong population")
    for name in ("Beta one", "Shared study"):
        _decide(client, rid, rec[name], "ta", "include")
    _decide(client, rid, rec["Shared study"], "ft", "include")
    _decide(client, rid, rec["Beta one"], "ft", "exclude", "Wrong outcome")

    whole = _prisma(client, rid)
    assert whole == {**whole, "identified": 4, "duplicates_removed": 1, "screened": 3, "ta_excluded": 1,
                     "sought": 2, "assessed": 2, "ft_excluded": 1, "included": 1}
    # Each record counts once for its own database, though the kept copy lists both.
    assert (whole["by_source:Scopus"], whole["by_source:PubMed"]) == (2, 2)
    assert _prisma(client, rid, a, b) == whole
    # The study both searches found counts for each of them, kept from either file.
    in_a = _prisma(client, rid, a)
    assert in_a == {**in_a, "identified": 2, "by_source:Scopus": 2, "duplicates_removed": 0, "screened": 2,
                    "ta_excluded": 1, "sought": 1, "ft_excluded": 0, "included": 1}
    assert "by_source:PubMed" not in in_a
    in_b = _prisma(client, rid, b)
    assert in_b == {**in_b, "identified": 2, "by_source:PubMed": 2, "duplicates_removed": 0, "screened": 2,
                    "ta_excluded": 0, "sought": 2, "ft_excluded": 1, "ft_excluded_reasons:Wrong outcome": 1, "included": 1}

    # Records: those each file imported, duplicates included, with the file they came from.
    assert len(_csv(client, rid, "records.csv")) == 4
    rows = _csv(client, rid, "records.csv", b)
    assert {r["file"] for r in rows} == {"b.ris"} and len(rows) == 2
    # Decisions: those on the records that count for the file.
    assert len(_csv(client, rid, "decisions.csv")) == 5
    assert {(int(d["record_id"]), d["stage"]) for d in _csv(client, rid, "decisions.csv", a)} == {
        (rec["Alpha one"], "ta"), (rec["Shared study"], "ta"), (rec["Shared study"], "ft")}
    assert len(_csv(client, rid, "decisions.csv", "unknown-file")) == 0


def test_under_the_file_order_a_search_counts_the_studies_it_kept(client):
    """One file per search (D-42): the shared study, kept from b.ris ranked first, is a duplicate
    removed from a.ris."""
    rid, files, rec = _review(client, "other-exports-order@example.org", {"keeper_rule": "file", "file_order": ["b.ris", "a.ris"]})
    _decide(client, rid, rec["Shared study"], "ta", "include")
    in_a, in_b = _prisma(client, rid, files["a.ris"]), _prisma(client, rid, files["b.ris"])
    assert (in_a["identified"], in_a["duplicates_removed"], in_a["screened"], in_a["sought"]) == (2, 1, 1, 0)
    assert (in_b["identified"], in_b["duplicates_removed"], in_b["screened"], in_b["sought"]) == (2, 0, 2, 1)
