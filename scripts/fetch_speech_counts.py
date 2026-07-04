#!/usr/bin/env python3
"""
国会会議録APIから議員の発言数を取得し facts.json に保存するスクリプト。
API仕様: https://kokkai.ndl.go.jp/api/speech

使い方:
  python3 scripts/fetch_speech_counts.py          # テストモード（最初の5名）
  python3 scripts/fetch_speech_counts.py --full   # 全員分
"""

import re
import json
import time
import urllib.request
import urllib.parse
import os
import argparse
import datetime

# ── 設定 ──────────────────────────────────────
FROM_DATE = "2021-11-01"        # 第49回衆院選後の臨時国会開始
UNTIL_DATE = datetime.date.today().isoformat()  # 実行日
SLEEP_SEC = 0.5                 # リクエスト間隔（サーバー負荷対策）
SAVE_EVERY = 20                 # 何名ごとに中間保存するか
TEST_COUNT = 5                  # テストモードで処理する人数
# ─────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS_PATH = os.path.join(BASE_DIR, "data.js")
OUTPUT_PATH = os.path.join(BASE_DIR, "facts.json")
ERROR_LOG_PATH = os.path.join(BASE_DIR, "error_log.txt")
NDL_API = "https://kokkai.ndl.go.jp/api/speech"


def extract_politicians(data_js_path):
    """data.js から id と name を抽出して返す。"""
    with open(data_js_path, encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(r'id:"(P\d+)"[^}]*?name:"([^"]+)"')
    politicians = []
    for m in pattern.finditer(content):
        pid = m.group(1)
        # 全角・半角スペースを除去（API は「岸田文雄」形式）
        name = m.group(2).replace("　", "").replace(" ", "")
        politicians.append({"id": pid, "name": name})
    return politicians


def fetch_speech_count(name, from_date, until_date):
    """
    会議録APIを呼び出し、指定期間の発言数を返す。
    成功時: int, エラー時: (None, str)
    """
    params = urllib.parse.urlencode({
        "speaker": name,
        "from": from_date,
        "until": until_date,
        "maximumRecords": 1,
        "recordPacking": "json",
    })
    url = f"{NDL_API}?{params}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "TORAN-DataFetcher/1.0"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return int(data.get("numberOfRecords", 0))
    except Exception as e:
        return None, str(e)


def load_existing(output_path):
    """既存の facts.json を読み込む（中断後の再開用）。"""
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_facts(facts, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)


def log_error(pid, name, reason):
    with open(ERROR_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{pid}\t{name}\t{reason}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full", action="store_true",
        help="全員分を実行（デフォルトは最初の5名のみ）"
    )
    args = parser.parse_args()
    test_mode = not args.full

    politicians = extract_politicians(DATA_JS_PATH)
    print(f"議員数: {len(politicians)} 名  期間: {FROM_DATE}〜{UNTIL_DATE}")

    if test_mode:
        politicians = politicians[:TEST_COUNT]
        print(f"[テストモード] 最初の {TEST_COUNT} 名のみ実行")

    facts = load_existing(OUTPUT_PATH)
    already_done = set(facts.keys())
    if already_done:
        print(f"既存データ: {len(already_done)} 名分（スキップ）")

    period_str = f"{FROM_DATE}〜{UNTIL_DATE}"
    errors = []
    processed = 0

    for i, pol in enumerate(politicians):
        pid, name = pol["id"], pol["name"]

        if pid in already_done:
            continue

        result = fetch_speech_count(name, FROM_DATE, UNTIL_DATE)

        if isinstance(result, tuple):
            _, err_msg = result
            print(f"  [ERROR] {pid} {name}: {err_msg}")
            log_error(pid, name, err_msg)
            errors.append(pid)
            facts[pid] = {
                "name": name, "speech_count": None,
                "period": period_str, "error": err_msg
            }
        else:
            facts[pid] = {
                "name": name, "speech_count": result, "period": period_str
            }
            warn = " ⚠️ 0件（表記ゆれ？）" if result == 0 else ""
            print(f"  {pid} {name}: {result}件{warn}")
            if result == 0:
                log_error(pid, name, "0件（表記ゆれの可能性）")

        processed += 1
        if processed % SAVE_EVERY == 0:
            save_facts(facts, OUTPUT_PATH)
            print(f"  [中間保存] {processed} 名処理済")

        time.sleep(SLEEP_SEC)

    save_facts(facts, OUTPUT_PATH)
    total = len([v for v in facts.values() if v.get("speech_count") is not None])
    print(f"\n完了: {len(facts)} 名分を保存（取得成功: {total} 名）")
    if errors:
        print(f"エラー: {len(errors)} 件 → {ERROR_LOG_PATH} を確認")


if __name__ == "__main__":
    main()
