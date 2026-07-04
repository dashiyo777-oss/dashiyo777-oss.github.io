#!/usr/bin/env python3
"""
P076(うるま譲司)・P815(大石あきこ)の発言数検証スクリプト。
実データのspeaker表記・会議名を確認して、誤マッチがないかを調べる。
"""

import json, urllib.request, urllib.parse, time

NDL_API = "https://kokkai.ndl.go.jp/api/speech"
FROM_DATE  = "2021-11-01"
UNTIL_DATE = "2026-06-30"
UA = "TORAN-Verify/1.0"


def fetch(params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{NDL_API}?{qs}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def count_only(speaker):
    data = fetch({"speaker": speaker, "from": FROM_DATE, "until": UNTIL_DATE,
                  "maximumRecords": 1, "recordPacking": "json"})
    return int(data["numberOfRecords"])


def sample_records(speaker, n=5):
    data = fetch({"speaker": speaker, "from": FROM_DATE, "until": UNTIL_DATE,
                  "maximumRecords": n, "recordPacking": "json"})
    total = int(data["numberOfRecords"])
    items = data.get("speechRecord", [])
    return total, items


# ── 1. うるま譲司 vs 漆間譲司 件数比較 ──────────────────────────
print("=" * 60)
print("1. numberOfRecords 比較")
print("=" * 60)

for name in ["うるま譲司", "漆間譲司"]:
    c = count_only(name)
    print(f"  speaker={name!r}: {c}件")
    time.sleep(1)

# ── 2. speaker=うるま譲司 の実データ（上位5件）──────────────────
print()
print("=" * 60)
print("2. speaker=うるま譲司 の実データ（上位5件）")
print("=" * 60)

total, records = sample_records("うるま譲司", 5)
print(f"  総件数: {total}件")
for r in records:
    print(f"  - speaker:       {r.get('speaker')!r}")
    print(f"    speakerYomi:   {r.get('speakerYomi')!r}")
    print(f"    speakerGroup:  {r.get('speakerGroup')!r}")
    print(f"    nameOfHouse:   {r.get('nameOfHouse')!r}")
    print(f"    nameOfMeeting: {r.get('nameOfMeeting')!r}")
    print(f"    date:          {r.get('date')!r}")
    print()

time.sleep(1)

# ── 3. speaker=大石あきこ の実データ（上位3件）──────────────────
print("=" * 60)
print("3. speaker=大石あきこ の実データ（上位3件）")
print("=" * 60)

total2, records2 = sample_records("大石あきこ", 3)
print(f"  総件数: {total2}件")
for r in records2:
    print(f"  - speaker:       {r.get('speaker')!r}")
    print(f"    speakerYomi:   {r.get('speakerYomi')!r}")
    print(f"    speakerGroup:  {r.get('speakerGroup')!r}")
    print(f"    nameOfHouse:   {r.get('nameOfHouse')!r}")
    print(f"    nameOfMeeting: {r.get('nameOfMeeting')!r}")
    print(f"    date:          {r.get('date')!r}")
    print()
