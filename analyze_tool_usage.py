"""
Usage analytics for the extraction workbench.

Reads extractions.db (same folder by default) and writes report-ready PNG
charts (300 dpi, Office-style palette, English labels) into ./charts/,
plus a summary_stats.txt with figures to quote in the report.

Run from VS Code or a terminal:
    python analyze_tool_usage.py            # uses ./extractions.db
    python analyze_tool_usage.py path/to/extractions.db
"""

import json
import sqlite3
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

# ── Office-style look ─────────────────────────────────────────────────────────
BLUE, ORANGE, GREY = "#4472C4", "#ED7D31", "#A5A5A5"
GOLD, BLUE2, GREEN = "#FFC000", "#5B9BD5", "#70AD47"
PALETTE = [BLUE, ORANGE, GREY, GOLD, BLUE2, GREEN]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Calibri", "Arial", "Helvetica", "DejaVu Sans"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.grid.axis": "y",
    "grid.color": "#E3E3E3",
    "grid.linewidth": 0.7,
    "axes.axisbelow": True,
    "figure.facecolor": "white",
})

DB = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "extractions.db"
OUT = Path(__file__).parent / "charts"
OUT.mkdir(exist_ok=True)
SUMMARY = []


def save(fig, name):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote charts/{name}")


def note(line):
    SUMMARY.append(line)
    print("  " + line)


# ── Load ─────────────────────────────────────────────────────────────────────
if not DB.exists():
    sys.exit(f"Database not found: {DB}")

con = sqlite3.connect(DB)
cols = [r[1] for r in con.execute("PRAGMA table_info(extractions)").fetchall()]
df = pd.read_sql("SELECT * FROM extractions", con)
con.close()

df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
df["verified_at"] = pd.to_datetime(df.get("verified_at"), errors="coerce")

ver = df[df["status"] == "verified"].copy()
ver = ver.sort_values("verified_at").reset_index(drop=True)
ver["order"] = range(1, len(ver) + 1)
ver["minutes"] = pd.to_numeric(ver["review_seconds"], errors="coerce") / 60.0
timed = ver.dropna(subset=["minutes"])
timed = timed[timed["minutes"] > 0]

# Sessions far above the median are almost always a timer left running while
# doing something else, not real verification effort. They are excluded from
# the time statistics and the time charts (raise the cap if needed).
MAX_PLAUSIBLE_MIN = 20
left_running = timed[timed["minutes"] > MAX_PLAUSIBLE_MIN]
timed = timed[timed["minutes"] <= MAX_PLAUSIBLE_MIN]

drafts = int((df["status"] == "draft").sum())
failed = int((df["status"] == "failed").sum())

print(f"Loaded {len(df)} rows: {len(ver)} verified, {drafts} drafts, {failed} failed\n")
note(f"Corpus in tool: {len(df)} records ({len(ver)} verified, {drafts} drafts, {failed} failed)")

# Parse data_json once
def parse(js):
    try:
        return json.loads(js or "{}")
    except Exception:
        return {}

ver["data"] = ver["data_json"].apply(parse)


# ── 1. Review time distribution ──────────────────────────────────────────────
if len(timed) >= 5:
    med = timed["minutes"].median()
    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    ax.hist(timed["minutes"], bins=30, color=BLUE, edgecolor="white", linewidth=0.6)
    ax.axvline(med, color=ORANGE, linewidth=1.6)
    ax.text(med, ax.get_ylim()[1] * 0.95, f"  median {med:.1f} min",
            color=ORANGE, va="top", fontsize=9)
    ax.set_xlabel("Verification time per study (minutes)")
    ax.set_ylabel("Number of studies")
    ax.set_title("Distribution of human verification time")
    save(fig, "01_review_time_distribution.png")
    note(f"Verification time: median {med:.1f} min, mean {timed['minutes'].mean():.1f} min "
         f"over {len(timed)} timed studies")
    if len(left_running):
        note(f"{len(left_running)} session(s) excluded as timer left running "
             f"(> {MAX_PLAUSIBLE_MIN} min)")
    note(f"Total human verification effort so far: {timed['minutes'].sum()/60:.1f} hours "
         f"(excluded sessions not counted)")
    if drafts:
        note(f"Projected effort for the {drafts} remaining drafts at the median pace: "
             f"{drafts*med/60:.1f} hours")

