"""Suggestions learned from a reviewer's decisions (krinea_core.learn): the text features, the
classifier, its quality estimate and the suggested exclusion reason."""
import numpy as np
import pytest

from krinea_core import learn

ON = ["Solar mini-grid electrification of rural villages", "Off-grid solar home systems and village electricity",
      "Rural electrification planning with solar mini-grids", "Mini-grid tariffs for rural electricity access",
      "Village solar power and household electricity demand", "Least-cost rural electrification with mini-grids"]
OFF = ["Hospital surgery outcomes in elderly patients", "Patients after cardiac surgery in the hospital",
       "Surgery waiting times and hospital beds", "Elderly patients and post-operative care",
       "Hospital nurses and surgery scheduling", "Cardiac patients readmitted to hospital"]
FISH = ["Fish stocks and coastal fisheries", "Coastal fisheries management and fish prices",
        "Fish farming along the coast", "Fisheries quotas and fish populations"]


def test_words_lose_accents_case_and_stop_words_and_come_with_their_pairs():
    assert learn.tokens("The Électricité of rural villages") == ["electricite", "rural", "villages",
                                                                 "electricite rural", "rural villages"]
    assert learn.tokens("") == []


def test_rows_have_unit_length_and_rare_terms_are_left_out():
    texts = ["solar village", "solar grid", "hospital"]
    x, buckets = learn.features(texts)
    # Terms are hashed into columns: the only one kept is the term found in two records.
    assert x.n_features == 1 and learn.term_names(texts, set(buckets.tolist())) == {int(buckets[0]): "solar"}
    norms = np.sqrt(np.bincount(x.rowid, weights=x.data ** 2, minlength=x.n))
    assert np.allclose(norms, [1, 1, 0])
    sub = x.rows([2, 0])
    assert sub.n == 2 and list(np.diff(sub.indptr)) == [0, 1]


def test_auc_counts_ties_half():
    assert learn.auc(np.array([0.9, 0.8, 0.1]), np.array([1.0, 0.0, 0.0])) == 1.0
    assert learn.auc(np.array([0.5, 0.5]), np.array([1.0, 0.0])) == 0.5
    assert learn.auc(np.array([0.5, 0.4]), np.array([1.0, 1.0])) is None


def test_the_reviewer_s_inclusions_rank_first_with_the_reason_of_lookalikes():
    texts = ON + OFF + FISH + ["Solar mini-grids for villages in Kenya", "Surgery in a rural hospital",
                               "Fish markets on the coast"]
    labels = {i: True for i in range(5)} | {i: False for i in range(6, 11)} | {i: False for i in range(12, 15)}
    reasons = {i: "Wrong population" for i in range(6, 11)} | {i: "Off topic" for i in range(12, 15)}
    res = learn.learn(texts, labels, reasons)
    new_solar, new_surgery, new_fish = res.scores[-3:]
    assert new_solar > 0.5 > new_surgery and new_solar > new_fish
    assert res.include_at >= res.exclude_at
    bounds = (res.include_at, res.exclude_at)
    assert learn.suggestion(new_solar, *bounds) == "include"
    assert learn.suggestion(new_surgery, *bounds) == learn.suggestion(new_fish, *bounds) == "exclude"
    assert res.reasons[-2] == "Wrong population" and res.reasons[-1] == "Off topic"
    assert res.reasons[-3] == ""                       # a likely inclusion gets no reason
    assert res.auc is not None and res.auc > 0.8
    assert "solar" in res.include_terms and "hospital" in res.exclude_terms
    # Records the reviewer decided keep their place: the inclusions above the exclusions.
    assert min(res.scores[i] for i in range(5)) > max(res.scores[i] for i in range(6, 11))


def test_suggestions_part_at_the_boundaries_learned_from_the_reviewer_s_own_decisions():
    held = np.array([0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.2, 0.75])
    y = np.array([1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    include_at, exclude_at = learn.thresholds(held, y)
    # Exclusions are suggested below nearly all inclusions, inclusions above nearly all exclusions.
    assert exclude_at < 0.62 and include_at > 0.6
    assert learn.suggestion(0.65, include_at, exclude_at) == "maybe"
    assert learn.suggestion(0.95, include_at, exclude_at) == "include"
    assert learn.suggestion(0.1, include_at, exclude_at) == "exclude"
    # Two kinds that part cleanly get one boundary halfway.
    assert learn.thresholds(np.array([0.9, 0.8, 0.2, 0.1]), np.array([1.0, 1.0, 0.0, 0.0])) == pytest.approx((0.5, 0.5))


def test_nothing_to_learn_from_one_kind_of_decision():
    res = learn.learn(ON, {0: True, 1: True})
    assert res.scores == [0.5] * len(ON) and res.auc is None and res.reasons == [""] * len(ON)


def test_the_estimate_reads_an_even_spread_of_a_large_set():
    y = np.array([1.0] * 30 + [0.0] * 2000)
    keep = learn._spread(y, 1000)
    assert len(keep) == 1000 and y[keep].sum() == 30 and len(set(keep)) == 1000
    y = np.array([1.0] * 900 + [0.0] * 900)
    keep = learn._spread(y, 1000)
    assert y[keep].sum() == 500 and len(set(keep)) == 1000
