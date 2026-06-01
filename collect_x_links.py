#!/usr/bin/env python3
"""
統覧 TORAN — Wikipedia Xリンク自動収集スクリプト
==============================================
politicians_base.json の各政治家の Wikipedia ページから
Twitter/X アカウントを自動収集し correction ファイルを生成する。

使い方:
  python3 collect_x_links.py           # 全員スキャン
  python3 collect_x_links.py --dry-run # 書き込まず確認のみ
  python3 collect_x_links.py --resume  # 途中から再開

中断しても --resume で続きから再開できます。
"""

import json, re, time, os, glob, argparse
from urllib.request import urlopen, Request
from urllib.parse import quote
from urllib.error import URLError

BASE_FILE      = 'output/politicians_base.json'
CORRECTIONS_DIR = 'corrections'
PROGRESS_FILE  = 'collect_x_links_progress.json'  # 途中経過保存

def get_next_correction_num():
    files = glob.glob(f'{CORRECTIONS_DIR}/correction_*.json')
    if not files:
        return 1
    nums = [int(m.group(1)) for f in files
            if (m := re.search(r'correction_(\d+)', os.path.basename(f)))]
    return max(nums) + 1 if nums else 1

IGNORE_HANDLES = {
    'intent', 'search', 'hashtag', 'share', 'home',
    'i', 'explore', 'notifications', 'messages', 'privacy', 'tos'
}

def _clean_handle(url: str) -> str | None:
    m = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)', url)
    if m and m.group(1).lower() not in IGNORE_HANDLES:
        return f"https://x.com/{m.group(1)}"
    return None

def fetch_x_from_wiki_url(wiki_url: str) -> str | None:
    """Wikipedia APIで外部リンク＋ウィキテキストを取得しX/Twitterハンドルを返す"""
    try:
        title = wiki_url.split('/wiki/')[-1]
        # extlinks と ウィキテキスト を同時取得
        api_url = (
            'https://ja.wikipedia.org/w/api.php'
            f'?action=query&prop=extlinks%7Crevisions&titles={title}'
            '&format=json&ellimit=100&rvprop=content&rvslots=main'
        )
        req = Request(api_url, headers={'User-Agent': 'TORAN-LinkCollector/1.0'})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))

        pages = data.get('query', {}).get('pages', {})
        for page in pages.values():
            # 1) extlinks から検索
            for link in page.get('extlinks', []):
                url = link.get('*', '')
                if 'twitter.com' in url or 'x.com' in url:
                    h = _clean_handle(url)
                    if h:
                        return h

            # 2) ウィキテキストから {{Twitter|handle}} テンプレートを検索
            wikitext = (page.get('revisions') or [{}])[0]
            wikitext = wikitext.get('slots', {}).get('main', {}).get('*', '') or \
                       wikitext.get('*', '')
            # {{Twitter|handle}} or {{Twitter|handle|...}}
            for m in re.finditer(r'\{\{[Tt]witter\s*\|\s*([A-Za-z0-9_]+)', wikitext):
                handle = m.group(1)
                if handle.lower() not in IGNORE_HANDLES:
                    return f"https://x.com/{handle}"
            # 直接URLが書かれているケース (twitter.com/xxx や x.com/xxx)
            for m in re.finditer(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)', wikitext):
                handle = m.group(1)
                if handle.lower() not in IGNORE_HANDLES:
                    return f"https://x.com/{handle}"

        return None
    except Exception:
        return None

def search_wiki_url(name: str) -> str | None:
    """名前でWikipedia検索してURLを返す"""
    try:
        clean = name.replace(' ', '').replace('　', '')
        api_url = (
            'https://ja.wikipedia.org/w/api.php'
            f'?action=query&list=search&srsearch={quote(clean)}'
            '&format=json&srlimit=1&srnamespace=0'
        )
        req = Request(api_url, headers={'User-Agent': 'TORAN-LinkCollector/1.0'})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        results = data.get('query', {}).get('search', [])
        if results:
            t = results[0]['title']
            return f"https://ja.wikipedia.org/wiki/{quote(t)}"
        return None
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description='WikipediaからXリンクを自動収集')
    parser.add_argument('--dry-run', action='store_true', help='書き込まずに確認のみ')
    parser.add_argument('--resume',  action='store_true', help='途中から再開')
    args = parser.parse_args()

    with open(BASE_FILE, encoding='utf-8') as f:
        politicians = json.load(f)

    # 進捗ロード（--resume時）
    progress = {}
    if args.resume and os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, encoding='utf-8') as f:
            progress = json.load(f)
        print(f'📂 進捗ロード: {len(progress)}名分の結果を引き継ぎ')

    # Xリンクが未設定の議員を対象に
    targets = [
        p for p in politicians
        if not p.get('links', {}).get('tw')
        and p.get('survey') == '評価済'
        and p['id'] not in progress
    ]
    print(f'🎯 対象: {len(targets)}名（評価済でXリンク未設定）')

    found_count = 0
    for i, p in enumerate(targets):
        pid  = p['id']
        name = p['name']
        wiki = (p.get('links') or {}).get('wiki', '')

        print(f'  [{i+1}/{len(targets)}] {pid} {name} ', end='', flush=True)

        # 1) 既存WikiリンクからX取得
        tw = None
        if wiki:
            tw = fetch_x_from_wiki_url(wiki)
            if tw:
                print(f'✅ Wiki→X: {tw}')

        # 2) Wikiリンクがない場合は名前で検索
        if not tw:
            wiki_found = search_wiki_url(name)
            if wiki_found:
                tw = fetch_x_from_wiki_url(wiki_found)
                if tw:
                    print(f'✅ 検索→X: {tw}')
                    wiki = wiki_found  # 発見したWikiURLも保存

        if not tw:
            print('－ 見つからず')

        progress[pid] = {'tw': tw or '', 'wiki': wiki or ''}
        if tw:
            found_count += 1

        # 進捗を随時保存（中断対応）
        if not args.dry_run:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)

        time.sleep(0.3)  # API負荷軽減

    print(f'\n📊 結果: {found_count}名のXリンクを発見 / {len(targets)}名中')

    # Xリンクが見つかった分だけ correction ファイルを生成
    updates = [
        {'id': pid, '_action': 'update', 'links': {'tw': v['tw'], 'wiki': v['wiki'], 'hp': '', 'yt': ''}}
        for pid, v in progress.items()
        if v['tw']
    ]

    if not updates:
        print('✅ 新規Xリンクなし。終了します。')
        return

    if args.dry_run:
        print(f'\n[DRY RUN] {len(updates)}名のlinksCorrectionを生成予定:')
        for u in updates[:10]:
            print(f"  {u['id']}: {u['links']['tw']}")
        return

    num = get_next_correction_num()
    filename = f"{CORRECTIONS_DIR}/correction_{num:03d}_x_links_bulk.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(updates, f, ensure_ascii=False, indent=2)

    print(f'\n✅ 保存: {filename}  ({len(updates)}件)')
    print('次のコマンドでマージしてください:')
    print('  python3 merge_batches.py && python3 generate_js_data.py')

if __name__ == '__main__':
    main()