# ── 2. Learning curve ────────────────────────────────────────────────────────
if len(timed) >= 15:
    roll = timed["minutes"].rolling(15, min_periods=5).median()
    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    ax.scatter(timed["order"], timed["minutes"], s=10, color=BLUE, alpha=0.35,
               label="Individual study")
    ax.plot(timed["order"], roll, color=ORANGE, linewidth=1.8,
            label="Rolling median (15 studies)")
    ax.set_xlabel("Study number (verification order)")
    ax.set_ylabel("Minutes")
    ax.set_title("Learning curve of the verification workflow")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, frameon=False)
    save(fig, "02_learning_curve.png")

# ── 3. Daily throughput ──────────────────────────────────────────────────────
if ver["verified_at"].notna().sum() >= 2:
    daily = ver.dropna(subset=["verified_at"]).groupby(ver["verified_at"].dt.date).size()
    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    ax.bar([d.strftime("%b %d") for d in daily.index], daily.values, color=BLUE, width=0.65)
    ax.set_ylabel("Studies verified")
    ax.set_title("Daily verification throughput")
    ax.tick_params(axis="x", rotation=45)
    for lbl in ax.get_xticklabels():
        lbl.set_ha("right")
    save(fig, "03_daily_throughput.png")
    note(f"Best day: {daily.max()} studies verified; active days: {len(daily)}")

# ── 4. Cumulative progress ───────────────────────────────────────────────────
if ver["verified_at"].notna().sum() >= 2:
    cum = ver.dropna(subset=["verified_at"]).sort_values("verified_at")
    total_workload = len(ver) + drafts
    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    ax.plot(cum["verified_at"], range(1, len(cum) + 1), color=BLUE, linewidth=1.8,
            label="Verified studies")
    ax.axhline(total_workload, color=GREY, linewidth=1.2, linestyle="--",
               label=f"Current workload ({total_workload})")
    ax.set_ylabel("Studies")
    ax.set_title("Cumulative verification progress")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.legend(loc="center left", frameon=False)
    save(fig, "04_cumulative_progress.png")

# ── 5. Work pattern by hour ──────────────────────────────────────────────────
if ver["verified_at"].notna().sum() >= 10:
    hours = ver["verified_at"].dt.hour.value_counts().reindex(range(24), fill_value=0)
    fig, ax = plt.subplots(figsize=(6.3, 3.2))
    ax.bar(hours.index, hours.values, color=BLUE2, width=0.7)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Studies verified")
    ax.set_title("Verification activity by hour of day")
    save(fig, "05_work_pattern_hours.png")

# ── 6. Extraction level split, and time by level ─────────────────────────────
levels = ver["data"].apply(lambda d: str(d.get("extraction_level", "")).strip().lower())
levels = levels[levels != ""]
if len(levels) >= 5:
    counts = levels.value_counts()
    total = int(counts.sum())
    order = [l for l in ("light", "full") if l in counts.index] + \
            [l for l in counts.index if l not in ("light", "full")]
    label_map = {"light": "Focused (light)", "full": "Whole-system (full)"}
    fig, ax = plt.subplots(figsize=(6.3, 1.6))
    x0 = 0.0
    for lvl, colour in zip(order, [BLUE, ORANGE, GREY]):
        v = int(counts[lvl])
        ax.barh([""], [v], left=x0, color=colour, height=0.55,
                label=label_map.get(lvl, lvl))
        ax.text(x0 + v / 2, 0, f"{v} ({100*v/total:.0f}%)", ha="center", va="center",
                color="white", fontsize=9, fontweight="bold")
        x0 += v
    ax.set_xlim(0, total)
    ax.grid(visible=False)
    ax.set_yticks([]); ax.set_xticks([])
    ax.spines["left"].set_visible(False); ax.spines["bottom"].set_visible(False)
    ax.set_title(f"Studies by extraction level (n = {total})")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=len(order), frameon=False)
    save(fig, "06_extraction_level.png")
    note("Extraction levels: " + ", ".join(f"{k} {v}" for k, v in counts.items()))

    lv = ver.copy()
    lv["level"] = lv["data"].apply(lambda d: str(d.get("extraction_level", "")).strip().lower())
    lv["minutes"] = pd.to_numeric(lv["review_seconds"], errors="coerce") / 60.0
    lv = lv.dropna(subset=["minutes"])
    lv = lv[(lv["minutes"] > 0) & (lv["minutes"] <= MAX_PLAUSIBLE_MIN) & (lv["level"] != "")]
    groups = [g["minutes"].values for _, g in lv.groupby("level")]
    names = [n for n, _ in lv.groupby("level")]
    if len(names) >= 2 and all(len(g) >= 3 for g in groups):
        fig, ax = plt.subplots(figsize=(4.6, 3.2))
        bp = ax.boxplot(groups, patch_artist=True, widths=0.5,
                        medianprops=dict(color=ORANGE, linewidth=1.6))
        ax.set_xticks(range(1, len(names) + 1))
        ax.set_xticklabels(names)
        for patch in bp["boxes"]:
            patch.set_facecolor(BLUE); patch.set_alpha(0.55); patch.set_edgecolor(BLUE)
        ax.set_ylabel("Verification time (minutes)")
        ax.set_title("Verification time by extraction level")
        save(fig, "07_time_by_level.png")

