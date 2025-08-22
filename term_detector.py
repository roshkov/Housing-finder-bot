# -*- coding: utf-8 -*-
import os, re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Tuple, List

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

def _parse_numeric_date(day: int, mon: int, year: int) -> Optional[datetime]:
    try:
        return datetime(_to_year(year), mon, day, tzinfo=_CPH)
    except ValueError:
        return None

# ---- Month lookups ----
def _mon_from_name(name: str) -> Optional[int]:
    if not name:
        return None
    s = name.strip().lower()
    return MONTH_NAME_TO_NUM.get(s[:3]) or MONTH_NAME_TO_NUM.get(s)

# ---- Ordinal helpers ----
_ORDINAL = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?\.?$", re.I)  # 2, 2nd, 2., 2nd.

def _parse_ordinal_day(token: str) -> Optional[int]:
    m = _ORDINAL.match(token.strip())
    return int(m.group(1)) if m else None

# ===== Patterns (ANY-ORDER) =====
NUMERIC_DMY = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")  # D-M-Y or M-D-Y (resolved later)
NUMERIC_YMD_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")        # 2025-09-02

# Textual variants (DA/EN months), any order with optional year and ordinals.
TEXTUAL_DAY_MONTH_YEAROPT = re.compile(
    r"\b(\d{1,2}(?:st|nd|rd|th)?\.?)\s+([A-Za-zæøåÆØÅ]+)(?:\s+(\d{2,4}))?\b"
)
TEXTUAL_MONTH_DAY_YEAROPT = re.compile(
    r"\b([A-Za-zæøåÆØÅ]+)\s+(\d{1,2}(?:st|nd|rd|th)?\.?)(?:,)?(?:\s+(\d{2,4}))?\b"
)
TEXTUAL_MONTH_YEAR = re.compile(
    r"\b([A-Za-zæøåÆØÅ]+)\s+(\d{2,4})\b"
)

# explicit duration (months / weeks)
DURATION_PATTERNS = [
    r"\b(\d{1,2})\s*[-\s]?(?:months?|mos?|mths?)\b",
    r"\b(\d{1,2})\s*(?:mdr\.?|måneder)\b",
    r"\b(\d{1,2})\s*(?:weeks?|uger)\b",  # weeks ~ n/4 months
]

# cues
ENDDATE_CUES = re.compile(r"\b(indtil|until|ending|ends|udløber|slutter|senest)\b", re.I)
RANGE_TERMS = re.compile(r"\b(i\s+perioden|perioden|tidsrum\w*|fra|from)\b", re.I)
BINDING_TERMS = re.compile(r"\b(bindingsperiode|binding|ubrydelig\s+lejeperiode|min(?:\.|imum)?\s+binding)\b", re.I)
CONNECTOR = re.compile(r"\b(to|til|indtil|until|through|thru)\b|[-–—]\s*", re.I)
OR_TERMS = re.compile(r"\b(or|eller)\b", re.I)  # NEW: treat as alternatives, not ranges
STARTDATE_CUES = re.compile(r"\b(ledigt\s+fra|available\s+from|from|fra)\b", re.I)

SHORTTERM_CUES = re.compile(
    r"\b(temporary|short[-\s]?term|sublet|sublease|midlertidig|midlertidigt|korttids|fremleje|fremlejet|lejlighedshotel)\b",
    re.I
)

# ===== Parsers =====
def _try_parse_numeric_anyorder(a: str, b: str, c: str) -> Optional[datetime]:
    """Try DMY first (EU/DK default), then MDY; also accept YMD if 'a' looks like a year."""
    if len(a) == 4:
        dt = _parse_numeric_date(int(c), int(b), int(a))
        if dt:
            return dt

    d1, m1, y1 = int(a), int(b), int(c)

    dt = _parse_numeric_date(d1, m1, y1)  # D-M-Y
    if dt:
        return dt

    dt = _parse_numeric_date(m1, d1, y1)  # M-D-Y
    if dt:
        return dt

    if len(a) == 4:
        dt = _parse_numeric_date(int(c), int(b), int(a))
        if dt:
            return dt

    return None

