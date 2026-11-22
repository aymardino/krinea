"""Screening suggestions learned from a reviewer's own decisions, with no AI service (D-54).

A classic text classifier, as some screening tools offer. Each record becomes a TF-IDF
vector of the words of its title, keywords and abstract (single words and pairs of
consecutive words). A logistic regression with L2 regularisation, both classes weighted
alike, learns from the records the reviewer included or excluded which words go with each.
It then scores every record between 0 and 1: how likely the reviewer is to include it.
Everything runs here in numpy; no text leaves the server.

The more decisions it learns from, the better it ranks. `learn` measures how well it does
on the reviewer's own decisions, by cross-validation (the AUC: the chance that a record the
reviewer included scores above one they excluded), and suggests an exclusion reason by
likeness to the records excluded for each reason.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

# Suggestions open once the reviewer has made MIN_DECISIONS inclusions or exclusions ("maybe"
# teaches nothing), with at least MIN_EACH of each: a model learns from examples of both kinds,
# whatever the size of the review.
MIN_DECISIONS = 50
MIN_EACH = 5
# A reason is suggested once at least MIN_REASON records were excluded for it.
MIN_REASON = 3
# A record is suggested for exclusion when it scores below what RECALL of the reviewer's own
# inclusions scored in cross-validation (so such a suggestion would have missed about 1 in 20
# of them), and for inclusion when it scores above what RECALL of their exclusions scored;
# "maybe" in between.
RECALL = 0.95
# The words most linked to each decision, shown to explain the ranking.
N_TERMS = 10
# The quality is measured by cross-validation in FOLDS groups, on MAX_CV decisions at most.
FOLDS = 5
MAX_CV = 1000

_WORD = re.compile(r"[a-z][a-z0-9]+")
STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being below
between both but by can could did do does doing down during each few for from further had has have having
he her here hers him his how i if in into is it its itself just me more most my no nor not now of off on
once only or other our out over own same she should so some such than that the their them then there these
they this those through to too under until up very was we were what when where which while who whom why will
with would you your
au aux avec ce ces cette dans de des du elle elles en est et il ils la le les leur leurs ne nous on ou par
pas plus pour qui que sa se ses son sont sur un une vous
""".split())


def record_text(title: str, keywords: str, abstract: str) -> str:
    return " ".join(x for x in (title, keywords, abstract) if x)


def tokens(text: str) -> list[str]:
    """Words without accents or case, stop words left out, then the pairs of consecutive words."""
    text = "".join(c for c in unicodedata.normalize("NFKD", (text or "").lower()) if not unicodedata.combining(c))
    words = [w for w in _WORD.findall(text) if w not in STOPWORDS]
    return words + [f"{a} {b}" for a, b in zip(words, words[1:])]


@dataclass
class Matrix:
    """A sparse matrix of records (rows) by terms (columns), in compressed rows."""
    indptr: np.ndarray
    indices: np.ndarray
    data: np.ndarray
    n_features: int
    rowid: np.ndarray = field(init=False)

    def __post_init__(self):
        self.rowid = np.repeat(np.arange(self.n, dtype=np.int64), np.diff(self.indptr))

    @property
    def n(self) -> int:
        return len(self.indptr) - 1

    def dot(self, w: np.ndarray) -> np.ndarray:
        return np.bincount(self.rowid, weights=self.data * w[self.indices], minlength=self.n)

    def tdot(self, r: np.ndarray) -> np.ndarray:
        return np.bincount(self.indices, weights=self.data * r[self.rowid], minlength=self.n_features)

    def rows(self, idx) -> "Matrix":
        idx = np.asarray(idx, dtype=np.int64)
        lengths = np.diff(self.indptr)[idx]
        starts = self.indptr[idx]
        take = (np.repeat(starts - np.concatenate(([0], np.cumsum(lengths)[:-1])), lengths)
                + np.arange(lengths.sum(), dtype=np.int64))
        indptr = np.concatenate(([0], np.cumsum(lengths))).astype(np.int64)
        return Matrix(indptr, self.indices[take], self.data[take], self.n_features)


