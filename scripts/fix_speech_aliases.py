#!/usr/bin/env python3
"""
表記ゆれ議員の発言数を別名で再取得し facts.json を更新するスクリプト。
旧字体（眞→真、澤→沢など）や通称名のマッピングを使って再検索する。

使い方:
  python3 scripts/fix_speech_aliases.py          # 実行（API呼び出しあり）
  python3 scripts/fix_speech_aliases.py --dry-run # API呼び出しなしで確認のみ
"""

import json, urllib.request, urllib.parse, time, argparse, datetime, os

# ── 別名マッピング（pid: [試行する名前リスト]）──────────────────────
# 旧字体・表記ゆれ
ALIASES = {
    "P010": ["浅田真澄美"],          # 眞→真
    "P109": ["鹿島祐介"],             # 嶋→島
    "P121": ["金沢結衣"],             # 澤→沢
    "P284": ["長沢興祐"],             # 澤→沢
    "P783": ["斎藤元彦", "齊藤元彦"], # 齋→斎/齊（兵庫県知事）
    "P794": ["浜田省司"],             # 濵→浜

    # 通称名（ひらがな・カタカナ）
    "P073": ["内山幸子"],             # 内山こう→戸籍名
    "P076": ["うるま譲司"],           # data.jsはひらがな、NDLでの照合用
    "P165": ["高来啓一郎", "高麗啓一郎"],  # こうらい啓一郎→漢字
    "P802": ["玉城康裕"],             # 玉城デニー→戸籍名
    "P815": ["大石あきこ"],           # data.jsは「大石晃子」、NDLはひらがな表記
    "P817": ["佐藤紗央里"],           # さとうさおり→漢字
}
# ────────────────────────────────────────────────────────────────────

FROM_DATE  = "2021-11-01"
UNTIL_DATE = datetime.date.today().isoformat()
SLEEP_SEC  = 1.0

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS_PATH   = os.path.join(BASE_DIR, "facts.json")
NDL_API      = "https://kokkai.ndl.go.jp/api/speech"


def fetch_count(name):
    params = urllib.parse.urlencode({
        "speaker": name,
        "from": FROM_DATE,
        "until": UNTIL_DATE,
        "maximumRecords": 1,
        "recordPacking": "json",
    })
    req = urllib.request.Request(
        f"{NDL_API}?{params}",
        headers={"User-Agent": "TORAN-AliasRetry/1.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return int(json.loads(resp.read())["numberOfRecords"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="API呼び出しなしで確認のみ")
    args = parser.parse_args()

    with open(FACTS_PATH, encoding="utf-8") as f:
        facts = json.load(f)

    period_str = f"{FROM_DATE}〜{UNTIL_DATE}"
    updated = []

    for pid, names in ALIASES.items():
        orig = facts.get(pid, {})
        orig_count = orig.get("speech_count", 0)
        orig_name  = orig.get("name", pid)
        print(f"\n{pid} {orig_name}（現在: {orig_count}件）")

        if args.dry_run:
            print(f"  [DRY-RUN] 試行予定: {names}")
            continue

        found = False
        for alias in names:
            try:
                count = fetch_count(alias)
                print(f"  → {alias}: {count}件")
                time.sleep(SLEEP_SEC)
                if count > 0:
                    facts[pid]["speech_count"] = count
                    facts[pid]["period"]       = period_str
                    facts[pid]["alias_used"]   = alias
                    updated.append(f"{pid} {orig_name} → {alias}: {count}件")
                    found = True
                    break
            except Exception as e:
                print(f"  ✗ {alias}: エラー ({e})")
                time.sleep(SLEEP_SEC)

        if not found and not args.dry_run:
            print(f"  → 全候補で0件または失敗（そのまま維持）")

    if not args.dry_run:
        with open(FACTS_PATH, "w", encoding="utf-8") as f:
            json.dump(facts, f, ensure_ascii=False, indent=2)
        print(f"\n=== 更新完了 ===")
        for u in updated:
            print(f"  ✅ {u}")
        if not updated:
            print("  更新なし（全候補で0件または確認できず）")


if __name__ == "__main__":
    main()