# ── 7. Robustness: tool share convergence as the corpus grows ────────────────
# Generic platforms are not named tools in the thesis methodology (they are
# covered by the ad hoc methodological families), so they are excluded here.
EXCLUDE_PLATFORMS = ("arcgis", "qgis", "matlab", "simulink", "vensim",
                     "excel", "python", "r ")

def tools_of(d):
    raw = str(d.get("tools_used", "") or "")
    out = []
    for tok in raw.replace(",", ";").split(";"):
        t = tok.strip()
        if not t:
            continue
        tl = t.lower()
        if tl == "r" or any(tl.startswith(p) for p in EXCLUDE_PLATFORMS):
            continue
        if tl.startswith("homer"):
            t = "HOMER"
        out.append(t)
    return out

ver["tools"] = ver["data"].apply(tools_of)
with_tools = ver[ver["tools"].map(len) > 0].reset_index(drop=True)
if len(with_tools) >= 20:
    all_tools = pd.Series([t for ts in with_tools["tools"] for t in ts])
    top = all_tools.value_counts().head(5).index.tolist()
    n = len(with_tools)
    shares = {t: [] for t in top}
    seen = {t: 0 for t in top}
    for i, ts in enumerate(with_tools["tools"], start=1):
        for t in top:
            if t in ts:
                seen[t] += 1
            shares[t].append(100.0 * seen[t] / i)
    fig, ax = plt.subplots(figsize=(6.3, 3.6))
    for t, c in zip(top, PALETTE):
        ax.plot(range(1, n + 1), shares[t], color=c, linewidth=1.7, label=t)
    ax.set_xlabel("Number of verified studies (verification order)")
    ax.set_ylabel("Share of studies using the tool (%)")
    ax.set_title("Convergence of tool shares as the verified corpus grows")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=min(5, len(top)),
              frameon=False)
    save(fig, "08_tool_share_convergence.png")
    lead = top[0]
    note(f"Leading tool in this verified subset: {lead} "
         f"({shares[lead][-1]:.1f}% of {n} studies with a tool recorded)")

# ── 8. AI correction rates (only if the app stores ai_json from now on) ──────
if "ai_json" in cols:
    ai = df[(df["status"] == "verified") & df.get("ai_json").notna()].copy()
    ai = ai[ai["ai_json"].astype(str).str.len() > 2]
    if len(ai) >= 10:
        diffs, totals = {}, {}
        for _, row in ai.iterrows():
            a, h = parse(row["ai_json"]), parse(row["data_json"])
            for f in a:
                if f == "extraction_level":
                    continue
                totals[f] = totals.get(f, 0) + 1
                if str(a.get(f, "")).strip() != str(h.get(f, "")).strip():
                    diffs[f] = diffs.get(f, 0) + 1
        rates = pd.Series({f: 100.0 * diffs.get(f, 0) / totals[f]
                           for f in totals if totals[f] >= 10}).sort_values()
        if len(rates):
            show = rates.tail(15)
            fig, ax = plt.subplots(figsize=(6.3, 0.28 * len(show) + 1.4))
            ax.barh(show.index.str.replace("_", " "), show.values, color=BLUE, height=0.6)
            ax.set_xlabel("Fields corrected by the human reviewer (%)")
            ax.set_title(f"AI extraction correction rate by field (n = {len(ai)} studies)")
            ax.grid(axis="x", color="#E3E3E3"); ax.grid(axis="y", visible=False)
            save(fig, "09_ai_correction_rates.png")
            note(f"AI-versus-human comparison available for {len(ai)} studies")
    else:
        print("  ai_json column present but not yet populated; "
              "correction-rate chart will appear as new studies are verified.")
else:
    print("  No ai_json column: correction-rate analysis needs the updated app "
          "(it preserves the raw AI values from now on).")

