"""
Scrape Toronto prayer times from valieasr.org.

Page layout: 12 tables (Jan-Dec). Each table has rows:
  [month-name]
  ['Date', 'فجر', 'طلوع', 'ظهر', 'غروب', 'مغرب']
  ['1', fajr, sunrise, noon, sunset, maghrib]
  ...
  optionally a 1-cell notice row like 'Daylight Saving (+1 Hour)'
  optionally a duplicate day row around the DST transition

The source uses 12-hour times for most rows but occasionally writes
hours > 12 (e.g. noon on March 8 appears as '13:29'). It also has at
least one typo where maghrib is written in AM ('5:56' instead of
'7:56' on March 29). We handle both.

Imsaak and Midnight aren't on this site:
  - Imsaak is dropped (the app no longer shows it).
  - Midnight is computed as the midpoint between sunset and the NEXT
    day's Fajr (Shar'i convention).
"""

import requests
from bs4 import BeautifulSoup
import json

URL = "http://www.valieasr.org/calendar/Prayer-Times.htm"
OUT = "data_toronto.json"


def to24(t, slot):
    """Convert 'h:mm' to 24-hour 'HH:MM'.

    Convention on this page:
      - dawn/sunrise are AM (~3:30-7:50 range)
      - noon/sunset/maghrib are PM
      - very rarely the source already writes the 24-hour form
        (e.g. '13:29') — detect and pass through.
    """
    h, m = t.split(":")
    h, m = int(h), int(m)
    if h > 12:
        # source already wrote 24-hour form
        hh = h
    elif slot in ("dawn", "sunrise"):
        hh = h % 12  # AM, "12:xx" -> 00:xx (shouldn't happen for these slots)
    else:
        hh = h if h == 12 else h + 12  # PM
    return f"{hh:02d}:{m:02d}"


def to_min(hhmm):
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def from_min(mins):
    mins %= 24 * 60
    return f"{mins // 60:02d}:{mins % 60:02d}"


def fetch_tables(url):
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.find_all("table")


def parse(tables):
    out = []
    for month_idx, t in enumerate(tables[:12]):
        month = month_idx + 1
        seen_days = set()
        for row in t.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) < 6:
                continue  # skips month-name, header, and DST-notice rows
            if not cells[0].isdigit():
                continue
            day = int(cells[0])
            if day in seen_days:
                continue  # drops the duplicate Nov 6 row at DST end
            times = cells[1:6]
            if not all(":" in s and s.split(":")[0].isdigit() for s in times):
                continue
            seen_days.add(day)
            out.append({
                "month": month,
                "day": day,
                "dawn":    to24(times[0], "dawn"),
                "sunrise": to24(times[1], "sunrise"),
                "noon":    to24(times[2], "noon"),
                "sunset":  to24(times[3], "sunset"),
                "maghrib": to24(times[4], "maghrib"),
            })
    return out


def repair_maghrib(data):
    """If maghrib lands before sunset (source typo, e.g. '5:56' instead of
    '7:56'), set maghrib = sunset + 15 min."""
    for row in data:
        s = to_min(row["sunset"])
        mg = to_min(row["maghrib"])
        # treat any maghrib that's earlier than sunset or absurdly late as bad
        if mg < s or mg - s > 60:
            row["maghrib"] = from_min(s + 15)
            row["_maghrib_repaired"] = True
    return data


def compute_midnight(data):
    """Shar'i midnight = midpoint between sunset and NEXT day's Fajr."""
    n = len(data)
    for i, row in enumerate(data):
        nxt = data[(i + 1) % n]
        sunset_min = to_min(row["sunset"])
        fajr_min = to_min(nxt["dawn"]) + 24 * 60
        mid = (sunset_min + fajr_min) // 2
        row["midnight"] = from_min(mid)
    return data


if __name__ == "__main__":
    print(f"Fetching {URL} ...")
    tables = fetch_tables(URL)
    print(f"  got {len(tables)} tables")
    data = parse(tables)
    print(f"  parsed {len(data)} day rows")

    data = repair_maghrib(data)
    repaired = [(r['month'], r['day']) for r in data if r.pop('_maghrib_repaired', False)]
    if repaired:
        print(f"  repaired maghrib on: {repaired}")

    data = compute_midnight(data)

    # Days-per-month sanity check
    counts = {}
    for r in data:
        counts[r['month']] = counts.get(r['month'], 0) + 1
    print(f"  days/month: {counts}")

    # Spot checks
    for m, d in [(1, 1), (3, 8), (3, 29), (6, 21), (11, 6), (11, 7), (12, 31)]:
        r = next((x for x in data if x["month"] == m and x["day"] == d), None)
        if r:
            print(f"  {m:2d}/{d:2d}  fajr {r['dawn']}  sunrise {r['sunrise']}  "
                  f"noon {r['noon']}  sunset {r['sunset']}  maghrib {r['maghrib']}  "
                  f"midnight {r['midnight']}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {OUT} ({len(data)} entries)")
