#!/usr/bin/env python3
"""Fetch East Money (东方财富) financial calendar → eastmoney_calendar.ics (stdlib only).

Sources (no login):
  1) https://data.eastmoney.com/dataapi/dcrl/dstx
     options: xsap (休市), jjsj (经济数据), hyhy (会议)
  2) Optional supplement: datacenter RPT_CPH_FECALENDAR (same meeting set as hyhy)

Filters out noisy Choice rows (库存等) and low-signal industry expos.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_PATH = ROOT / "eastmoney_calendar.ics"

DSTX = "https://data.eastmoney.com/dataapi/dcrl/dstx"
# Pull ~90 days ahead (and a few days back for in-progress holidays/meetings).
LOOKBACK_DAYS = 3
HORIZON_DAYS = 90
# dstx rejects weird option values with 500; stick to known codes.
OPTIONS = "xsap,jjsj,hyhy"

TZ_SH = timezone(timedelta(hours=8))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ashare-calendar/1.0; +https://github.com/lbhsh/ashare-calendar)",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://data.eastmoney.com/dcrl/dashi.html",
}

# Drop commodity inventory noise etc.
SKIP_SUBSTR = (
    "库存",
    "精粉",
    "球团",
    "块矿",
    "贸易矿",
    "铁矿石",
    "电解铝",
    "螺纹钢",
    "热卷",
    "煤炭库存",
    "仓单",
)

# China/HK economic keywords (still skip inventory noise).
MACRO_KW_CN = (
    "GDP",
    "CPI",
    "PPI",
    "PMI",
    "LPR",
    "社融",
    "社会融资",
    "M2",
    "M1",
    "工业增加值",
    "社会消费品零售",
    "进出口",
    "贸易差额",
    "外汇储备",
    "新增人民币贷款",
    "城镇调查失业率",
    "失业率",
    "降准",
    "降息",
    "公开市场",
    "贷款市场报价",
)
# Non-China: only high-signal US/global releases (WSCN already covers broad macros).
MACRO_KW_GLOBAL = (
    "非农",
    "非农业",
    "FOMC",
    "利率决议",
    "联邦基金",
    "核心PCE",
    "PCE物价",
    "初请失业",
    "ADP",
    "ISM:PMI",
    "ISM：PMI",
    "ISM PMI",
)

# Meetings: keep only high-signal types / name keywords.
MEETING_FE_TYPES = {
    "美联储议息会议",
    "中国共产党中央全会",
}
MEETING_KW = (
    "美联储",
    "FOMC",
    "议息",
    "中央全会",
    "中央经济",
    "两会",
    "全国人大",
    "全国政协",
    "政治局",
    "降准",
    "降息",
    "G20",
    "APEC",
    "金砖",
    "财长和央行行长",
)

MKT_KEEP = ("A股", "港股", "沪股通", "深股通", "港股通")


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
    return f"em-{event_id}-{digest}@ashare-calendar.local"


def parse_em_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = str(s).strip().replace("/", "-")
    if len(s) >= 19:
        chunk, fmt = s[:19], "%Y-%m-%d %H:%M:%S"
    elif len(s) >= 16:
        chunk, fmt = s[:16], "%Y-%m-%d %H:%M"
    else:
        chunk, fmt = s[:10], "%Y-%m-%d"
    try:
        return datetime.strptime(chunk, fmt).replace(tzinfo=TZ_SH)
    except ValueError:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=TZ_SH)
        except ValueError:
            return None


def is_china_city(city: str) -> bool:
    c = city or ""
    return any(x in c for x in ("中国", "香港", "澳门", "台湾"))


def keep_macro_name(name: str, city: str) -> bool:
    if not name:
        return False
    if any(s in name for s in SKIP_SUBSTR):
        return False
    if is_china_city(city) or name.startswith("中国"):
        return any(k in name for k in MACRO_KW_CN)
    return any(k in name for k in MACRO_KW_GLOBAL)


def keep_meeting(item: dict) -> bool:
    fe_type = item.get("FE_TYPE") or ""
    name = item.get("FE_NAME") or ""
    if fe_type in MEETING_FE_TYPES:
        return True
    # Do not scan CONTENT — diplomatic notes often false-positive on short KW.
    blob = fe_type + name
    return any(k in blob for k in MEETING_KW)


def keep_mkt(mkt: str) -> bool:
    return any(k in (mkt or "") for k in MKT_KEEP)


def fetch_dstx(fromdate: date, todate: date) -> dict:
    qs = urllib.parse.urlencode(
        {
            "fromdate": fromdate.isoformat(),
            "todate": todate.isoformat(),
            "option": OPTIONS,
        }
    )
    url = f"{DSTX}?{qs}"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} fetching {url}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"URL error fetching {url}: {e}") from e
    if not isinstance(data, dict):
        raise SystemExit(f"unexpected dstx payload type={type(data)}")
    # HTML error pages sometimes sneak through as str after decode issues
    if "xsap" not in data and "jjsj" not in data and "hyhy" not in data:
        raise SystemExit(f"dstx missing expected keys: {list(data.keys())[:10]}")
    return data


def events_from_xsap(rows: list) -> list[dict]:
    out = []
    for i, item in enumerate(rows or []):
        if not keep_mkt(item.get("MKT") or ""):
            continue
        start = parse_em_dt(item.get("SDATE"))
        end = parse_em_dt(item.get("EDATE")) or start
        if not start:
            continue
        holiday = item.get("HOLIDAY") or "休市"
        mkt = item.get("MKT") or ""
        half = str(item.get("XS") or "") == "1"
        day = "半天" if half else "全天"
        title = f"[休市] {holiday} · {mkt}（{day}）"
        # all-day inclusive: ICS DTEND is exclusive → +1 day after end date
        start_d = start.date()
        end_d = (end.date() if end else start_d) + timedelta(days=1)
        eid = f"xsap-{start_d.isoformat()}-{mkt}-{holiday}-{day}"
        out.append(
            {
                "kind": "xsap",
                "eid": eid,
                "all_day": True,
                "start_d": start_d,
                "end_d": end_d,
                "summary": title,
                "desc": f"因{holiday}{mkt}{day}休市\n来源：东方财富大事提醒 / Choice",
                "cat": "休市",
            }
        )
    return out


def events_from_jjsj(rows: list) -> list[dict]:
    out = []
    for day in rows or []:
        dt = parse_em_dt(day.get("Date"))
        if not dt:
            continue
        city_day = day.get("City") or ""
        for item in day.get("Data") or []:
            name = (item.get("Name") or "").strip()
            city = (item.get("City") or city_day or "").strip()
            if not keep_macro_name(name, city):
                continue
            # midnight → all-day; otherwise timed 1h block
            all_day = dt.hour == 0 and dt.minute == 0 and dt.second == 0
            summary = name
            if city and not name.startswith(city):
                summary = f"[{city}] {name}"
            # trim verbose Choice suffixes a bit for SUMMARY length
            if len(summary) > 120:
                summary = summary[:117] + "..."
            eid = f"jjsj-{dt.strftime('%Y%m%dT%H%M%S')}-{name}"
            out.append(
                {
                    "kind": "jjsj",
                    "eid": eid,
                    "all_day": all_day,
                    "start": dt,
                    "end": dt + timedelta(hours=1),
                    "start_d": dt.date(),
                    "end_d": dt.date() + timedelta(days=1),
                    "summary": summary,
                    "desc": f"地区：{city or '-'}\n来源：东方财富大事提醒 / Choice 经济数据",
                    "cat": "经济数据",
                }
            )
    return out


def events_from_hyhy(rows: list) -> list[dict]:
    out = []
    for item in rows or []:
        if not keep_meeting(item):
            continue
        start = parse_em_dt(item.get("START_DATE"))
        end = parse_em_dt(item.get("END_DATE")) or start
        if not start:
            continue
        name = (item.get("FE_NAME") or "会议").strip()
        fe_type = (item.get("FE_TYPE") or "会议").strip()
        code = item.get("FE_CODE") or ""
        title = f"[会议] {name}"
        if fe_type and fe_type not in name:
            title = f"[会议·{fe_type}] {name}"
        start_d = start.date()
        end_d = (end.date() if end else start_d) + timedelta(days=1)
        parts = [f"类型：{fe_type}"]
        if item.get("CITY"):
            parts.append(f"地点：{item['CITY']}")
        if item.get("SPONSOR_NAME"):
            parts.append(f"主办：{item['SPONSOR_NAME']}")
        if item.get("CONTENT"):
            parts.append(str(item["CONTENT"])[:500])
        parts.append("来源：东方财富财经日历 / Choice")
        eid = f"hyhy-{code or name}-{start_d.isoformat()}"
        out.append(
            {
                "kind": "hyhy",
                "eid": eid,
                "all_day": True,
                "start_d": start_d,
                "end_d": end_d,
                "summary": title[:140],
                "desc": "\n".join(parts),
                "cat": "会议",
            }
        )
    return out


def to_vevent(ev: dict, stamp: str) -> str:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{stable_uid(ev['eid'])}",
        f"DTSTAMP:{stamp}",
    ]
    if ev.get("all_day"):
        lines.append(f"DTSTART;VALUE=DATE:{ev['start_d'].strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{ev['end_d'].strftime('%Y%m%d')}")
    else:
        lines.append(
            f"DTSTART;TZID=Asia/Shanghai:{ev['start'].strftime('%Y%m%dT%H%M%S')}"
        )
        lines.append(
            f"DTEND;TZID=Asia/Shanghai:{ev['end'].strftime('%Y%m%dT%H%M%S')}"
        )
    lines.extend(
        [
            fold_ics(f"SUMMARY:{escape_text(ev['summary'])}"),
            fold_ics(f"DESCRIPTION:{escape_text(ev['desc'])}"),
            fold_ics(f"CATEGORIES:{escape_text(ev.get('cat') or '东方财富')}"),
            "TRANSP:TRANSPARENT",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ]
    )
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


def build_ics(events: list[dict]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # dedupe by eid
    by_id: dict[str, dict] = {}
    for ev in events:
        by_id[ev["eid"]] = ev
    events = list(by_id.values())

    def sort_key(ev: dict):
        if ev.get("all_day"):
            return (ev["start_d"].isoformat(), "0", ev["summary"])
        return (ev["start"].isoformat(), "1", ev["summary"])

    events.sort(key=sort_key)
    parts = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Bing Liu//East Money Calendar//ZH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        fold_ics("X-WR-CALNAME:东方财富财经日历"),
        "X-WR-TIMEZONE:Asia/Shanghai",
        fold_ics(
            "X-WR-CALDESC:东方财富大事提醒（休市+筛选后经济数据+重要会议）；fetch_eastmoney_calendar.py"
        ),
        vtimezone_shanghai(),
    ]
    for ev in events:
        parts.append(to_vevent(ev, stamp))
    parts.append("END:VCALENDAR")
    return "\r\n".join(parts) + "\r\n"


def main() -> None:
    today = datetime.now(TZ_SH).date()
    start = today - timedelta(days=LOOKBACK_DAYS)
    end = today + timedelta(days=HORIZON_DAYS)
    raw = fetch_dstx(start, end)
    time.sleep(0.2)
    events: list[dict] = []
    events.extend(events_from_xsap(raw.get("xsap") or []))
    events.extend(events_from_jjsj(raw.get("jjsj") or []))
    events.extend(events_from_hyhy(raw.get("hyhy") or []))
    # dedupe + sort for reporting (same as ICS)
    by_id = {e["eid"]: e for e in events}
    events = list(by_id.values())

    def sort_key(ev: dict):
        if ev.get("all_day"):
            return (ev["start_d"].isoformat(), "0", ev["summary"])
        return (ev["start"].isoformat(), "1", ev["summary"])

    events.sort(key=sort_key)
    ics = build_ics(events)
    OUT_PATH.write_bytes(ics.encode("utf-8"))
    n_xsap = sum(1 for e in events if e["kind"] == "xsap")
    n_jj = sum(1 for e in events if e["kind"] == "jjsj")
    n_hy = sum(1 for e in events if e["kind"] == "hyhy")
    print(
        f"Wrote {OUT_PATH} ({len(events)} events; "
        f"xsap={n_xsap}, jjsj={n_jj}, hyhy={n_hy}; "
        f"window={start}→{end})"
    )
    for e in events[:10]:
        when = (
            e["start_d"].isoformat()
            if e.get("all_day")
            else e["start"].strftime("%Y-%m-%d %H:%M")
        )
        print(f"  sample: {when} {e['summary'][:90]}")
    if len(events) > 10:
        print(f"  ... and {len(events) - 10} more")
    if len(events) == 0:
        raise SystemExit("no events after filter — aborting")


if __name__ == "__main__":
    main()