# ── 9. RAISE audit: quantified responsible-AI-use metrics ────────────────────
# Maps what the database can prove to the RAISE (2026) recommendations for
# evidence synthesists (accountability 1.1, in-context validation 1.2/1.3,
# transparent reporting 1.8/1.9). Output: charts/raise_audit.txt + one chart.
audit = []
audit.append("RAISE self-audit, generated " + str(pd.Timestamp.now().date()))
audit.append("")

# Human oversight (RAISE 1.1, 1.9b): only human-verified records enter the corpus
audit.append(f"Human verification coverage: {len(ver)} of {len(ver)} corpus records "
             f"human-verified before inclusion (100% by design; {drafts} drafts pending)")
if len(timed):
    audit.append(f"Documented verification effort: {timed['minutes'].sum()/60:.1f} h, "
                 f"median {timed['minutes'].median():.1f} min per study (n = {len(timed)})")

# Transparent reporting (RAISE 1.9a): systems, versions and dates of use
mo = df[df["status"] == "verified"].groupby("model").agg(
    n=("id", "count"), first=("created_at", "min"), last=("created_at", "max"))
audit.append("")
audit.append("AI systems used (declare per RAISE 1.9a):")
for m, r in mo.iterrows():
    audit.append(f"  {m}: {int(r['n'])} studies, "
                 f"{str(r['first'])[:10]} to {str(r['last'])[:10]}")

# Traceability: filled fields backed by a verbatim source quote
try:
    q_tot, q_ok, per_field = {}, {}, {}
    for _, row in ver.iterrows():
        vals = row["data"]
        qts = parse(row.get("quotes_json"))
        for f, v in vals.items():
            if f in ("extraction_level", "power_pool") or not str(v).strip():
                continue
            q_tot[f] = q_tot.get(f, 0) + 1
            if str(qts.get(f, "")).strip():
                q_ok[f] = q_ok.get(f, 0) + 1
    if q_tot:
        overall = 100.0 * sum(q_ok.values()) / sum(q_tot.values())
        audit.append("")
        audit.append(f"Source-quote traceability: {overall:.1f}% of filled fields carry "
                     f"a verbatim quote from the paper")
        per_field = pd.Series({f: 100.0 * q_ok.get(f, 0) / n
                               for f, n in q_tot.items() if n >= 10}).sort_values()
        if len(per_field) >= 5:
            show = per_field.head(12)
            fig, ax = plt.subplots(figsize=(6.3, 0.28 * len(show) + 1.4))
            ax.barh(show.index.str.replace("_", " "), show.values, color=BLUE, height=0.6)
            ax.set_xlabel("Fields with a verbatim source quote (%)")
            ax.set_title("Lowest source-quote coverage by field")
            ax.grid(axis="x", color="#E3E3E3"); ax.grid(axis="y", visible=False)
            ax.set_xlim(0, 100)
            save(fig, "10_quote_coverage.png")
except Exception as e:
    print("  quote-coverage audit skipped:", e)

# Residual quality flags on the verified corpus (anomaly checker re-run)
try:
    import anomalies
    n_err = n_warn = 0
    for _, row in ver.iterrows():
        fl = anomalies.check_draft(row["data"], parse(row.get("quotes_json")))
        e_, w_ = anomalies.summarise(fl)
        n_err += e_; n_warn += w_
    audit.append(f"Residual anomaly-checker flags on the verified corpus: "
                 f"{n_err} error(s), {n_warn} warning(s) across {len(ver)} studies "
                 f"({n_err/max(len(ver),1):.2f} errors per study)")
except Exception as e:
    print("  residual-anomaly audit skipped:", e)

# In-context validation (RAISE 1.2, 1.3, 1.9b): AI-versus-human correction data
if "ai_json" in cols:
    n_eval = int(((df["status"] == "verified") &
                  df["ai_json"].notna() &
                  (df["ai_json"].astype(str).str.len() > 2)).sum())
    audit.append(f"In-context evaluation sample (AI values preserved for comparison): "
                 f"{n_eval} studies and growing")

(OUT / "raise_audit.txt").write_text("\n".join(audit) + "\n", encoding="utf-8")
print("\n".join("  " + a for a in audit))
print("\nRAISE audit written to charts/raise_audit.txt")

# ── Summary file ─────────────────────────────────────────────────────────────
(Path(OUT) / "summary_stats.txt").write_text("\n".join(SUMMARY) + "\n", encoding="utf-8")
print(f"\nSummary written to charts/summary_stats.txt ({len(SUMMARY)} figures to quote)")