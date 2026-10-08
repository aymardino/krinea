"""
prisma.py — PRISMA 2020 flow diagram as SVG, following the official templates
(prisma-statement.org, CC BY 4.0): white boxes with black borders, black
arrows with triangular heads, Arial 9 pt, rounded phase bands "Identification /
Screening / Included" and column headers in the template's light blue.

    svg = prisma.render_svg(counts, variant="new_v2", lang="en")

Variants: new_v1 (databases and registers only), new_v2 (+ other methods),
updated_v1 / updated_v2 (updated reviews, with the previous-version column).
`counts` is the dict produced by the application (identified, by_source,
duplicates_removed, screened, ta_excluded, sought, not_retrieved, assessed,
ft_excluded, ft_excluded_reasons, included …). Missing keys read as 0.
"""
from __future__ import annotations

import html
import re

VARIANTS = ("new_v1", "new_v2", "updated_v1", "updated_v2")
PX = 96                           # inches -> pixels, as in the Word templates
BAND_FILL = "#9DC3E6"             # Office "Blue, Accent 5, Lighter 40 %" used by the templates
FONT = "Arial, Helvetica, sans-serif"
FONT_PX = 12                      # 9 pt
BOX_W = round(2.064 * PX)         # 198 px, the template's box width
BAND_W = round(0.287 * PX)        # 28 px
ROW_H = {"id": round(1.36 * PX), "one": round(0.576 * PX), "inc": round(0.792 * PX)}
GAP_X = round(0.66 * PX)          # horizontal gap between boxes (3.33 - 0.61 - 2.06 in)
MARGIN = 12

_L = {
    "en": {
        "id_header_db": "Identification of studies via databases and registers",
        "id_header_other": "Identification of studies via other methods",
        "id_header_db_new": "Identification of new studies via databases and registers",
        "id_header_other_new": "Identification of new studies via other methods",
        "prev_header": "Previous studies",
        "identification": "Identification", "screening": "Screening", "included": "Included",
        "identified": "Records identified from:", "databases": "Databases", "registers": "Registers",
        "removed": "Records removed before screening:",
        "dup": "Duplicate records removed", "auto": "Records marked as ineligible by automation tools",
        "other_removed": "Records removed for other reasons",
        "screened": "Records screened", "excluded": "Records excluded",
        "sought": "Reports sought for retrieval", "not_retrieved": "Reports not retrieved",
        "assessed": "Reports assessed for eligibility", "reports_excluded": "Reports excluded:",
        "included_studies": "Studies included in review", "included_reports": "Reports of included studies",
        "new_included_studies": "New studies included in review", "new_included_reports": "Reports of new included studies",
        "total_studies": "Total studies included in review", "total_reports": "Reports of total included studies",
        "prev_studies": "Studies included in previous version of review",
        "prev_reports": "Reports of studies included in previous version of review",
        "other_identified": "Records identified from:", "websites": "Websites", "organisations": "Organisations",
        "citation": "Citation searching", "n": "n",
    },
    "fr": {
        "id_header_db": "Identification des études via bases de données et registres",
        "id_header_other": "Identification des études via d'autres méthodes",
        "id_header_db_new": "Identification des nouvelles études via bases de données et registres",
        "id_header_other_new": "Identification des nouvelles études via d'autres méthodes",
        "prev_header": "Études précédentes",
        "identification": "Identification", "screening": "Sélection", "included": "Inclusion",
        "identified": "Notices identifiées depuis :", "databases": "Bases de données", "registers": "Registres",
        "removed": "Notices retirées avant la sélection :",
        "dup": "Doublons retirés", "auto": "Notices jugées inéligibles par des outils automatiques",
        "other_removed": "Notices retirées pour d'autres raisons",
        "screened": "Notices triées", "excluded": "Notices exclues",
        "sought": "Rapports recherchés", "not_retrieved": "Rapports non récupérés",
        "assessed": "Rapports évalués pour éligibilité", "reports_excluded": "Rapports exclus :",
        "included_studies": "Études incluses dans la revue", "included_reports": "Rapports des études incluses",
        "new_included_studies": "Nouvelles études incluses", "new_included_reports": "Rapports des nouvelles études incluses",
        "total_studies": "Total des études incluses", "total_reports": "Rapports du total des études incluses",
        "prev_studies": "Études incluses dans la version précédente",
        "prev_reports": "Rapports des études de la version précédente",
        "other_identified": "Notices identifiées depuis :", "websites": "Sites web", "organisations": "Organisations",
        "citation": "Recherche de citations", "n": "n",
    },
}


