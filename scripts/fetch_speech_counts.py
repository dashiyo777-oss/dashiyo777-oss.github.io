#!/usr/bin/env python3
"""
国会会議録APIから議員の発言数を取得し facts.json に保存するスクリプト。
API仕様: https://kokkai.ndl.go.jp/api/speech
"""

import re
import json
import time
import urllib.request
import urllib.parse
import os

# ── 設定 ──────────────────────────────────────
FROM_DATE = "2021-11-01"   # 第49回衆院選後の臨時国会開始
UNTIL_DATE = "2026-06-30"
SLEEP_SEC = 1.0            # リクエスト間隔（サーバー負荷対策）
SAVE_EVERY = 10            # 何名ごとに中間保存するか
TEST_MODE = True           # True=最初の5名のみ / False=全員
# ─────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS_PATH = os.path.join(BASE_DIR, "data.js")
OUTPUT_PATH = os.path.join(BASE_DIR, "facts.json")
ERROR_LOG_PATH = os.path.join(BASE_DIR, "error_log.txt")


def extract_politicians(data_js_path):
    """data.js から id と name を抽出して返す。"""
    with open(data_js_path, encoding="utf-8") as f:
        content = f.read()

    # id:"P001", name:"逢沢 一郎" のペアを抽出
    pattern = re.compile(r'id:"(P\d+)"[^}]*?name:"([^"]+)"')
    politicians = []
    for m in pattern.finditer(content):
        pid = m.group(1)
        name = m.group(2).replace("　", "").replace(" ", "")  # 全角・半角スペース除去
        politicians.append({"id": pid, "name": name})
    return politicians


def fetch_speech_count(name, from_date, until_date):
    """
    会議録APIを呼び出し、指定期間の発言数を返す。
    エラー時は None を返す。
    """
    params = urllib.parse.urlencode({
        "speaker": name,
        "from": from_date,
        "until": until_date,
        "maximumRecords": 1,
        "recordPacking": "json",
    })
    url = f"https://kokkai.ndl.go.jp/api/speech?{params}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TORAN-DataFetcher/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        count = data.get("numberOfRecords", 0)
        return int(count)
    except Exception as e:
        return None, str(e)


def load_existing(output_path):
    """既存の facts.json を読み込む（再開用）。"""
    if os.path.exists(output_path):
        with open(output_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_facts(facts, output_path):
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)


def log_error(pid, name, reason, error_log_path):
    with open(error_log_path, "a", encoding="utf-8") as f:
        f.write(f"{pid}\t{name}\t{reason}\n")


def main():
    politicians = extract_politicians(DATA_JS_PATH)
    print(f"議員数: {len(politicians)} 名")

    if TEST_MODE:
        politicians = politicians[:5]
        print(f"[テストモード] 最初の {len(politicians)} 名のみ実行")

    facts = load_existing(OUTPUT_PATH)
    already_done = set(facts.keys())
    print(f"既存データ: {len(already_done)} 名分")

    period_str = f"{FROM_DATE}〜{UNTIL_DATE}"
    errors = []

    for i, pol in enumerate(politicians):
        pid = pol["id"]
        name = pol["name"]

        if pid in already_done:
            print(f"  スキップ（取得済）: {pid} {name}")
            continue

        result = fetch_speech_count(name, FROM_DATE, UNTIL_DATE)

        if isinstance(result, tuple):
            # エラー
            _, err_msg = result
            print(f"  [ERROR] {pid} {name}: {err_msg}")
            log_error(pid, name, err_msg, ERROR_LOG_PATH)
            errors.append(pid)
            facts[pid] = {"name": name, "speech_count": None, "period": period_str, "error": err_msg}
        else:
            count = result
            facts[pid] = {"name": name, "speech_count": count, "period": period_str}
            status = f"{count}件" if count > 0 else "0件 ⚠️"
            print(f"  {pid} {name}: {status}")
            if count == 0:
                log_error(pid, name, "0件（表記ゆれの可能性）", ERROR_LOG_PATH)

        # 中間保存
        if (i + 1) % SAVE_EVERY == 0:
            save_facts(facts, OUTPUT_PATH)
            print(f"  [保存] {i + 1} 名処理済")

        time.sleep(SLEEP_SEC)

    # 最終保存
    save_facts(facts, OUTPUT_PATH)
    print(f"\n完了: {len(facts)} 名分を {OUTPUT_PATH} に保存")
    if errors:
        print(f"エラー: {len(errors)} 件 → {ERROR_LOG_PATH} を確認してください")


if __name__ == "__main__":
    main()
