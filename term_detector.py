# -*- coding: utf-8 -*-
import os, re
from datetime import datetime
from zoneinfo import ZoneInfo

# ===== Config =====
SHORT_TERM_MONTHS_DEFAULT = 6  # override with env SHORT_TERM_MONTHS

# ===== Helpers =====
_CPH = ZoneInfo("Europe/Copenhagen")
MONTHS_DA_FULL = ["januar","februar","marts","april","maj","juni","juli","august","september","oktober","november","december"]
MONTHS_EN_FULL = ["january","february","march","april","may","june","july","august","september","october","november","december"]
MONTHS_DA_ABBR = ["jan","feb","mar","apr","maj","jun","jul","aug","sep","okt","nov","dec"]
MONTHS_EN_ABBR = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]

MONTH_NAME_TO_NUM = {m:i+1 for i,m in enumerate(MONTHS_DA_FULL)}
MONTH_NAME_TO_NUM.update({m:i+1 for i,m in enumerate(MONTHS_EN_FULL)})
MONTH_NAME_TO_NUM.update({m:i+1 for i,m in enumerate(MONTHS_DA_ABBR)})
MONTH_NAME_TO_NUM.update({m:i+1 for i,m in enumerate(MONTHS_EN_ABBR)})

def _now_cph() -> datetime:
    return datetime.now(_CPH)

def _months_between(a: datetime, b: datetime) -> float:
    return (b.year - a.year) * 12 + (b.month - a.month) + (b.day - a.day) / 30.0

def _to_year(y: int) -> int:
    return y + 2000 if y < 100 else y

def _parse_numeric_date(day: int, mon: int, year: int) -> datetime | None:
    try:
        return datetime(_to_year(year), mon, day, tzinfo=_CPH)
    except ValueError:
        return None

def _parse_textual_date(day: int | None, mon_name: str, year: int) -> datetime | None:
    mon = MONTH_NAME_TO_NUM.get(mon_name.lower()[:3]) or MONTH_NAME_TO_NUM.get(mon_name.lower())
    if not mon:
        return None
    if day is None:
        day = 28  # assume late month if day omitted
    return _parse_numeric_date(day, mon, _to_year(year))

# ===== Patterns =====
NUMERIC_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
TEXTUAL_DATE_WITH_DAY = re.compile(r"\b(\d{1,2})\s+([A-Za-zæøåÆØÅ]+)\s+(\d{2,4})\b")
TEXTUAL_DATE_MONTH_YEAR = re.compile(r"\b([A-Za-zæøåÆØÅ]+)\s+(\d{2,4})\b")

# explicit duration (months / weeks)
DURATION_PATTERNS = [
    r"\b(\d{1,2})\s*[-\s]?(?:months?|mos?|mths?)\b",
    r"\b(\d{1,2})\s*(?:mdr\.?|måneder)\b",
    r"\b(\d{1,2})\s*(?:weeks?|uger)\b",  # weeks ~ n/4 months
]

# explicit end cues (do NOT include generic 'til' here)
ENDDATE_CUES = re.compile(r"\b(indtil|until|ending|ends|udløber|slutter|senest)\b", re.I)

# “range context” words that indicate a period between two dates
RANGE_TERMS = re.compile(r"\b(i\s+perioden|perioden|tidsrum|fra)\b", re.I)

# binding/minimum-term context
BINDING_TERMS = re.compile(r"\b(bindingsperiode|binding|ubrydelig\s+lejeperiode|min(?:\.|imum)?\s+binding)\b", re.I)

def _extract_all_dates(text: str) -> list[datetime]:
    dates: list[datetime] = []
    for d, m, y in NUMERIC_DATE.findall(text):
        dt = _parse_numeric_date(int(d), int(m), int(y))
        if dt: dates.append(dt)
    for d, mon_name, y in TEXTUAL_DATE_WITH_DAY.findall(text):
        dt = _parse_textual_date(int(d), mon_name, int(y))
        if dt: dates.append(dt)
    for mon_name, y in TEXTUAL_DATE_MONTH_YEAR.findall(text):
        dt = _parse_textual_date(None, mon_name, int(y))
        if dt: dates.append(dt)
    # sort + dedupe
    dates = sorted({dt.isoformat(): dt for dt in dates}.values())
    return dates