def features(texts: list[str], min_df: int = 2) -> tuple[Matrix, list[str]]:
    """TF-IDF rows of unit length (sublinear term counts, smoothed IDF), over the terms found in
    at least `min_df` records; and the terms, in column order."""
    docs = [Counter(tokens(t)) for t in texts]
    df = Counter(term for d in docs for term in d)
    terms = sorted(t for t, k in df.items() if k >= min_df)
    col = {t: i for i, t in enumerate(terms)}
    idf = np.log((1 + len(texts)) / (1 + np.array([df[t] for t in terms], dtype=float))) + 1
    indptr, indices, data = [0], [], []
    for d in docs:
        row = sorted((col[t], 1 + math.log(k)) for t, k in d.items() if t in col)
        indices.extend(i for i, _ in row)
        data.extend(v for _, v in row)
        indptr.append(len(indices))
    indices = np.array(indices, dtype=np.int64)
    data = np.array(data, dtype=float) * (idf[indices] if len(indices) else 1.0)
    indptr = np.array(indptr, dtype=np.int64)
    m = Matrix(indptr, indices, data, len(terms))
    norms = np.sqrt(np.bincount(m.rowid, weights=data ** 2, minlength=m.n))
    m.data = data / np.where(norms > 0, norms, 1.0)[m.rowid]
    return m, terms


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 0.5 * (1 + np.tanh(0.5 * z))


def fit(x: Matrix, y: np.ndarray, iters: int | None = None) -> tuple[np.ndarray, float]:
    """Weights and intercept of an L2 logistic regression, the two classes weighted alike (as
    scikit-learn's LogisticRegression(C=1, class_weight="balanced"), which it matches), by
    Nesterov's accelerated gradient. Rows have unit length, so the loss gradient is
    0.5-Lipschitz and the step is fixed. The error shrinks by about 1/sqrt(kappa) a step, kappa
    growing with the number of decisions: 6 sqrt(kappa) steps (100 to 400) bring the scores
    within a few thousandths of the optimum."""
    n = len(y)
    pos = max(1, int(y.sum()))
    sw = np.where(y == 1, 0.5 / pos, 0.5 / max(1, n - pos))
    lam = 1.0 / n
    step = 1.0 / (0.5 + lam)
    kappa = (0.5 + lam) / lam
    beta = (np.sqrt(kappa) - 1) / (np.sqrt(kappa) + 1)
    if iters is None:
        iters = int(min(400, max(100, 6 * np.sqrt(kappa))))
    w = v = np.zeros(x.n_features)
    b = vb = 0.0
    for _ in range(iters):
        r = sw * (_sigmoid(x.dot(v) + vb) - y)
        w_next = v - step * (x.tdot(r) + lam * v)
        b_next = vb - step * r.sum()
        v = w_next + beta * (w_next - w)
        vb = b_next + beta * (b_next - b)
        w, b = w_next, b_next
    return w, b