_NBSP = "\u00a0"


def _wrap(text: str, max_chars: int = 32) -> list[str]:
    # keep "(n = 1234)" on one line, as the template does
    text = re.sub(r"\((n = [^)]*)\)", lambda m: "(" + m.group(1).replace(" ", _NBSP) + ")", text)
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines or [""]


class _Canvas:
    def __init__(self):
        self.parts: list[str] = []
        self.w = 0
        self.h = 0

    def box(self, x: int, y: int, w: int, h: int, lines: list[str], fill: str = "#FFFFFF",
            rounded: bool = False, bold_first: bool = False, align: str = "left") -> tuple[int, int, int, int]:
        self.w, self.h = max(self.w, x + w), max(self.h, y + h)
        rx = ' rx="6" ry="6"' if rounded else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="#000" '
                          f'stroke-width="1"{rx}/>')
        wrapped: list[tuple[str, bool]] = []
        for i, ln in enumerate(lines):
            for piece in _wrap(ln, max(10, int(w / 6.2))):
                wrapped.append((piece, bold_first and i == 0))
        line_h = FONT_PX + 3
        total = line_h * len(wrapped)
        ty = y + (h - total) / 2 + FONT_PX - 1
        for piece, bold in wrapped:
            tx = x + 7 if align == "left" else x + w / 2
            anchor = "start" if align == "left" else "middle"
            weight = ' font-weight="bold"' if bold else ""
            self.parts.append(f'<text x="{tx:.1f}" y="{ty:.1f}" font-family="{FONT}" font-size="{FONT_PX}" '
                              f'text-anchor="{anchor}"{weight}>{html.escape(piece)}</text>')
            ty += line_h
        return x, y, w, h

    def band(self, x: int, y_top: int, y_bottom: int, label: str) -> None:
        h = y_bottom - y_top
        cx, cy = x + BAND_W / 2, y_top + h / 2
        self.parts.append(f'<rect x="{x}" y="{y_top}" width="{BAND_W}" height="{h}" fill="{BAND_FILL}" '
                          f'stroke="#000" stroke-width="1" rx="6" ry="6"/>')
        self.parts.append(f'<text x="{cx:.1f}" y="{cy:.1f}" font-family="{FONT}" font-size="{FONT_PX}" '
                          f'text-anchor="middle" dominant-baseline="middle" '
                          f'transform="rotate(-90 {cx:.1f} {cy:.1f})">{html.escape(label)}</text>')
        self.w, self.h = max(self.w, x + BAND_W), max(self.h, y_bottom)

    def arrow(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self.parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#000" '
                          f'stroke-width="1" marker-end="url(#arrow)"/>')

    def elbow(self, x1: float, y1: float, x2: float, y2: float) -> None:
        """Right-angle connector: horizontal to x2, then vertical to y2."""
        self.parts.append(f'<polyline points="{x1:.1f},{y1:.1f} {x2:.1f},{y1:.1f} {x2:.1f},{y2:.1f}" fill="none" '
                          f'stroke="#000" stroke-width="1" marker-end="url(#arrow)"/>')

    def svg(self) -> str:
        w, h = self.w + MARGIN, self.h + MARGIN
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
                f'font-family="{FONT}">'
                '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#000"/></marker></defs>'
                f'<rect width="{w}" height="{h}" fill="#FFFFFF"/>')
        return head + "".join(self.parts) + "</svg>"


