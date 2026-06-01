#!/usr/bin/env python3
"""
統覧 TORAN — Xリンク管理スクリプト
=====================================
使い方:

  # Xリンク未設定の議員をCSVに出力（Googleスプレッドシートに貼り付け用）
  python manage_links.py --export

  # Googleスプレッドシートから保存したCSVを読み込んでcorrectionを生成
  python manage_links.py --import missing_x_links.csv

CSVの形式:
  pid, name, party, district, status, wiki_url, tw
  tw列に https://x.com/handle または @handle を入力してください。
"""

import json, csv, glob, re, os, argparse, sys
from datetime import date

BASE_FILE       = 'output/politicians_base.json'
CORRECTIONS_DIR = 'corrections'
EXPORT_FILE     = 'missing_x_links.csv'

def get_next_correction_num():
    files = glob.glob(f'{CORRECTIONS_DIR}/correction_*.json')
    if not files:
        return 1
    nums = [int(m.group(1)) for f in files
            if (m := re.search(r'correction_(\d+)', os.path.basename(f)))]
    return max(nums) + 1 if nums else 1

def normalize_tw(value: str) -> str:
    """@handle または x.com/handle → https://x.com/handle に正規化"""
    v = value.strip()
    if not v:
        return ''
    # すでにURL形式
    if v.startswith('http'):
        m = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)', v)
        return f"https://x.com/{m.group(1)}" if m else ''
    # @handle 形式
    if v.startswith('@'):
        return f"https://x.com/{v[1:]}"
    # handle のみ
    if re.match(r'^[A-Za-z0-9_]+$', v):
        return f"https://x.com/{v}"
    return ''

def cmd_export():
    with open(BASE_FILE, encoding='utf-8') as f:
        politicians = json.load(f)

    # Xリンク未設定・評価済の議員
    targets = [
        p for p in politicians
        if not (p.get('links') or {}).get('tw')
        and p.get('survey') == '評価済'
    ]
    print(f'📋 Xリンク未設定: {len(targets)}名')

    with open(EXPORT_FILE, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['pid', 'name', 'party', 'district', 'status', 'wiki_url', 'tw'])
        for p in targets:
            writer.writerow([
                p['id'],
                p['name'],
                p.get('party', ''),
                p.get('district', ''),
                p.get('status', ''),
                (p.get('links') or {}).get('wiki', ''),
                '',  # ← ここにXアカウントを入力
            ])

    print(f'✅ 保存: {EXPORT_FILE}')
    print('次のステップ:')
    print('  1. Googleスプレッドシートにインポート')
    print('  2. tw列に https://x.com/handle を入力')
    print('  3. CSVとしてダウンロード')
    print(f'  4. python manage_links.py --import {EXPORT_FILE}')

def cmd_import(csv_file: str):
    if not os.path.exists(csv_file):
        print(f'❌ ファイルが見つかりません: {csv_file}')
        sys.exit(1)

    updates = []
    skipped = 0
    with open(csv_file, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tw_raw = row.get('tw', '').strip()
            if not tw_raw:
                skipped += 1
                continue
            tw = normalize_tw(tw_raw)
            if not tw:
                print(f"  ⚠️  {row['pid']} {row['name']}: 無効な形式「{tw_raw}」→ スキップ")
                skipped += 1
                continue
            wiki = row.get('wiki_url', '').strip()
            updates.append({
                'id': row['pid'],
                '_action': 'update',
                'links': {'tw': tw, 'hp': '', 'yt': '', 'wiki': wiki}
            })
            print(f"  ✅ {row['pid']} {row['name']}: {tw}")

    print(f'\n📊 {len(updates)}件のリンクを取得 / {skipped}件スキップ')

    if not updates:
        print('新規データなし。終了します。')
        return

    num = get_next_correction_num()
    filename = f"{CORRECTIONS_DIR}/correction_{num:03d}_x_links_manual.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(updates, f, ensure_ascii=False, indent=2)

    print(f'\n✅ 保存: {filename}')
    print('次のコマンドでサイトに反映してください:')
    print('  python merge_batches.py && python generate_js_data.py')
    print('  git add -A && git commit -m "update: Xリンク手動追加" && git push')

def main():
    parser = argparse.ArgumentParser(description='Xリンク管理')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--export', action='store_true', help='未設定リストをCSV出力')
    group.add_argument('--import', dest='import_file', metavar='CSV', help='CSVからcorrectionを生成')
    args = parser.parse_args()

    if args.export:
        cmd_export()
    else:
        cmd_import(args.import_file)

if __name__ == '__main__':
    main()
