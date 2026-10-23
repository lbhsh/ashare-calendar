#!/usr/bin/env python3
"""Fetch Wall Street CN (华尔街见闻) macro calendar → wscn_macro.ics (stdlib only)."""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "wscn_macro.ics"

API = "https://api-one-wscn.awtmt.com/apiv1/finance/macrodatas"
# API rejects windows longer than ~30 days; chunk requests.
CHUNK_DAYS = 28
# How far ahead to pull (days).
HORIZON_DAYS = 90
# Filter: keep all China events, plus non-CN with importance >= MIN_GLOBAL_IMPORTANCE.
# WSCN importance is typically 1–4 (4 = highest).
MIN_GLOBAL_IMPORTANCE = 3
CN_IDS = {"CN"}
# Also keep Hong Kong as China-related.
CN_RELATED_IDS = {"CN", "HK"}

TZ_SH = timezone(timedelta(hours=8))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ashare-calendar/1.0; +https://github.com/lbhsh/ashare-calendar)",
    "Accept": "application/json",
    "Referer": "https://wallstreetcn.com/",
    "Origin": "https://wallstreetcn.com",
}


def fold_ics(line: str, limit: int = 75) -> str:
    if len(line.encode("utf-8")) <= limit:
        return line
    out: list[str] = []
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
    return f"wscn-{event_id}-{digest}@ashare-calendar.local"


def fetch_chunk(start: int, end: int) -> list[dict]:
    url = f"{API}?start={start}&end={end}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} fetching {url}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"URL error fetching {url}: {e}") from e

    code = data.get("code")
    if code != 20000:
        raise SystemExit(f"API code={code} message={data.get('message')!r} url={url}")
    items = (data.get("data") or {}).get("items") or []
    if not isinstance(items, list):
        return []
    return items


def fetch_all(now: int | None = None) -> list[dict]:
    now = int(now if now is not None else time.time())
    horizon_end = now + HORIZON_DAYS * 86400
    by_id: dict[int | str, dict] = {}
    cursor = now
    while cursor < horizon_end:
        chunk_end = min(cursor + CHUNK_DAYS * 86400, horizon_end)
        items = fetch_chunk(cursor, chunk_end)
        for it in items:
            eid = it.get("id")
            if eid is None:
                continue
            by_id[eid] = it
        # Advance; if API returns empty far out, still step forward.
        cursor = chunk_end
        time.sleep(0.35)
    return list(by_id.values())


def keep(item: dict) -> bool:
    cid = (item.get("country_id") or "").upper()
    imp = int(item.get("importance") or 0)
    if cid in CN_RELATED_IDS:
        return True
    return imp >= MIN_GLOBAL_IMPORTANCE


def format_desc(item: dict) -> str:
    parts = []
    country = item.get("country") or item.get("country_id") or ""
    if country:
        parts.append(f"国家/地区：{country}")
    imp = item.get("importance")
    if imp is not None:
        parts.append(f"重要性：{imp}/4")
    period = item.get("period") or ""
    if period:
        parts.append(f"周期：{period}")
    for label, key in (
        ("公布值", "actual"),
        ("预期", "forecast"),
        ("前值", "previous"),
        ("修正", "revised"),
    ):
        val = item.get(key)
        if val not in (None, ""):
            parts.append(f"{label}：{val}")
    mark = item.get("mark") or ""
    if mark:
        parts.append(str(mark))
    parts.append("来源：华尔街见闻宏观日历")
    return "\n".join(parts)


def summary(item: dict) -> str:
    title = (item.get("title") or item.get("event") or "宏观数据").strip()
    country = (item.get("country") or "").strip()
    if country and not title.startswith(country):
        return f"[{country}] {title}"
    return title


def to_vevent(item: dict, stamp: str) -> str | None:
    ts = item.get("public_date")
    if not ts:
        return None
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return None
    eid = str(item.get("id"))
    dt = datetime.fromtimestamp(ts, TZ_SH)
    # 1-hour block; many WSCN times are release clocks.
    dt_end = dt + timedelta(hours=1)
    dtstart = dt.strftime("%Y%m%dT%H%M%S")
    dtend = dt_end.strftime("%Y%m%dT%H%M%S")
    cat = item.get("country") or item.get("country_id") or "宏观"
    lines = [
        "BEGIN:VEVENT",
        f"UID:{stable_uid(eid)}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;TZID=Asia/Shanghai:{dtstart}",
        f"DTEND;TZID=Asia/Shanghai:{dtend}",
        fold_ics(f"SUMMARY:{escape_text(summary(item))}"),
        fold_ics(f"DESCRIPTION:{escape_text(format_desc(item))}"),
        fold_ics(f"CATEGORIES:{escape_text(str(cat))}"),
        "TRANSP:TRANSPARENT",
        "STATUS:CONFIRMED",
        "END:VEVENT",
    ]
    return "\r\n".join(lines)


def vtimezone_shanghai() -> str:
    # Minimal VTIMEZONE for Asia/Shanghai (no DST since 1991).
    return "\r\n".join(
        [
            "BEGIN:VTIMEZONE",
            "TZID:Asia/Shanghai",
            "X-LIC-LOCATION:Asia/Shanghai",
            "BEGIN:STANDARD",
            "TZOFFSETFROM:+0800",
            "TZOFFSETTO:+0800",
            "TZNAME:CST",
            "DTSTART:19700101T000000",
            "END:STANDARD",
            "END:VTIMEZONE",
        ]
    )


def build_ics(items: list[dict]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    kept = [i for i in items if keep(i)]
    kept.sort(key=lambda x: (int(x.get("public_date") or 0), str(x.get("id"))))
    parts = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Bing Liu//WSCN Macro//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        fold_ics("X-WR-CALNAME:华尔街见闻宏观"),
        "X-WR-TIMEZONE:Asia/Shanghai",
        fold_ics(
            "X-WR-CALDESC:华尔街见闻宏观（中国全部 + 全球重要性≥3）；由 fetch_wscn_macro.py 自动更新"
        ),
        vtimezone_shanghai(),
    ]
    for it in kept:
        ve = to_vevent(it, stamp)
        if ve:
            parts.append(ve)
    parts.append("END:VCALENDAR")
    return "\r\n".join(parts) + "\r\n"


def main() -> None:
    raw = fetch_all()
    ics = build_ics(raw)
    OUT_PATH.write_bytes(ics.encode("utf-8"))
    kept = [i for i in raw if keep(i)]
    cn = sum(1 for i in kept if (i.get("country_id") or "").upper() in CN_RELATED_IDS)
    print(
        f"Wrote {OUT_PATH} ({len(kept)} events from {len(raw)} raw; "
        f"CN/HK={cn}, global high-imp={len(kept) - cn}; "
        f"horizon={HORIZON_DAYS}d, filter=CN/HK all OR importance>={MIN_GLOBAL_IMPORTANCE})"
    )
    for i in kept[:8]:
        ts = int(i["public_date"])
        print(
            f"  sample: {datetime.fromtimestamp(ts, TZ_SH).isoformat()} "
            f"imp={i.get('importance')} {summary(i)}"
        )
    if len(kept) > 8:
        print(f"  ... and {len(kept) - 8} more")
    if len(kept) == 0:
        raise SystemExit("no events after filter — aborting without overwrite expectation")


if __name__ == "__main__":
    main()
