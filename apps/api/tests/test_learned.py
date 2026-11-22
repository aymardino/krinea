"""Suggestions learned from each reviewer's own title/abstract decisions (D-54): they open at
50 inclusions or exclusions with 5 of each, run as a job, score every record for the reviewer
alone, order the list, and suggest the exclusion reason of lookalikes."""
import io

from tests.conftest import register

SOLAR = ["solar mini-grid electrification", "rural village electricity access", "off-grid solar home systems",
         "least-cost electrification planning", "mini-grid tariffs and village demand"]
HOSPITAL = ["hospital surgery outcomes", "elderly patients after cardiac surgery", "nurses and hospital beds",
            "post-operative care of patients", "surgery waiting times"]


def _ris(n_each: int) -> str:
    out = []
    for i in range(n_each):
        for kind, words in (("S", SOLAR), ("H", HOSPITAL)):
            title = f"{words[i % 5].capitalize()}: case {kind}{i} of {words[(i + 2) % 5]}"
            out.append(f"TY  - JOUR\nTI  - {title}\nAB  - We study {words[(i + 1) % 5]} and {words[(i + 3) % 5]}.\nPY  - 2020\nER  -\n")
    return "\n".join(out)


def _review(client) -> tuple[str, list[dict]]:
    register(client, "learn-owner@example.org", "Owner")
    rid = client.post("/reviews", json={"title": "Learned", "criteria": {"exclusion_reasons": ["Wrong population"]}}).json()["id"]
    r = client.post(f"/reviews/{rid}/imports", data={"source_db": "Scopus"},
                    files={"files": ("s.ris", io.BytesIO(_ris(40).encode()), "application/x-research-info-systems")})
    assert r.status_code == 201, r.text
    items = client.get(f"/reviews/{rid}/records?stage=ta&view=all&limit=500").json()["items"]
    assert len(items) == 80
    return rid, items


def _decide(client, rid, rec, decision, reason=""):
    r = client.post(f"/reviews/{rid}/records/{rec['id']}/decision", json={"stage": "ta", "decision": decision, "reason": reason})
    assert r.status_code == 200, r.text


def test_suggestions_open_at_enough_decisions_and_order_the_list(client, client2):
    rid, items = _review(client)
    solar = [r for r in items if ": case S" in r["title"]]
    hospital = [r for r in items if ": case H" in r["title"]]
    st = client.get(f"/reviews/{rid}/learned").json()
    assert st["ready"] is False and st["n_include"] == 0 and st["min_decisions"] == 50 and st["run"] is None

    for rec in solar[:4]:
        _decide(client, rid, rec, "include")
    for rec in hospital[:30]:
        _decide(client, rid, rec, "exclude", "Wrong population")
    for rec in solar[30:35]:
        _decide(client, rid, rec, "maybe")                 # a "maybe" teaches nothing
    st = client.get(f"/reviews/{rid}/learned").json()
    assert (st["n_include"], st["n_exclude"], st["ready"]) == (4, 30, False)
    r = client.post(f"/reviews/{rid}/learned")
    assert r.status_code == 400 and "you have 4 and 30" in r.json()["detail"]

    for rec in solar[4:20]:
        _decide(client, rid, rec, "include")
    assert client.get(f"/reviews/{rid}/learned").json()["ready"] is True
    job = client.post(f"/reviews/{rid}/learned").json()
    assert job["kind"] == "learn" and job["status"] == "done", job
    assert job["result"]["n_include"] == 20 and job["result"]["scored"] == 80

    st = client.get(f"/reviews/{rid}/learned").json()
    assert st["run"]["n_include"] == 20 and st["run"]["auc"] > 0.9 and st["new_since"] == 0
    assert any("solar" in t or "electrification" in t or "village" in t for t in st["run"]["include_terms"])

    # Undecided records carry the reviewer's suggestion; a likely exclusion carries its reason.
    todo = {r["id"]: r for r in client.get(f"/reviews/{rid}/records?stage=ta&view=todo&limit=500").json()["items"]}
    assert todo[solar[25]["id"]]["learned"]["decision"] == "include"
    assert todo[hospital[35]["id"]]["learned"]["decision"] == "exclude"
    assert todo[hospital[35]["id"]]["learned"]["reason"] == "Wrong population"
    assert todo[solar[25]["id"]]["learned"]["reason"] == ""

    # The list in the order of the suggestions: likely inclusions first, or exclusions first.
    order = [r["id"] for r in client.get(f"/reviews/{rid}/records?stage=ta&view=todo&limit=500&sort=learned").json()["items"]]
    undecided_solar = {r["id"] for r in solar[20:30] + solar[35:]}
    assert set(order[:len(undecided_solar)]) == undecided_solar
    back = [r["id"] for r in client.get(f"/reviews/{rid}/records?stage=ta&view=todo&limit=500&sort=learned_exclude").json()["items"]]
    assert set(back[-len(undecided_solar):]) == undecided_solar

    # A decision made since the run counts as new; the suggestions stay as they were until the next.
    _decide(client, rid, solar[25], "include")
    assert client.get(f"/reviews/{rid}/learned").json()["new_since"] == 1
    one = client.get(f"/reviews/{rid}/records/{solar[25]['id']}?stage=ta").json()
    assert one["learned"]["decision"] == "include"
    # Full-text screening shows none.
    assert client.get(f"/reviews/{rid}/records/{solar[25]['id']}?stage=ft").json()["learned"] is None

    # The suggestions are personal: a teammate sees none until they have their own.
    register(client2, "learn-mate@example.org", "Mate")
    r = client.post(f"/reviews/{rid}/invitations", json={"email": "learn-mate@example.org", "role": "reviewer"})
    assert r.status_code == 201, r.text
    token = r.json()["accept_url"].rsplit("/", 1)[1]
    assert client2.post("/reviews/invitations/accept", json={"token": token}).status_code == 200
    mate = client2.get(f"/reviews/{rid}/records?stage=ta&view=all&limit=500").json()["items"]
    assert len(mate) == 80 and all(r["learned"] is None for r in mate)
    st = client2.get(f"/reviews/{rid}/learned").json()
    assert st["run"] is None and st["n_include"] == 0
