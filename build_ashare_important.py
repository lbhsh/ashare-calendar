#!/usr/bin/env python3
"""Build the single primary A-share important ICS feed (stdlib only).

Merges:
  1) Curated ashare nodes from events.json (MSCI/中证/两会/交割/财报/政策)
  2) Strict China high-impact macros from Wall Street CN API
     (官方PMI / CPI / PPI / LPR / GDP / 社融 / 新增人民币贷款)
  3) Optional rare US spillover: FOMC / 美联储利率决议 only

Writes: ashare_important.ics
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import generate_ics as curated

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "ashare_important.ics"

API = "https://api-one-wscn.awtmt.com/apiv1/finance/macrodatas"
CHUNK_DAYS = 28
HORIZON_DAYS = 90

TZ_SH = timezone(timedelta(hours=8))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ashare-calendar/1.0; +https://github.com/lbhsh/ashare-calendar)",
    "Accept": "application/json",
    "Referer": "https://wallstreetcn.com/",
    "Origin": "https://wallstreetcn.com",
}

# China high-impact only — keep list short on purpose.
CN_KEEP_KW = (
    "官方制造业PMI",
    "官方非制造业PMI",
    "官方综合PMI",
    "CPI",
    "PPI",
    "LPR",
    "贷款市场报价",
    "GDP",
    "社会融资",
    "社融",
    "新增人民币贷款",
)

# Titles that look macro but are noise even if they hit a short KW.
CN_SKIP_SUBSTR = (
    "RatingDog",
    "财新",
    "外汇储备",
    "M0",
    "M1",
    "M2",  # often co-released with 社融; drop to reduce clutter
    "贸易帐",
    "进口同比",
    "出口同比",
    "经常帐",
    "工业增加值",
    "社会消费品零售",
    "失业率",
    "房地产开发",
    "固定资产投资",
    "工业企业利润",
    "大会",
    "展览会",
    "博览会",
    "论坛",
    "峰会",
    "IPO",
    "截止日",  # 财报截止已在手工节点
)

# Rare US spillover only.
FOMC_KW = (
    "美联储利率决议",
    "FOMC利率决议",
    "联邦基金利率决议",
)


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


def stable_uid(prefix: str, event_id: str) -> str:
    digest = hashlib.sha1(f"{prefix}:{event_id}".encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{event_id}-{digest}@ashare-calendar.local"


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
    if data.get("code") != 20000:
        raise SystemExit(f"API code={data.get('code')} message={data.get('message')!r}")
    items = (data.get("data") or {}).get("items") or []
    return items if isinstance(items, list) else []


def fetch_wscn(now: int | None = None) -> list[dict]:
    now = int(now if now is not None else time.time())
    horizon_end = now + HORIZON_DAYS * 86400
    by_id: dict = {}
    cursor = now
    while cursor < horizon_end:
        chunk_end = min(cursor + CHUNK_DAYS * 86400, horizon_end)
        for it in fetch_chunk(cursor, chunk_end):
            eid = it.get("id")
            if eid is not None:
                by_id[eid] = it
        cursor = chunk_end
        time.sleep(0.35)
    return list(by_id.values())


def title_of(item: dict) -> str:
    return (item.get("title") or item.get("event") or "").strip()


def keep_cn_macro(item: dict) -> bool:
    cid = (item.get("country_id") or "").upper()
    if cid != "CN":
        return False
    title = title_of(item)
    if not title:
        return False
    if any(s in title for s in CN_SKIP_SUBSTR):
        return False
    # Prefer 官方 PMI only (skip bare "PMI" without 官方 via KW list).
    return any(k in title for k in CN_KEEP_KW)


def keep_fomc(item: dict) -> bool:
    title = title_of(item)
    if not title:
        return False
    return any(k in title for k in FOMC_KW)


def format_macro_desc(item: dict) -> str:
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
    parts.append("来源：华尔街见闻（严格筛选写入 A股重要节点）")
    return "\n".join(parts)


def macro_summary(item: dict) -> str:
    title = title_of(item)
    cid = (item.get("country_id") or "").upper()
    if cid == "CN":
        return f"[宏观] {title}"
    country = (item.get("country") or cid or "").strip()
    if country:
        return f"[宏观·{country}] {title}"
    return f"[宏观] {title}"


def vevent_curated(e: dict, stamp: str) -> str:
    d = date.fromisoformat(e["date"])
    next_d = d + timedelta(days=1)
    status = "TENTATIVE" if e.get("status") == "tentative" else "CONFIRMED"
    desc = e.get("description") or ""
    if e.get("status") == "tentative" and "待公告" not in (e.get("title") or ""):
        desc = (desc + "\n（日期待官方公告确认）").strip()
    lines = [
        "BEGIN:VEVENT",
        f"UID:{stable_uid('curated', e['id'])}",
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


def vevent_macro(item: dict, stamp: str) -> str | None:
    ts = item.get("public_date")
    if not ts:
        return None
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        return None
    eid = str(item.get("id"))
    dt = datetime.fromtimestamp(ts, TZ_SH)
    dt_end = dt + timedelta(hours=1)
    lines = [
        "BEGIN:VEVENT",
        f"UID:{stable_uid('macro', eid)}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;TZID=Asia/Shanghai:{dt.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND;TZID=Asia/Shanghai:{dt_end.strftime('%Y%m%dT%H%M%S')}",
        fold_ics(f"SUMMARY:{escape_text(macro_summary(item))}"),
        fold_ics(f"DESCRIPTION:{escape_text(format_macro_desc(item))}"),
        "CATEGORIES:宏观",
        "TRANSP:TRANSPARENT",
        "STATUS:CONFIRMED",
        "END:VEVENT",
    ]
    return "\r\n".join(lines)


def vtimezone_shanghai() -> str:
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


def build_ics(curated_events: list[dict], macros: list[dict]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parts = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Bing Liu//A-Share Important//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        fold_ics("X-WR-CALNAME:A股重要节点"),
        "X-WR-TIMEZONE:Asia/Shanghai",
        fold_ics(
            "X-WR-CALDESC:A股最重要节点：调仓/两会/交割/财报/政策 + 中国高影响宏观（官方PMI/CPI/PPI/LPR/GDP/社融/信贷）+ 可选FOMC"
        ),
        vtimezone_shanghai(),
    ]
    for e in curated_events:
        parts.append(vevent_curated(e, stamp))
    for it in macros:
        ve = vevent_macro(it, stamp)
        if ve:
            parts.append(ve)
    parts.append("END:VCALENDAR")
    return "\r\n".join(parts) + "\r\n"


def main() -> None:
    data = curated.load_data()
    curated_events = curated.all_events(data)
    raw = fetch_wscn()
    cn = [i for i in raw if keep_cn_macro(i)]
    fomc = [i for i in raw if keep_fomc(i)]
    # de-dupe by id
    macros_by_id = {i.get("id"): i for i in cn + fomc}
    macros = list(macros_by_id.values())
    macros.sort(key=lambda x: (int(x.get("public_date") or 0), str(x.get("id"))))

    ics = build_ics(curated_events, macros)
    OUT_PATH.write_bytes(ics.encode("utf-8"))

    print(
        f"Wrote {OUT_PATH} "
        f"(curated={len(curated_events)}, cn_macro={len(cn)}, fomc={len(fomc)}, "
        f"total={len(curated_events) + len(macros)}; horizon={HORIZON_DAYS}d)"
    )
    print("  curated sample:")
    for e in curated_events[:5]:
        print(f"    {e['date']} {e['title']}")
    print("  macro sample:")
    for i in macros[:12]:
        ts = int(i["public_date"])
        print(
            f"    {datetime.fromtimestamp(ts, TZ_SH).strftime('%Y-%m-%d %H:%M')} "
            f"{macro_summary(i)}"
        )
    if len(macros) > 12:
        print(f"    ... and {len(macros) - 12} more macros")


if __name__ == "__main__":
    main()
