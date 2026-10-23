#!/usr/bin/env python3
"""Generate A-share financial-events ICS calendar (stdlib only)."""

from __future__ import annotations

import json
import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVENTS_PATH = ROOT / "events.json"
OUT_PATH = ROOT / "ashare_events.ics"

WEEKDAY = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    d += timedelta(weeks=n - 1)
    if d.month != month:
        raise ValueError(f"no {n}th weekday={weekday} in {year}-{month:02d}")
    return d


def fold_ics(line: str, limit: int = 75) -> str:
    """RFC5545 line folding (UTF-8 safe enough for Chinese titles)."""
    if len(line.encode("utf-8")) <= limit:
        return line
    out = []
    buf = ""
    for ch in line:
        trial = buf + ch
        if len(trial.encode("utf-8")) > limit and buf:
            out.append(buf)
            buf = " " + ch
        else:
            buf = trial
    if buf:
        out.append(buf)
    return "\r\n".join(out)


def escape_text(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def stable_uid(event_id: str) -> str:
    digest = hashlib.sha1(event_id.encode("utf-8")).hexdigest()[:16]
    return f"{event_id}-{digest}@ashare-calendar.local"


def dtstamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def load_data() -> dict:
    with EVENTS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def generated_events(data: dict) -> list[dict]:
    gens = data.get("generators") or {}
    out: list[dict] = []
    for key, cfg in gens.items():
        if not cfg.get("enabled"):
            continue
        weekday = WEEKDAY[cfg["weekday"].lower()]
        nth = int(cfg["nth"])
        skip = set(cfg.get("skip_keys") or [])
        for year in cfg.get("years") or []:
            for month in range(1, 13):
                ym = f"{year}-{month:02d}"
                if ym in skip:
                    continue
                d = nth_weekday(year, month, weekday, nth)
                eid = f"{cfg['id_prefix']}-{d.isoformat()}"
                out.append(
                    {
                        "id": eid,
                        "date": d.isoformat(),
                        "title": cfg["title"],
                        "category": "交割",
                        "description": cfg.get("description", ""),
                        "status": "confirmed",
                        "source": key,
                    }
                )
    return out


def all_events(data: dict) -> list[dict]:
    curated = list(data.get("events") or [])
    # Drop generated counterparts overridden by curated
    overridden = set()
    for e in curated:
        ov = e.get("overrides_generated")
        if ov:
            overridden.add(ov)
    generated = []
    for e in generated_events(data):
        src = e.get("source")
        ym = e["date"][:7]
        if src and f"{src}:{ym}" in overridden:
            continue
        # also support skip via generators.skip_keys already applied
        generated.append(e)
    merged = curated + generated
    # de-dupe by id
    seen = set()
    unique = []
    for e in merged:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        unique.append(e)
    unique.sort(key=lambda x: (x["date"], x["title"]))
    return unique


def vevent(e: dict, stamp: str) -> str:
    d = date.fromisoformat(e["date"])
    next_d = d + timedelta(days=1)
    status = "TENTATIVE" if e.get("status") == "tentative" else "CONFIRMED"
    desc = e.get("description") or ""
    if e.get("status") == "tentative" and "待公告" not in (e.get("title") or ""):
        desc = (desc + "\n（日期待官方公告确认）").strip()
    lines = [
        "BEGIN:VEVENT",
        f"UID:{stable_uid(e['id'])}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{next_d.strftime('%Y%m%d')}",
        fold_ics(f"SUMMARY:{escape_text(e['title'])}"),
        fold_ics(f"DESCRIPTION:{escape_text(desc)}"),
        f"CATEGORIES:{escape_text(e.get('category') or 'A股')}",
        "TRANSP:TRANSPARENT",
        f"STATUS:{status}",
        "END:VEVENT",
    ]
    return "\r\n".join(lines)


def build_ics(data: dict, events: list[dict]) -> str:
    stamp = dtstamp_utc()
    name = data.get("calendar_name") or "A股金融节点"
    tz = data.get("timezone") or "Asia/Shanghai"
    parts = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Bing Liu//A-Share Events//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        fold_ics(f"X-WR-CALNAME:{escape_text(name)}"),
        f"X-WR-TIMEZONE:{tz}",
        "X-WR-CALDESC:A股调仓/两会/交割/财报/政策节点（手工维护+规则生成）",
    ]
    for e in events:
        parts.append(vevent(e, stamp))
    parts.append("END:VCALENDAR")
    return "\r\n".join(parts) + "\r\n"


def main() -> None:
    data = load_data()
    events = all_events(data)
    ics = build_ics(data, events)
    OUT_PATH.write_text(ics, encoding="utf-8", newline="\n")
    # normalize to CRLF as written above already uses \r\n
    OUT_PATH.write_bytes(ics.encode("utf-8"))
    print(f"Wrote {OUT_PATH} ({len(events)} events)")
    for e in events[:8]:
        print(f"  sample: {e['date']} {e['title']}")
    if len(events) > 8:
        print(f"  ... and {len(events) - 8} more")


if __name__ == "__main__":
    main()
