#!/usr/bin/env python3
"""
facts.json の前月スナップショット（facts_prev.json）との差分を計算し、
highlights.json を生成する。

使い方:
  python3 scripts/calc_highlights.py            # 本番（facts_prev.json を更新）
  python3 scripts/calc_highlights.py --dry-run  # 差分表示のみ（ファイル更新なし）
"""

import json
import re
import datetime
import argparse
import os

BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACTS_PATH      = os.path.join(BASE_DIR, "facts.json")
PREV_PATH       = os.path.join(BASE_DIR, "facts_prev.json")
HIGHLIGHTS_PATH = os.path.join(BASE_DIR, "highlights.json")
DATA_JS_PATH    = os.path.join(BASE_DIR, "data.js")

# しきい値（差分がこれ未満の議員はランキング対象外）
SPEECH_THRESHOLD   = 5
QUESTION_THRESHOLD = 1
BILL_THRESHOLD     = 1
TOP_N = 3


def extract_politicians(path: str) -> dict:
    """data.js から {pid: {name, party, status}} を返す。"""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(
        r'id:"(P\d+)"[^,]*,\s*name:"([^"]+)"[^,]*,\s*reading:"[^"]*"[^,]*,'
        r'\s*party:"([^"]+)".*?status:"([^"]+)"',
        re.DOTALL,
    )
    result = {}
    for m in pattern.finditer(content):
        result[m.group(1)] = {
            "name":   m.group(2),
            "party":  m.group(3),
            "status": m.group(4),
        }
    return result


def top_n(items: list, threshold: int, n: int) -> list:
    """diff が threshold 以上の items を diff 降順・curr 降順で TOP N に絞る。"""
    filtered = [x for x in items if x["diff"] >= threshold]
    filtered.sort(key=lambda x: (-x["diff"], -x["curr"]))
    return filtered[:n]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run", action="store_true",
        help="ファイルを更新せず標準出力に結果を表示する",
    )
    args = parser.parse_args()

    today = datetime.date.today().strftime("%Y.%m.%d")

    # ── 現在の facts.json を読む ──
    with open(FACTS_PATH, encoding="utf-8") as f:
        curr_facts: dict = json.load(f)

    # ── 前回スナップショットを読む（なければ初回実行） ──
    if os.path.exists(PREV_PATH):
        with open(PREV_PATH, encoding="utf-8") as f:
            prev_data: dict = json.load(f)
        prev_facts   = {k: v for k, v in prev_data.items() if not k.startswith("_")}
        period_from  = prev_data.get("_snapshot_date", "不明")
        first_run    = False
    else:
        prev_facts   = {}
        period_from  = today
        first_run    = True

    if first_run:
        print("初回実行: facts_prev.json が存在しないため first_run モードで生成します")
        result = {
            "generated":    today,
            "period_from":  today,
            "period_to":    today,
            "first_run":    True,
            "no_change":    False,
            "speech_top3":  [],
            "question_top3": [],
            "bill_top3":    [],
        }
    else:
        # ── data.js から現職フィルタ用情報を取得 ──
        politicians = extract_politicians(DATA_JS_PATH)

        speech_items, question_items, bill_items = [], [], []

        for pid, pol in politicians.items():
            if pol["status"] != "現職":
                continue
            curr = curr_facts.get(pid, {})
            prev = prev_facts.get(pid, {})

            def get_diff(key: str):
                c = curr.get(key) or 0
                p = prev.get(key) or 0
                return c - p, c, p

            sd, sc, sp = get_diff("speech_count")
            if sd > 0:
                speech_items.append({
                    "id": pid, "name": pol["name"], "party": pol["party"],
                    "prev": sp, "curr": sc, "diff": sd,
                })

            qd, qc, qp = get_diff("question_count")
            if qd > 0:
                question_items.append({
                    "id": pid, "name": pol["name"], "party": pol["party"],
                    "prev": qp, "curr": qc, "diff": qd,
                })

            bd, bc, bp = get_diff("bill_sponsor_count")
            if bd > 0:
                bill_items.append({
                    "id": pid, "name": pol["name"], "party": pol["party"],
                    "prev": bp, "curr": bc, "diff": bd,
                })

        s_top3 = top_n(speech_items,   SPEECH_THRESHOLD,   TOP_N)
        q_top3 = top_n(question_items, QUESTION_THRESHOLD, TOP_N)
        b_top3 = top_n(bill_items,     BILL_THRESHOLD,     TOP_N)
        no_change = not (s_top3 or q_top3 or b_top3)

        result = {
            "generated":    today,
            "period_from":  period_from,
            "period_to":    today,
            "first_run":    False,
            "no_change":    no_change,
            "speech_top3":  s_top3,
            "question_top3": q_top3,
            "bill_top3":    b_top3,
        }

    output = json.dumps(result, ensure_ascii=False, indent=2)
    print(output)

    if args.dry_run:
        print("\n[dry-run] ファイルは更新しません")
        return

    # ── highlights.json を保存 ──
    with open(HIGHLIGHTS_PATH, "w", encoding="utf-8") as f:
        f.write(output + "\n")
    print(f"\nhighlights.json を保存しました")

    # ── facts_prev.json を更新（月次実行のみ。手動 dry-run では更新しない） ──
    snapshot = dict(curr_facts)
    snapshot["_snapshot_date"] = today
    with open(PREV_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"facts_prev.json を更新しました（スナップショット日: {today}）")


if __name__ == "__main__":
    main()
