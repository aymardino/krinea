"""Screening suggestions learned from a reviewer's own decisions, with no AI service (D-54).

A classic text classifier, as some screening tools offer. Each record becomes a TF-IDF
vector of the words of its title, keywords and abstract (single words and pairs of
consecutive words), hashed into a fixed number of columns so that no vocabulary is kept in
memory (as scikit-learn's HashingVectorizer): a review of 20,000 records fits in the 512 MB
of a small server (D-56). A logistic regression with L2 regularisation, both classes weighted
alike, learns from the records the reviewer included or excluded which words go with each.
It then scores every record between 0 and 1: how likely the reviewer is to include it.
Everything runs here in numpy; no text leaves the server.

The more decisions it learns from, the better it ranks. `learn` measures how well it does
on the reviewer's own decisions, by cross-validation (the AUC: the chance that a record the
reviewer included scores above one they excluded), and suggests an exclusion reason by
likeness to the records excluded for each reason.
"""
from __future__ import annotations

import re
import unicodedata
import zlib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

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
# Terms are hashed into N_BUCKETS columns; a column found in fewer than MIN_DF records is dropped.
N_BUCKETS = 1 << 20
MIN_DF = 2

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


# Rows taken at a time in a product, and records read at a time to build the features: the
# temporary arrays stay small whatever the size of the review (D-56).
CHUNK = 4096


@dataclass
class Matrix:
    """A sparse matrix of records (rows) by terms (columns), in compressed rows: 32-bit column
    numbers and values."""
    indptr: np.ndarray
    indices: np.ndarray
    data: np.ndarray
    n_features: int

    @property
    def n(self) -> int:
        return len(self.indptr) - 1

    @property
    def rowid(self) -> np.ndarray:
        """The row of each stored value."""
        return np.repeat(np.arange(self.n, dtype=np.int32), np.diff(self.indptr))

    def _spans(self):
        for a in range(0, self.n, CHUNK):
            b = min(self.n, a + CHUNK)
            lo, hi = int(self.indptr[a]), int(self.indptr[b])
            yield a, b, lo, hi, np.repeat(np.arange(b - a, dtype=np.int32), np.diff(self.indptr[a:b + 1]))

    def dot(self, w: np.ndarray) -> np.ndarray:
        out = np.zeros(self.n)
        for a, b, lo, hi, rows in self._spans():
            out[a:b] = np.bincount(rows, weights=self.data[lo:hi] * w[self.indices[lo:hi]], minlength=b - a)
        return out

    def tdot(self, r: np.ndarray) -> np.ndarray:
        out = np.zeros(self.n_features)
        for a, b, lo, hi, rows in self._spans():
            out += np.bincount(self.indices[lo:hi], weights=self.data[lo:hi] * r[a:b][rows], minlength=self.n_features)
        return out

    def rows(self, idx) -> "Matrix":
        idx = np.asarray(idx, dtype=np.int64)
        lengths = np.diff(self.indptr)[idx]
        starts = self.indptr[idx]
        take = (np.repeat(starts - np.concatenate(([0], np.cumsum(lengths)[:-1])), lengths)
                + np.arange(lengths.sum(), dtype=np.int64))
        indptr = np.concatenate(([0], np.cumsum(lengths))).astype(np.int64)
        return Matrix(indptr, self.indices[take], self.data[take], self.n_features)


def _bucket(term: str) -> int:
    return zlib.crc32(term.encode("utf-8")) & (N_BUCKETS - 1)


def features(texts: Iterable[str], min_df: int = MIN_DF) -> tuple[Matrix, np.ndarray]:
    """TF-IDF rows of unit length (sublinear term counts, smoothed IDF) over hashed terms, the
    columns found in fewer than `min_df` records left out; and the bucket of each column, for
    `term_names`. The records are read once, CHUNK at a time, each block kept as two flat arrays
    (bucket, count) until the document frequencies are known."""
    blocks: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    df = np.zeros(N_BUCKETS, dtype=np.int64)
    lengths: list[int] = []
    buckets: list[np.ndarray] = []
    counts: list[np.ndarray] = []

    def close() -> None:
        if lengths:
            b = np.concatenate(buckets)
            blocks.append((np.array(lengths, dtype=np.int32), b, np.concatenate(counts)))
            df[:] += np.bincount(b, minlength=N_BUCKETS)
            lengths.clear(), buckets.clear(), counts.clear()

    for text in texts:
        toks = tokens(text)
        b, k = np.unique(np.fromiter((_bucket(t) for t in toks), dtype=np.int32, count=len(toks)), return_counts=True)
        lengths.append(len(b))
        buckets.append(b)
        counts.append(np.minimum(k, 65535).astype(np.uint16))
        if len(lengths) == CHUNK:
            close()
    close()
    n = sum(len(block[0]) for block in blocks)
    kept = df >= min_df
    columns = np.flatnonzero(kept)
    column = (np.cumsum(kept) - 1).astype(np.int32)
    idf = (np.log((1 + n) / (1 + df[columns].astype(float))) + 1).astype(np.float32)
    out_indices, out_data, out_lengths = [], [], []
    while blocks:                          # each block let go once turned into rows
        lens, b, k = blocks.pop(0)
        keep = kept[b]
        rows = np.repeat(np.arange(len(lens), dtype=np.int32), lens)[keep]
        cols = column[b[keep]]
        vals = (1 + np.log(k[keep].astype(np.float32))) * idf[cols]
        norms = np.sqrt(np.bincount(rows, weights=vals.astype(float) ** 2, minlength=len(lens)))
        out_data.append((vals / np.where(norms > 0, norms, 1.0)[rows]).astype(np.float32))
        out_indices.append(cols)
        out_lengths.append(np.bincount(rows, minlength=len(lens)))
    indices = np.concatenate(out_indices) if out_indices else np.zeros(0, np.int32)
    data = np.concatenate(out_data) if out_data else np.zeros(0, np.float32)
    indptr = np.concatenate([[0], np.cumsum(np.concatenate(out_lengths))] if out_lengths else [[0]]).astype(np.int64)
    return Matrix(indptr, indices, data, len(columns)), columns


def term_names(texts: Iterable[str], wanted: set[int]) -> dict[int, str]:
    """The term of each bucket of `wanted`: the one met most often in `texts` (a bucket seldom
    holds two)."""
    seen: dict[int, Counter] = defaultdict(Counter)
    for text in texts:
        for t in tokens(text):
            b = _bucket(t)
            if b in wanted:
                seen[b][t] += 1
    return {b: c.most_common(1)[0][0] for b, c in seen.items()}


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
    x, buckets = features(texts)
    idx = np.array(sorted(labels), dtype=np.int64)
    y = np.array([1.0 if labels[i] else 0.0 for i in idx])
    if not x.n_features or not len(idx) or y.min() == y.max():
        return Learned([0.5] * n, [""] * n, None, 0.5, 0.5, [], [])
    train = x.rows(idx)
    w, b = fit(train, y)
    scores = _sigmoid(x.dot(w) + b)
    order = np.argsort(-w, kind="stable")
    top_in = [int(i) for i in order[:N_TERMS] if w[i] > 0]
    top_out = [int(i) for i in order[::-1][:N_TERMS] if w[i] < 0]
    names = term_names(texts, {int(buckets[i]) for i in top_in + top_out})
    include_terms = [names[int(buckets[i])] for i in top_in if int(buckets[i]) in names]
    exclude_terms = [names[int(buckets[i])] for i in top_out if int(buckets[i]) in names]
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