def _extract_date_spans(text: str) -> list[tuple[int, int, datetime]]:
    """Return list of (start, end, datetime) for every detected date."""
    spans: list[tuple[int,int,datetime]] = []

    for m in NUMERIC_DATE.finditer(text):
        d, mo, y = m.groups()
        dt = _parse_numeric_date(int(d), int(mo), int(y))
        if dt: spans.append((m.start(), m.end(), dt))

    for m in TEXTUAL_DATE_WITH_DAY.finditer(text):
        d, mon_name, y = m.groups()
        dt = _parse_textual_date(int(d), mon_name, int(y))
        if dt: spans.append((m.start(), m.end(), dt))

    for m in TEXTUAL_DATE_MONTH_YEAR.finditer(text):
        mon_name, y = m.groups()
        dt = _parse_textual_date(None, mon_name, int(y))
        if dt: spans.append((m.start(), m.end(), dt))

    # sort by position
    spans.sort(key=lambda x: x[0])
    return spans

def _first_duration_months(tl: str) -> tuple[float, re.Match] | tuple[None, None]:
    for pat in DURATION_PATTERNS:
        for m in re.finditer(pat, tl):
            n = float(m.group(1))
            months = n / 4.0 if ("week" in pat or "uger" in pat) else n
            return months, m
    return None, None

def is_short_term_heuristic(
    text: str,
    months_threshold: int | None = None,
    now: datetime | None = None,
) -> dict:
    months_threshold = months_threshold or int(os.getenv("SHORT_TERM_MONTHS", SHORT_TERM_MONTHS_DEFAULT))
    now = now or _now_cph()

    t = " ".join((text or "").split())
    tl = t.lower()

    # 1) Explicit duration — but guard for binding context nearby
    dur, dur_match = _first_duration_months(tl)
    if dur is not None:
        # binding near the duration?
        binding_nearby = False
        if dur_match:
            left = tl[max(0, dur_match.start() - 48): dur_match.start()]
            right = tl[dur_match.end(): dur_match.end() + 48]
            binding_nearby = bool(BINDING_TERMS.search(left)) or bool(BINDING_TERMS.search(right))

        if binding_nearby:
            return {
                "is_short_term": False,
                "reason": f"Binding period ~{dur:.1f} months indicates a minimum term, not an end date",
                "end_date": None,
                "confidence": "high",
            }
        # otherwise treat as explicit duration
        if dur <= months_threshold:
            return {
                "is_short_term": True,
                "reason": f"Explicit duration ~{dur:.1f} months ≤ {months_threshold}",
                "end_date": None,
                "confidence": "high",
            }
        # duration > threshold → not short by duration; keep checking dates
        # (do not early-return True)

    # 2) Dates: detect ranges or single end dates
    dates = _extract_all_dates(t)

   # 2a) Range detection between two date spans
    date_spans = _extract_date_spans(t)
    if len(date_spans) >= 2:
        CONNECTOR = re.compile(r"\b(to|til|indtil|until)\b|[-–—]", re.I)
        RANGE_HINT_NEAR = re.compile(r"\b(i\s+perioden|perioden|tidsrum\w*|fra)\b", re.I)  # tidsrummet/tidsrumet, etc.

        for i in range(len(date_spans) - 1):
            s1, e1, d1 = date_spans[i]
            s2, e2, d2 = date_spans[i + 1]
            between = t[e1:s2]
            before_first = t[max(0, s1 - 48): s1]

            connector_between = CONNECTOR.search(between) is not None
            just_gap_between = len(between) <= 24 and re.fullmatch(r"[\s,.;:()/\-–—]*", between) is not None
            range_hint_before = RANGE_HINT_NEAR.search(before_first) is not None

            if connector_between or (just_gap_between and range_hint_before):
                start, end = (d1, d2) if d1 <= d2 else (d2, d1)
                range_months = _months_between(start, end)
                if range_months <= months_threshold:
                    return {
                        "is_short_term": True,
                        "reason": f"Date range {start.date()} → {end.date()} (~{range_months:.1f} months ≤ {months_threshold})",
                        "end_date": end.isoformat(),
                        "confidence": "high",
                    }
                # If longer than threshold, keep checking single end-date below
                break  # only consider the first adjacent pair

    # 2b) Single explicit end cue + a date (e.g., “indtil 15.08.2026”, “ending January 2026”)
    if ENDDATE_CUES.search(tl) and dates:
        end = dates[-1]
        months_left = _months_between(now, end)
        if months_left <= months_threshold:
            return {
                "is_short_term": True,
                "reason": f"End date {end.date()} is ~{months_left:.1f} months from now ≤ {months_threshold}",
                "end_date": end.isoformat(),
                "confidence": "med",
            }
        else:
            return {
                "is_short_term": False,
                "reason": f"End date {end.date()} is ~{months_left:.1f} months from now > {months_threshold}",
                "end_date": end.isoformat(),
                "confidence": "med",
            }

    # 3) Nothing decisive → not short-term
    return {
        "is_short_term": False,
        "reason": "No clear duration or rental period (range/end) detected; any 'binding' is a minimum term",
        "end_date": None,
        "confidence": "low",
    }
