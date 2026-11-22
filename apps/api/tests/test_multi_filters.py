"""Views, files and labels picked several at once: a record shows when it matches any of the
views, any of the files and any of the labels, in the record lists and in the AI runs that
follow them (D-40)."""
import io

from tests.conftest import register


def _ris(*titles: str) -> bytes:
    return "\n".join(f"TY  - JOUR\nTI  - {t}\nPY  - 2020\nER  -\n" for t in titles).encode()


def _review(client):
    register(client, "multi-owner@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Several at once"}).json()["id"]
    for name, titles in (("a.ris", ("Alpha one", "Alpha two", "Alpha three")), ("b.ris", ("Beta one", "Beta two"))):
        r = client.post(f"/reviews/{rid}/imports", data={"source_db": name[0].upper()},
                        files={"files": (name, io.BytesIO(_ris(*titles)), "application/x-research-info-systems")})
        assert r.status_code == 201, r.text
    files = {i["filename"]: i["id"] for i in client.get(f"/reviews/{rid}/imports").json()}
    recs = {r["title"]: r["id"] for r in client.get(f"/reviews/{rid}/records?stage=ta&view=all").json()["items"]}
    return rid, files, recs


def _titles(client, rid, query):
    r = client.get(f"/reviews/{rid}/records?stage=ta&{query}")
    assert r.status_code == 200, r.text
    return {x["title"] for x in r.json()["items"]}


def test_views_files_and_labels_add_up(client):
    rid, files, recs = _review(client)
    for title, labels in (("Alpha one", "SQ1"), ("Alpha two", "SQ2; costs"), ("Beta one", "SQ10"), ("Beta two", "SQ1")):
        assert client.patch(f"/reviews/{rid}/records/{recs[title]}", json={"labels": labels}).status_code == 200
    for title, decision in (("Alpha one", "include"), ("Alpha two", "maybe"), ("Beta one", "exclude")):
        r = client.post(f"/reviews/{rid}/records/{recs[title]}/decision", json={"stage": "ta", "decision": decision})
        assert r.status_code == 200, r.text

    # Views: any of them.
    assert _titles(client, rid, "view=mine_include&view=mine_maybe") == {"Alpha one", "Alpha two"}
    assert _titles(client, rid, "view=todo&view=mine_exclude") == {"Alpha three", "Beta one", "Beta two"}
    assert _titles(client, rid, "view=todo") == {"Alpha three", "Beta two"}
    assert _titles(client, rid, "view=todo&view=all") == set(recs)
    assert client.get(f"/reviews/{rid}/records?stage=ta&view=todo&view=nonsense").status_code == 400

    # Files: any of them; labels: any of them, each whole ("SQ1" is not "SQ10").
    a, b = files["a.ris"], files["b.ris"]
    assert _titles(client, rid, f"view=all&import_id={a}") == {"Alpha one", "Alpha two", "Alpha three"}
    assert _titles(client, rid, f"view=all&import_id={a}&import_id={b}") == set(recs)
    assert _titles(client, rid, "view=all&label=SQ1") == {"Alpha one", "Beta two"}
    assert _titles(client, rid, "view=all&label=SQ1&label=costs") == {"Alpha one", "Alpha two", "Beta two"}
    assert _titles(client, rid, "view=all&label=sq10&label=") == {"Beta one"}

    # Different filters narrow each other down.
    assert _titles(client, rid, f"view=todo&view=mine_include&import_id={b}") == {"Beta two"}
    assert _titles(client, rid, f"view=mine_include&view=mine_maybe&label=SQ2&import_id={a}") == {"Alpha two"}

    # An AI run follows the same list: records without a decision of yours, in the views picked.
    preview = lambda queue: client.post(f"/reviews/{rid}/ai/screen/preview", json={"stage": "ta", "queue": queue}).json()  # noqa: E731
    assert preview({"view": ["todo", "mine_maybe"], "import_id": [a]})["available"] == 1         # Alpha three
    assert preview({"view": ["todo"], "import_id": [a, b], "label": ["SQ1"]})["available"] == 1  # Beta two
    # A page from before still sends one view, label and file as plain strings.
    assert preview({"view": "todo", "label": "", "import_id": ""})["available"] == 2