def auc(scores: np.ndarray, y: np.ndarray) -> float | None:
    """The chance that a positive scores above a negative (ties count half)."""
    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    if not n_pos or not n_neg:
        return None
    _, inv, counts = np.unique(scores, return_inverse=True, return_counts=True)
    ranks = (np.cumsum(counts) - (counts - 1) / 2)[inv]
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def _spread(y: np.ndarray, cap: int) -> np.ndarray:
    """At most `cap` decisions, evenly spread in each class, the smaller class kept whole up to
    half of them."""
    if len(y) <= cap:
        return np.arange(len(y))
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    k_pos = min(len(pos), max(cap // 2, cap - len(neg)))

    def pick(a: np.ndarray, k: int) -> np.ndarray:
        return a[np.linspace(0, len(a) - 1, k).round().astype(np.int64)] if k else a[:0]
    return np.sort(np.concatenate([pick(pos, k_pos), pick(neg, cap - k_pos)]))


def held_out(x: Matrix, y: np.ndarray, folds: int = FOLDS,
             cap: int = MAX_CV) -> tuple[np.ndarray, np.ndarray] | None:
    """The score of each decision by a model that did not learn it, with the decisions scored:
    they are dealt in turn into `folds` groups, includes and excludes apart, so every group has
    both. Beyond `cap` decisions, an even spread of `cap` of them is enough."""
    keep = _spread(y, cap)
    x, y = x.rows(keep), y[keep]
    k = min(folds, int(y.sum()), int(len(y) - y.sum()))
    if k < 2:
        return None
    group = np.empty(len(y), dtype=int)
    for cls in (0, 1):
        where = np.flatnonzero(y == cls)
        group[where] = np.arange(len(where)) % k
    held = np.empty(len(y))
    for g in range(k):
        test = np.flatnonzero(group == g)
        train = np.flatnonzero(group != g)
        w, b = fit(x.rows(train), y[train])
        held[test] = _sigmoid(x.rows(test).dot(w) + b)
    return held, y


def thresholds(held: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """(include_at, exclude_at) from the held-out scores: see RECALL. When the two kinds part
    cleanly, one boundary halfway between them."""
    exclude_at = float(np.quantile(held[y == 1], 1 - RECALL))
    include_at = float(np.quantile(held[y == 0], RECALL))
    if include_at < exclude_at:
        include_at = exclude_at = (include_at + exclude_at) / 2
    return include_at, exclude_at


def suggestion(score: float, include_at: float = 0.5, exclude_at: float = 0.5) -> str:
    return "include" if score > include_at else "exclude" if score < exclude_at else "maybe"


@dataclass
class Learned:
    scores: list[float]                 # one per record, in the order given
    reasons: list[str]                  # the likely exclusion reason, "" when none
    auc: float | None                   # cross-validated, on the reviewer's decisions
    include_at: float                   # suggestion boundaries (see RECALL)
    exclude_at: float
    include_terms: list[str]            # the words most linked to inclusion
    exclude_terms: list[str]            # and to exclusion


def learn(texts: list[str], labels: dict[int, bool], reasons: dict[int, str] | None = None) -> Learned:
    """Scores for every record of `texts`, learned from `labels` (record index: True when the
    reviewer included it, False when excluded). `reasons` gives the reason of excluded records;
    records likely excluded get the reason whose records they resemble most."""
    n = len(texts)
    x, terms = features(texts)
    idx = np.array(sorted(labels), dtype=np.int64)
    y = np.array([1.0 if labels[i] else 0.0 for i in idx])
    if not x.n_features or not len(idx) or y.min() == y.max():
        return Learned([0.5] * n, [""] * n, None, 0.5, 0.5, [], [])
    train = x.rows(idx)
    w, b = fit(train, y)
    scores = _sigmoid(x.dot(w) + b)
    order = np.argsort(-w, kind="stable")
    include_terms = [terms[i] for i in order[:N_TERMS] if w[i] > 0]
    exclude_terms = [terms[i] for i in order[::-1][:N_TERMS] if w[i] < 0]
    cv = held_out(train, y)
    quality = auc(*cv) if cv else None
    include_at, exclude_at = thresholds(*cv) if cv else (0.5, 0.5)

    out_reasons = [""] * n
    by_reason: dict[str, list[int]] = {}
    for i, r in (reasons or {}).items():
        if r and i in labels and not labels[i]:
            by_reason.setdefault(r, []).append(i)
    kept = sorted(r for r, rows in by_reason.items() if len(rows) >= MIN_REASON)
    if kept:
        # The centre of each reason's records, then each record's likeness to every centre.
        sims = []
        for r in kept:
            centre = x.rows(by_reason[r]).tdot(np.ones(len(by_reason[r])))
            norm = np.linalg.norm(centre)
            sims.append(x.dot(centre / norm) if norm else np.zeros(n))
        best = np.argmax(np.vstack(sims), axis=0)
        for i in range(n):
            if suggestion(scores[i], include_at, exclude_at) == "exclude":
                out_reasons[i] = kept[best[i]]
    return Learned([float(s) for s in scores], out_reasons, quality, include_at, exclude_at, include_terms, exclude_terms)
