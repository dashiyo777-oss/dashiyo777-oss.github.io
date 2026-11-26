#!/usr/bin/env python3
"""
国会会議録APIから議員の発言を1件ずつ取得し、発言者の肩書きで
「議員としての発言」「答弁（政府側）」「議事進行」に分けて facts.json に保存する。

背景:
  facts.json の speech_count は、委員会での質問と、大臣・副大臣などとしての
  答弁、議長・委員長としての議事進行をすべて合わせた件数である。
  2026-10-26 の定期便（発言1,000回以上×政党別）で、読者から「答弁を含む数字で
  政党を比べられるのか」と指摘を受けた。会議録APIは発言ごとに speakerPosition
  （例: 内閣総理大臣、文部科学副大臣、議長）を持つため、これで分類する。

  speech_count は変更しない。結果は facts.json の speech_breakdown に別に保存する。

分類（speakerPosition による）:
  government: 大臣・副大臣・大臣政務官・内閣官房長官・内閣官房副長官としての発言
  chair:      議長・副議長・委員長・委員長代理・会長（審査会・調査会）としての発言
  member:     肩書きなし（議員としての質問・討論・趣旨説明など）
  other:      上記以外の肩書き（分類できなかったもの。件数を確認して規則を見直す）

API仕様: https://kokkai.ndl.go.jp/api.html （speech は1回あたり最大100件）

使い方:
  python3 scripts/fetch_speech_breakdown.py               # テスト（最初の5名）
  python3 scripts/fetch_speech_breakdown.py --full        # 全員分（2時間前後）
  python3 scripts/fetch_speech_breakdown.py --ids P001 P173  # 指定した議員のみ
"""

import re
import os
import sys
import json
import time
import argparse
import datetime
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_aliases import get_aliases

# ── 設定 ──────────────────────────────────────
FROM_DATE = "2021-11-01"        # fetch_speech_counts.py と同じ起点
UNTIL_DATE = datetime.date.today().isoformat()
PAGE_SIZE = 100                 # API の上限
SLEEP_SEC = 1.0                 # リクエスト間隔（サーバー負荷対策）
SAVE_EVERY = 10                 # 何名ごとに中間保存するか
TEST_COUNT = 5
# ─────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS_PATH = os.path.join(BASE_DIR, "data.js")
FACTS_PATH = os.path.join(BASE_DIR, "facts.json")
NDL_API = "https://kokkai.ndl.go.jp/api/speech"
ALIASES = get_aliases("ndl")

GOVERNMENT_RE = re.compile(r"大臣|政務官|官房長官|官房副長官")
CHAIR_RE = re.compile(r"議長|委員長|会長")


def classify(position):
    if not position:
        return "member"
    if GOVERNMENT_RE.search(position):
        return "government"
    if CHAIR_RE.search(position):
        return "chair"
    return "other"


def extract_politicians(data_js_path):
    """data.js から id と name を抽出する（fetch_speech_counts.py と同じ規則）。"""
    with open(data_js_path, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(r'id:"(P\d+)"[^}]*?name:"([^"]+)"')
    return [
        {"id": m.group(1), "name": m.group(2).replace("　", "").replace(" ", "")}
        for m in pattern.finditer(content)
    ]


def fetch_page(name, start):
    params = urllib.parse.urlencode({
        "speaker": name,
        "from": FROM_DATE,
        "until": UNTIL_DATE,
        "maximumRecords": PAGE_SIZE,
        "startRecord": start,
        "recordPacking": "json",
    })
    req = urllib.request.Request(
        f"{NDL_API}?{params}", headers={"User-Agent": "TORAN-SpeechBreakdown/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_breakdown(name):
    """1人分の発言をすべて取得し、分類ごとの件数と other の肩書きを返す。"""
    counts = {"member": 0, "government": 0, "chair": 0, "other": 0}
    other_positions = {}
    start, total = 1, None
    while True:
        data = fetch_page(name, start)
        if total is None:
            total = int(data.get("numberOfRecords", 0))
        for rec in data.get("speechRecord", []):
            kind = classify(rec.get("speakerPosition"))
            counts[kind] += 1
            if kind == "other":
                pos = rec.get("speakerPosition")
                other_positions[pos] = other_positions.get(pos, 0) + 1
        nxt = data.get("nextRecordPosition")
        time.sleep(SLEEP_SEC)
        if not nxt:
            break
        start = int(nxt)
    counts["total"] = total
    return counts, other_positions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="全員分を実行")
    parser.add_argument("--ids", nargs="+", help="指定した議員IDのみ実行")
    args = parser.parse_args()

    politicians = extract_politicians(DATA_JS_PATH)
    if args.ids:
        politicians = [p for p in politicians if p["id"] in set(args.ids)]
    elif not args.full:
        politicians = politicians[:TEST_COUNT]
        print(f"[テストモード] 最初の {TEST_COUNT} 名のみ実行")

    with open(FACTS_PATH, encoding="utf-8") as f:
        facts = json.load(f)

    period_str = f"{FROM_DATE}〜{UNTIL_DATE}"
    print(f"対象: {len(politicians)} 名  期間: {period_str}")
    processed, errors = 0, []

    for pol in politicians:
        pid, name = pol["id"], pol["name"]
        entry = facts.setdefault(pid, {"name": name})
        # 同じ日に取得済みならスキップ（中断後の再開用）
        if entry.get("speech_breakdown", {}).get("period") == period_str:
            continue

        names = [name] + [a for a in ALIASES.get(pid, []) if a != name]
        try:
            for candidate in names:
                counts, others = fetch_breakdown(candidate)
                if counts["total"] > 0:
                    break
        except Exception as e:
            print(f"  [ERROR] {pid} {name}: {e}")
            errors.append(pid)
            time.sleep(SLEEP_SEC)
            continue

        counted = counts["member"] + counts["government"] + counts["chair"] + counts["other"]
        result = {**counts, "period": period_str}
        if candidate != name:
            result["alias_used"] = candidate
        if counted != counts["total"]:
            # 取得途中で件数が変わった等。値はそのまま残し、印を付ける
            result["mismatch"] = True
        if others:
            result["other_positions"] = others
        entry["speech_breakdown"] = result

        print(f"  {pid} {name}: 計{counts['total']} 議員{counts['member']} "
              f"答弁{counts['government']} 議事{counts['chair']} 他{counts['other']}")

        processed += 1
        if processed % SAVE_EVERY == 0:
            with open(FACTS_PATH, "w", encoding="utf-8") as f:
                json.dump(facts, f, ensure_ascii=False, indent=2)

    with open(FACTS_PATH, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)
    print(f"\n完了: {processed} 名を更新  エラー: {len(errors)} 名 {errors if errors else ''}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
