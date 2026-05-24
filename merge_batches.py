#!/usr/bin/env python3
"""
統覧 TORAN — バッチマージスクリプト
=====================================
使い方:
  python merge_batches.py

  batches/batch_*.json を読み込み、
  output/politicians_base.json に上書きマージして
  output/politicians_merged.json を出力します。
"""

import json, glob, os
from datetime import date

BASE_FILE   = 'output/politicians_base.json'
BATCHES_DIR = 'batches'
OUT_FILE    = 'output/politicians_merged.json'
DATA_JS     = '../portfolio/data.js'   # HTMLが読み込むファイル（任意）

def main():
    # ── ベースJSONを読み込む ──
    with open(BASE_FILE, encoding='utf-8') as f:
        base_list = json.load(f)

    base_map = {p['id']: p for p in base_list}
    print(f"📂 ベース: {len(base_list)}名")

    # ── バッチを順番に読み込む ──
    batch_files = sorted(glob.glob(f'{BATCHES_DIR}/batch_*.json'))
    if not batch_files:
        print(f"⚠️  {BATCHES_DIR}/ にバッチファイルが見つかりません。")
        return

    merged_count = 0
    evidence_count = 0

    for bf in batch_files:
        with open(bf, encoding='utf-8') as f:
            batch = json.load(f)

        for item in batch:
            pid = item.get('id')
            if pid not in base_map:
                print(f"  ⚠️  {pid} はベースに存在しません → スキップ")
                continue

            p = base_map[pid]

            # スコア・評価フィールドを上書き
            for key in ['total','rank','axes','stances','role',
                        'plus','minus','comment',
                        'flag_crime','flag_caution']:
                if key in item:
                    p[key] = item[key]

            # evidenceを追加（重複しないように）
            existing_summaries = {e.get('summary','') for e in p.get('evidence', [])}
            new_ev = item.get('evidence', [])
            added = 0
            for ev in new_ev:
                # pid を付与
                ev['pid'] = pid
                if ev.get('summary','') not in existing_summaries:
                    p.setdefault('evidence', []).append(ev)
                    existing_summaries.add(ev.get('summary',''))
                    added += 1

            # survey フラグ更新
            if item.get('total', 0) > 0:
                p['survey'] = '評価済'
                p['updated'] = date.today().strftime('%Y.%m')
            elif item.get('rank') == '情報不足':
                p['survey'] = '情報不足'

            merged_count += 1
            evidence_count += added

        print(f"  ✅ {os.path.basename(bf)}: {len(batch)}名マージ")

    # ── 集計 ──
    result = list(base_map.values())

    evaluated   = sum(1 for p in result if p.get('total', 0) > 0)
    info_lack   = sum(1 for p in result if p.get('rank') == '情報不足')
    pending     = sum(1 for p in result if p.get('rank') == '未評価')
    total_ev    = sum(len(p.get('evidence', [])) for p in result)
    crime_flags = sum(1 for p in result if p.get('flag_crime'))
    caution_flags = sum(1 for p in result if p.get('flag_caution'))

    # ── 出力 ──
    os.makedirs('output', exist_ok=True)
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n📄 出力: {OUT_FILE}")

    print(f"\n【現在の進捗】")
    print(f"  評価済:    {evaluated}名 ({evaluated/len(result)*100:.1f}%)")
    print(f"  情報不足:  {info_lack}名")
    print(f"  未評価:    {pending}名")
    print(f"  根拠件数:  {total_ev}件")
    print(f"  🚨犯罪フラグ: {crime_flags}名")
    print(f"  ⚠️ 要注意フラグ: {caution_flags}名")
    print(f"  残りバッチ: あと約{pending//15 + 1}バッチ")

    # ── base を上書き更新 ──
    with open(BASE_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {BASE_FILE} も更新しました")

if __name__ == '__main__':
    main()