def _parse_textual_day_month_yearopt(day_token: str, mon_name: str, year_str: Optional[str]) -> Tuple[Optional[datetime], bool]:
    mon = _mon_from_name(mon_name)
    if not mon:
        return None, False
    day = _parse_ordinal_day(day_token)
    if day is None:
        return None, False
    had_year = year_str is not None
    year = int(year_str) if year_str else _now_cph().year
    return _parse_numeric_date(day, mon, year), had_year

def _parse_textual_month_day_yearopt(mon_name: str, day_token: str, year_str: Optional[str]) -> Tuple[Optional[datetime], bool]:
    mon = _mon_from_name(mon_name)
    if not mon:
        return None, False
    day = _parse_ordinal_day(day_token)
    if day is None:
        return None, False
    had_year = year_str is not None
    year = int(year_str) if year_str else _now_cph().year
    return _parse_numeric_date(day, mon, year), had_year

def _parse_textual_month_year(mon_name: str, year_str: str) -> Optional[datetime]:
    mon = _mon_from_name(mon_name)
    if not mon:
        return None
    return _parse_numeric_date(28, mon, int(year_str))  # assume late-month

# ===== Extraction =====
def _extract_all_dates(text: str) -> List[datetime]:
    dates: List[datetime] = []

    for y, m, d in NUMERIC_YMD_ISO.findall(text):
        dt = _parse_numeric_date(int(d), int(m), int(y))
        if dt: dates.append(dt)

    for a, b, c in NUMERIC_DMY.findall(text):
        dt = _try_parse_numeric_anyorder(a, b, c)
        if dt: dates.append(dt)

    for day, mon, y in TEXTUAL_DAY_MONTH_YEAROPT.findall(text):
        dt, _had_year = _parse_textual_day_month_yearopt(day, mon, y if y else None)
        if dt: dates.append(dt)
    for mon, day, y in TEXTUAL_MONTH_DAY_YEAROPT.findall(text):
        dt, _had_year = _parse_textual_month_day_yearopt(mon, day, y if y else None)
        if dt: dates.append(dt)
    for mon, y in TEXTUAL_MONTH_YEAR.findall(text):
        dt = _parse_textual_month_year(mon, y)
        if dt: dates.append(dt)

    return sorted({dt.isoformat(): dt for dt in dates}.values())

def _extract_date_spans(text: str) -> List[Tuple[int, int, datetime, bool]]:
    """Return (start, end, datetime, had_year) for every detected date."""
    spans: List[Tuple[int,int,datetime,bool]] = []

    for m in NUMERIC_YMD_ISO.finditer(text):
        y, mo, d = m.groups()
        dt = _parse_numeric_date(int(d), int(mo), int(y))
        if dt: spans.append((m.start(), m.end(), dt, True))

    for m in NUMERIC_DMY.finditer(text):
        a, b, c = m.groups()
        dt = _try_parse_numeric_anyorder(a, b, c)
        if dt: spans.append((m.start(), m.end(), dt, True))  # numeric has a year

    for m in TEXTUAL_DAY_MONTH_YEAROPT.finditer(text):
        day, mon, y = m.groups()
        dt, had_year = _parse_textual_day_month_yearopt(day, mon, y if y else None)
        if dt: spans.append((m.start(), m.end(), dt, had_year))

    for m in TEXTUAL_MONTH_DAY_YEAROPT.finditer(text):
        mon, day, y = m.groups()
        dt, had_year = _parse_textual_month_day_yearopt(mon, day, y if y else None)
        if dt: spans.append((m.start(), m.end(), dt, had_year))

    for m in TEXTUAL_MONTH_YEAR.finditer(text):
        mon, y = m.groups()
        dt = _parse_textual_month_year(mon, y)
        if dt: spans.append((m.start(), m.end(), dt, True))

    spans.sort(key=lambda x: x[0])
    return spans