def _n(c: dict, key: str) -> int:
    try:
        return int(c.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def render_svg(counts: dict, variant: str = "new_v1", lang: str = "en") -> str:
    if variant not in VARIANTS:
        raise ValueError(f"variant must be one of {VARIANTS}")
    L = _L.get(lang, _L["en"])
    c = counts or {}
    updated, other = variant.startswith("updated"), variant.endswith("v2")
    cv = _Canvas()
    N = L["n"]

    # Columns (left to right): [previous] | identified | removed/excluded | [other identified | other not retrieved]
    x = MARGIN + BAND_W + 14
    col_prev = x if updated else None
    if updated:
        x += round(1.59 * PX) + 18
    col1 = x
    col2 = col1 + BOX_W + GAP_X
    col3 = col2 + BOX_W + GAP_X if other else None
    col4 = col3 + BOX_W + GAP_X if other else None

    # Rows
    y_head = MARGIN
    y_id = y_head + 28 + 10
    h_id = ROW_H["id"]
    y_scr = y_id + h_id + 40
    h1 = ROW_H["one"]
    y_sought = y_scr + h1 + 36
    y_assessed = y_sought + h1 + 36
    reasons = c.get("ft_excluded_reasons") or {}
    h_excl = max(round(1.24 * PX), 40 + 15 * (len(reasons) + 1))
    y_inc = y_assessed + max(h1, h_excl) + 40
    h_inc = ROW_H["inc"]

    # Headers
    hdr_db = L["id_header_db_new"] if updated else L["id_header_db"]
    cv.box(col1, y_head, 2 * BOX_W + GAP_X, 28, [hdr_db], fill=BAND_FILL, rounded=True, align="center")
    if other:
        cv.box(col3, y_head, 2 * BOX_W + GAP_X, 28, [L["id_header_other_new"] if updated else L["id_header_other"]],
               fill=BAND_FILL, rounded=True, align="center")
    if updated:
        cv.box(col_prev, y_head, round(1.59 * PX), 28, [L["prev_header"]], fill=BAND_FILL, rounded=True, align="center")

    # Identification row
    sources = c.get("by_source") or {}
    id_lines = [L["identified"], f"{L['databases']} ({N} = {_n(c, 'identified')})", f"{L['registers']} ({N} = 0)"]
    if sources and len(sources) <= 6:
        id_lines = [L["identified"]] + [f"{html.escape(str(k))} ({N} = {v})" for k, v in sources.items()]
    h_id = max(h_id, 22 + 15 * len(id_lines))
    cv.box(col1, y_id, BOX_W, h_id, id_lines)
    cv.box(col2, y_id, BOX_W, h_id, [L["removed"], f"{L['dup']} ({N} = {_n(c, 'duplicates_removed')})",
                                     f"{L['auto']} ({N} = {_n(c, 'automation_excluded')})",
                                     f"{L['other_removed']} ({N} = {_n(c, 'other_removed')})"])
    cv.arrow(col1 + BOX_W, y_id + h_id / 2, col2, y_id + h_id / 2)
    if other:
        cv.box(col3, y_id, BOX_W, h_id, [L["other_identified"], f"{L['websites']} ({N} = {_n(c, 'other_websites')})",
                                         f"{L['organisations']} ({N} = {_n(c, 'other_organisations')})",
                                         f"{L['citation']} ({N} = {_n(c, 'other_citation')})"])
    if updated:
        cv.box(col_prev, y_id, round(1.59 * PX), h_id, [f"{L['prev_studies']} ({N} = {_n(c, 'previous_studies')})",
                                                        f"{L['prev_reports']} ({N} = {_n(c, 'previous_reports')})"])
    cv.band(MARGIN, y_id, y_id + h_id, L["identification"])

    # Screening rows
    y_scr = y_id + h_id + 40
    y_sought = y_scr + h1 + 36
    y_assessed = y_sought + h1 + 36
    y_inc = y_assessed + max(h1, h_excl) + 40
    cv.box(col1, y_scr, BOX_W, h1, [f"{L['screened']} ({N} = {_n(c, 'screened')})"])
    cv.box(col2, y_scr, BOX_W, h1, [f"{L['excluded']} ({N} = {_n(c, 'ta_excluded')})"])
    cv.arrow(col1 + BOX_W / 2, y_id + h_id, col1 + BOX_W / 2, y_scr)
    cv.arrow(col1 + BOX_W, y_scr + h1 / 2, col2, y_scr + h1 / 2)
    cv.box(col1, y_sought, BOX_W, h1, [f"{L['sought']} ({N} = {_n(c, 'sought')})"])
    cv.box(col2, y_sought, BOX_W, h1, [f"{L['not_retrieved']} ({N} = {_n(c, 'not_retrieved')})"])
    cv.arrow(col1 + BOX_W / 2, y_scr + h1, col1 + BOX_W / 2, y_sought)
    cv.arrow(col1 + BOX_W, y_sought + h1 / 2, col2, y_sought + h1 / 2)
    excl_lines = [f"{L['reports_excluded']}"] + [f"{html.escape(str(k))} ({N} = {v})" for k, v in reasons.items()]
    if not reasons:
        excl_lines += [f"Reason 1 ({N} = 0)", f"Reason 2 ({N} = 0)", f"Reason 3 ({N} = 0)"]
    cv.box(col1, y_assessed, BOX_W, h1, [f"{L['assessed']} ({N} = {_n(c, 'assessed')})"])
    cv.box(col2, y_assessed, BOX_W, h_excl, excl_lines)
    cv.arrow(col1 + BOX_W / 2, y_sought + h1, col1 + BOX_W / 2, y_assessed)
    cv.arrow(col1 + BOX_W, y_assessed + h1 / 2, col2, y_assessed + h1 / 2)
    if other:
        cv.box(col3, y_sought, BOX_W, h1, [f"{L['sought']} ({N} = {_n(c, 'other_sought')})"])
        cv.box(col4, y_sought, BOX_W, h1, [f"{L['not_retrieved']} ({N} = {_n(c, 'other_not_retrieved')})"])
        cv.arrow(col3 + BOX_W / 2, y_id + h_id, col3 + BOX_W / 2, y_sought)
        cv.arrow(col3 + BOX_W, y_sought + h1 / 2, col4, y_sought + h1 / 2)
        cv.box(col3, y_assessed, BOX_W, h1, [f"{L['assessed']} ({N} = {_n(c, 'other_assessed')})"])
        cv.box(col4, y_assessed, BOX_W, h_excl, [L["reports_excluded"], f"Reason 1 ({N} = 0)", f"Reason 2 ({N} = 0)"])
        cv.arrow(col3 + BOX_W / 2, y_sought + h1, col3 + BOX_W / 2, y_assessed)
        cv.arrow(col3 + BOX_W, y_assessed + h1 / 2, col4, y_assessed + h1 / 2)
    cv.band(MARGIN, y_scr, y_assessed + max(h1, h_excl), L["screening"])

    # Included
    if updated:
        cv.box(col1, y_inc, BOX_W, h_inc, [f"{L['new_included_studies']} ({N} = {_n(c, 'included')})",
                                           f"{L['new_included_reports']} ({N} = {_n(c, 'reports_included')})"])
        y_total = y_inc + h_inc + 36
        total_studies = _n(c, "included") + _n(c, "previous_studies")
        total_reports = _n(c, "reports_included") + _n(c, "previous_reports")
        cv.box(col1, y_total, BOX_W, h_inc, [f"{L['total_studies']} ({N} = {total_studies})",
                                             f"{L['total_reports']} ({N} = {total_reports})"])
        cv.arrow(col1 + BOX_W / 2, y_inc + h_inc, col1 + BOX_W / 2, y_total)
        cv.elbow(col_prev + round(1.59 * PX) / 2, y_id + h_id, col_prev + round(1.59 * PX) / 2, y_total + h_inc / 2)
        cv.arrow(col_prev + round(1.59 * PX) / 2, y_total + h_inc / 2, col1, y_total + h_inc / 2)
        band_bottom = y_total + h_inc
    else:
        cv.box(col1, y_inc, BOX_W, h_inc, [f"{L['included_studies']} ({N} = {_n(c, 'included')})",
                                           f"{L['included_reports']} ({N} = {_n(c, 'reports_included')})"])
        band_bottom = y_inc + h_inc
    cv.arrow(col1 + BOX_W / 2, y_assessed + h1, col1 + BOX_W / 2, y_inc)
    if other:
        cv.elbow(col3 + BOX_W / 2, y_assessed + h1, col3 + BOX_W / 2, y_inc + h_inc / 2)
        cv.arrow(col3 + BOX_W / 2, y_inc + h_inc / 2, col1 + BOX_W, y_inc + h_inc / 2)
    cv.band(MARGIN, y_inc, band_bottom, L["included"])
    return cv.svg()
