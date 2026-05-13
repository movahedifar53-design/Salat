import requests
from bs4 import BeautifulSoup
import json
import sys

def scrape_prayer_times(city):
    url = f"https://najaf.org/english/prayer/united-kingdom?ct={city}"
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    results = []
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')
        # Find which month this table belongs to by looking at preceding header
        month_num = None

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 8:
                try:
                    day = int(cells[0].get_text(strip=True))
                except ValueError:
                    continue

                imsaak = cells[1].get_text(strip=True)
                dawn = cells[2].get_text(strip=True)
                sunrise = cells[3].get_text(strip=True)
                noon = cells[4].get_text(strip=True)
                sunset = cells[5].get_text(strip=True)
                maghrib = cells[6].get_text(strip=True)
                midnight = cells[7].get_text(strip=True)

                # Validate time format
                for t in [imsaak, dawn, sunrise, noon, sunset, maghrib, midnight]:
                    if ':' not in t:
                        break
                else:
                    results.append({
                        'day': day,
                        'imsaak': imsaak,
                        'dawn': dawn,
                        'sunrise': sunrise,
                        'noon': noon,
                        'sunset': sunset,
                        'maghrib': maghrib,
                        'midnight': midnight
                    })

    # Now assign months - the tables should be in order Jan-Dec
    # Group by sequential day resets (day goes from high back to 1)
    months_data = []
    current_month = []
    prev_day = 0

    for entry in results:
        if entry['day'] <= prev_day and current_month:
            months_data.append(current_month)
            current_month = []
        current_month.append(entry)
        prev_day = entry['day']

    if current_month:
        months_data.append(current_month)

    # Build final output with month numbers
    final = []
    for month_idx, month_entries in enumerate(months_data):
        month_num = month_idx + 1
        for entry in month_entries:
            entry['month'] = month_num
            final.append(entry)

    # Reorder keys
    ordered = []
    for entry in final:
        ordered.append({
            'month': entry['month'],
            'day': entry['day'],
            'imsaak': entry['imsaak'],
            'dawn': entry['dawn'],
            'sunrise': entry['sunrise'],
            'noon': entry['noon'],
            'sunset': entry['sunset'],
            'maghrib': entry['maghrib'],
            'midnight': entry['midnight']
        })

    return ordered

if __name__ == '__main__':
    for city in ['birmingham', 'london']:
        print(f"Scraping {city}...")
        data = scrape_prayer_times(city)
        print(f"  Got {len(data)} days, months: {data[0]['month']}-{data[-1]['month']}")

        # Spot check
        for m, d in [(1,1), (3,24), (6,21), (9,15), (12,31)]:
            row = [r for r in data if r['month']==m and r['day']==d]
            if row:
                r = row[0]
                print(f"  {m:2d}/{d:2d}: {r['imsaak']} {r['dawn']} {r['sunrise']} {r['noon']} {r['sunset']} {r['maghrib']} {r['midnight']}")
            else:
                print(f"  {m:2d}/{d:2d}: NOT FOUND")

        outfile = f"data_{city}.json"
        with open(outfile, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  Saved to {outfile}")
