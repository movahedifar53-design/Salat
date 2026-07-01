"""
Generate data_munich.json for the Salat Widget PWA.

Prayer times computed astronomically with the standard PrayTimes.org core
using the University of Tehran (Institute of Geophysics) Shia parameters:
    Fajr    = 17.7 deg below horizon
    Maghrib = 4.5  deg below horizon (Shia maghrib, redness gone)
    Midnight = Jafari (midpoint of sunset -> next fajr)

Munich: lat 48.1374 N, lon 11.5755 E, base timezone UTC+1 (CET),
DST (CEST, UTC+2) from 29 Mar 2026 to 25 Oct 2026.

Fields written per day: dawn (Fajr), sunrise, noon (Dhuhr),
sunset (true), maghrib (Shia), midnight (Jafari).
"""
import json
import math
from datetime import date, timedelta

LAT = 48.1374
LON = 11.5755
TZ_BASE = 1  # CET, UTC+1
YEAR = 2026

# Tehran / Institute of Geophysics angles
FAJR_ANGLE = 17.7
MAGHRIB_ANGLE = 4.5
RISESET_ANGLE = 0.833  # sunrise/sunset with standard refraction, elv=0

# ---- trig helpers in degrees ----
def dtr(d): return d * math.pi / 180.0
def rtd(r): return r * 180.0 / math.pi
def sin(d): return math.sin(dtr(d))
def cos(d): return math.cos(dtr(d))
def arcsin(x): return rtd(math.asin(x))
def arccos(x): return rtd(math.acos(x))
def arctan2(y, x): return rtd(math.atan2(y, x))

def fixangle(a):
    a = a - 360.0 * math.floor(a / 360.0)
    return a + 360.0 if a < 0 else a

def fixhour(a):
    a = a - 24.0 * math.floor(a / 24.0)
    return a + 24.0 if a < 0 else a

def julian(y, m, d):
    if m <= 2:
        y -= 1
        m += 12
    A = math.floor(y / 100.0)
    B = 2 - A + math.floor(A / 4.0)
    return (math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1))
            + d + B - 1524.5)

def sun_position(jd):
    D = jd - 2451545.0
    g = fixangle(357.529 + 0.98560028 * D)
    q = fixangle(280.459 + 0.98564736 * D)
    L = fixangle(q + 1.915 * sin(g) + 0.020 * sin(2 * g))
    e = 23.439 - 0.00000036 * D
    RA = arctan2(cos(e) * sin(L), cos(L)) / 15.0
    eqt = q / 15.0 - fixhour(RA)
    decl = arcsin(sin(e) * sin(L))
    return decl, eqt

class DayCalc:
    def __init__(self, y, m, d, lat, lon, tz):
        self.lat = lat
        self.lon = lon
        self.tz = tz
        self.jdate = julian(y, m, d) - lon / (15.0 * 24.0)

    def mid_day(self, t):
        eqt = sun_position(self.jdate + t)[1]
        return fixhour(12.0 - eqt)

    def sun_angle_time(self, angle, t, ccw=False):
        decl = sun_position(self.jdate + t)[0]
        noon = self.mid_day(t)
        inner = (-sin(angle) - sin(decl) * sin(self.lat)) / (cos(decl) * cos(self.lat))
        inner = max(-1.0, min(1.0, inner))
        tt = (1.0 / 15.0) * arccos(inner)
        return noon + (-tt if ccw else tt)

    def compute(self):
        # initial day-portion guesses (hours/24)
        fajr = self.sun_angle_time(FAJR_ANGLE, 5.0 / 24.0, ccw=True)
        sunrise = self.sun_angle_time(RISESET_ANGLE, 6.0 / 24.0, ccw=True)
        dhuhr = self.mid_day(12.0 / 24.0)
        sunset = self.sun_angle_time(RISESET_ANGLE, 18.0 / 24.0)
        maghrib = self.sun_angle_time(MAGHRIB_ANGLE, 18.0 / 24.0)

        times = {'fajr': fajr, 'sunrise': sunrise, 'dhuhr': dhuhr,
                 'sunset': sunset, 'maghrib': maghrib}
        # to local clock time
        off = self.tz - self.lon / 15.0
        for k in times:
            times[k] = fixhour(times[k] + off)

        # Jafari midnight = sunset + (next-day-fajr - sunset)/2
        # duration sunset->fajr crosses midnight, so use fixhour of the diff
        night = fixhour((times['fajr'] + 24.0) - times['sunset'])
        times['midnight'] = fixhour(times['sunset'] + night / 2.0)
        return times

def hm(x):
    # round to nearest minute, format HH:MM
    total = int(round(x * 60.0))
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"

def is_dst(d):
    # CEST 2026: 29 Mar 02:00 -> 25 Oct 03:00
    return date(2026, 3, 29) <= d < date(2026, 10, 25)

records = []
d = date(YEAR, 1, 1)
while d.year == YEAR:
    tz = TZ_BASE + (1 if is_dst(d) else 0)
    t = DayCalc(d.year, d.month, d.day, LAT, LON, tz).compute()
    records.append({
        "month": d.month,
        "day": d.day,
        "dawn": hm(t['fajr']),
        "sunrise": hm(t['sunrise']),
        "noon": hm(t['dhuhr']),
        "sunset": hm(t['sunset']),
        "maghrib": hm(t['maghrib']),
        "midnight": hm(t['midnight']),
    })
    d += timedelta(days=1)

with open("data_munich.json", "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False)

print(f"Wrote {len(records)} days to data_munich.json")
# quick sanity print for a few dates
for probe in [(1, 1), (3, 21), (6, 21), (9, 23), (12, 21)]:
    r = next(x for x in records if x['month'] == probe[0] and x['day'] == probe[1])
    print(r)

# Qibla bearing for Munich (reference; app computes this live from GPS)
def qibla(lat, lon):
    mlat, mlon = 21.4225, 39.8262
    dl = dtr(mlon - lon)
    y = math.sin(dl) * math.cos(dtr(mlat))
    x = (math.cos(dtr(lat)) * math.sin(dtr(mlat))
         - math.sin(dtr(lat)) * math.cos(dtr(mlat)) * math.cos(dl))
    return (rtd(math.atan2(y, x)) + 360) % 360
print(f"Munich Qibla bearing = {qibla(LAT, LON):.1f} deg from true North")