def _first_duration_months(tl: str):
    for pat in DURATION_PATTERNS:
        for m in re.finditer(pat, tl):
            n = float(m.group(1))
            months = n / 4.0 if ("week" in pat or "uger" in pat) else n
            return months, m
    return None, None

# ===== Heuristic =====
def is_short_term_heuristic(
    text: str,
    months_threshold: Optional[int] = None,
    now: Optional[datetime] = None,
) -> dict:
    months_threshold = months_threshold or int(os.getenv("SHORT_TERM_MONTHS", SHORT_TERM_MONTHS_DEFAULT))
    now = now or _now_cph()

    t = " ".join((text or "").split())
    tl = t.lower()

    # 0) Cue words → hint of short-term (unless contradicted by binding later)
    cue_hit = SHORTTERM_CUES.search(tl) is not None
    if cue_hit and not BINDING_TERMS.search(tl):
        # Don't let cue words override explicit long durations/ranges; we early-return
        # only if no binding, and we'll still check durations/ranges below if needed.
        cue_only = True
    else:
        cue_only = False

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
        if dur <= months_threshold:
            return {
                "is_short_term": True,
                "reason": f"Explicit duration ~{dur:.1f} months ≤ {months_threshold}",
                "end_date": None,
                "confidence": "high",
            }
        # duration > threshold → keep checking dates

    # 2) Dates: detect ranges or single end dates
    dates = _extract_all_dates(t)
    date_spans = _extract_date_spans(t)

    # 2a) Range detection between two date spans
    if len(date_spans) >= 2:
        for i in range(len(date_spans) - 1):
            s1, e1, d1, y1 = date_spans[i]
            s2, e2, d2, y2 = date_spans[i + 1]
            between = t[e1:s2]
            before_first = t[max(0, s1 - 48): s1]

            # NEW: if there's "or/eller" between the two dates, treat as alternatives, not a range
            if OR_TERMS.search(between):
                continue

            connector_between = CONNECTOR.search(between) is not None
            just_gap_between = len(between) <= 24 and re.fullmatch(r"[\s,.;:()/\-–—]*", between) is not None
            range_hint_before = RANGE_TERMS.search(before_first) is not None

            if connector_between or (just_gap_between and range_hint_before):
                # Year inference: if exactly one side lacked an explicit year, project it from the other side
                if y1 and not y2:
                    d2 = d2.replace(year=d1.year)
                elif y2 and not y1:
                    d1 = d1.replace(year=d2.year)

                start, end = (d1, d2) if d1 <= d2 else (d2, d1)
                range_months = _months_between(start, end)
                if range_months <= months_threshold:
                    return {
                        "is_short_term": True,
                        "reason": f"Date range {start.date()} → {end.date()} (~{range_months:.1f} months ≤ {months_threshold})",
                        "end_date": end.isoformat(),
                        "confidence": "high",
                    }
                # longer than threshold: keep checking single end-date below
                break  # only consider the first adjacent pair

    # 2b) Single explicit end cue + a date
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

    # 2c) NEW: Handle "start only" availability like "ledigt fra 1. juli eller 1. august"
    # If there are dates but no range/end/duration, and a start cue is present, do NOT classify as short-term.
    if STARTDATE_CUES.search(tl) and dates and dur is None and not ENDDATE_CUES.search(tl):
        return {
            "is_short_term": False,
            "reason": "Only a start/availability date detected (e.g., 'ledigt fra ...'); no end date or duration provided",
            "end_date": None,
            "confidence": "med",
        }

    # 3) Cue-only fallback (no binding and nothing contradicting)
    if cue_only:
        return {
            "is_short_term": True,
            "reason": "Cue word suggests temporary/short-term; no contrary binding, duration, or end date detected",
            "end_date": None,
            "confidence": "low",
        }

    # 4) Nothing decisive → not short-term
    return {
        "is_short_term": False,
        "reason": "No clear duration or rental period (range/end) detected; any 'binding' is a minimum term",
        "end_date": None,
        "confidence": "low",
    }
