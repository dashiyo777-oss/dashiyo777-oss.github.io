#!/usr/bin/env python3
"""
参議院投票記録プローブ第3回: vote_ind.htmの全リンクと詳細1件取得。
"""

import urllib.request, time, re

UA = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; feasibility study)"
SLEEP = 3.0

def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        for enc in ("utf-8", "euc-jp", "shift_jis", "cp932"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors='replace')
    except Exception as e:
        return f"ERROR: {e}"

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")


# ── 1. vote_ind.htm の全 href と テーブル行の確認 ───────────────
section("1. 第221回 vote_ind.htm 詳細解析")

url_ind = "https://www.sangiin.go.jp/japanese/touhyoulist/221/vote_ind.htm"
html = fetch(url_ind)
time.sleep(SLEEP)

if html.startswith("ERROR"):
    print(f"  取得失敗: {html}")
else:
    print(f"  取得成功: {len(html)}文字")

    # 全 href を無条件に列挙
    all_hrefs = re.findall(r'href="([^"]+)"', html)
    # ナビ・CSS等を除く（/common/, /japanese/joho, /cgi-bin, #, javascript: 以外）
    candidate_hrefs = [h for h in all_hrefs if not any(x in h for x in
        ['/common/', '/cgi-bin/', '/japanese/joho', '/japanese/sitemap',
         '/japanese/link', '/japanese/aramashi', '/japanese/taiken',
         '/japanese/kids', '/japanese/annai', '/japanese/kokusai',
         '/japanese/kon_', '/japanese/kaiki', 'webtv', '.css', '.js',
         '#', 'search.cgi', 'http://'])]
    print(f"\n  ナビ除外後のリンク ({len(candidate_hrefs)}件):")
    for h in candidate_hrefs:
        print(f"    {h}")

    # onclick 属性も確認
    onclicks = re.findall(r'onclick="([^"]+)"', html)
    print(f"\n  onclick属性 ({len(onclicks)}件, 先頭10件): {onclicks[:10]}")

    # テーブルの実際の行内容（最初の15行）
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
    print(f"\n  <tr>行数: {len(rows)}")
    print(f"\n  最初の15行の内容（タグ込み）:")
    for i, row in enumerate(rows[:15]):
        # 前後の空白を除いてコンパクトに表示
        cleaned = re.sub(r'\s+', ' ', row.strip())[:300]
        print(f"  [行{i+1}] {cleaned}")

    # <a>タグ付きのテキストを全て抽出
    a_tags = re.findall(r'<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE)
    print(f"\n  <a>タグ一覧 ({len(a_tags)}件):")
    for href, text in a_tags:
        clean_text = re.sub(r'\s+', ' ', text.strip())[:60]
        print(f"    href='{href}' text='{clean_text}'")


# ── 2. 詳細ページ1件 ────────────────────────────────────────────
section("2. 詳細ページ1件取得")

# 候補リンクから詳細ページURLを組み立て
detail_url = None
if not html.startswith("ERROR"):
    # vote_ind.htm と同じディレクトリのリンクを探す
    local_links = [h for h in re.findall(r'href="([^"]+)"', html)
                   if not h.startswith('/') and not h.startswith('http')
                   and not h.startswith('#') and '.' in h]
    print(f"  ローカル相対リンク: {local_links[:20]}")

    # また、数字を含むものも探す（幅広く）
    num_links = [h for h in re.findall(r'href="([^"]+)"', html)
                 if re.search(r'\d', h) and 'vote' not in h.lower()
                 or 'vote' in h.lower()]
    print(f"  数字or'vote'含むリンク: {num_links[:20]}")

    if local_links:
        first = local_links[0]
        base = "https://www.sangiin.go.jp/japanese/touhyoulist/221/"
        detail_url = base + first.lstrip("./")
    elif num_links:
        first = num_links[0]
        if not first.startswith("http"):
            detail_url = "https://www.sangiin.go.jp" + (first if first.startswith("/") else "/japanese/touhyoulist/221/" + first)
        else:
            detail_url = first

# フォールバック: よくある命名パターン
if not detail_url:
    candidates = [
        "https://www.sangiin.go.jp/japanese/touhyoulist/221/vote001.htm",
        "https://www.sangiin.go.jp/japanese/touhyoulist/221/vote_001.htm",
        "https://www.sangiin.go.jp/japanese/touhyoulist/221/touhyou001.htm",
        "https://www.sangiin.go.jp/japanese/touhyoulist/221/1.htm",
    ]
    for c in candidates:
        print(f"  フォールバック試行: {c}")
        test = fetch(c)
        time.sleep(SLEEP)
        if not test.startswith("ERROR"):
            detail_url = c
            html_detail = test
            print(f"  → 取得成功: {len(test)}文字")
            break
        else:
            print(f"  → {test}")

if detail_url and not html.startswith("ERROR"):
    if 'html_detail' not in dir():
        print(f"\n  取得URL: {detail_url}")
        html_detail = fetch(detail_url)
        time.sleep(SLEEP)

    if not html_detail.startswith("ERROR"):
        print(f"  取得成功: {len(html_detail)}文字")
        print(f"\n  【先頭4000文字】\n{html_detail[:4000]}")
        print(f"\n  【後半2000文字】\n{html_detail[-2000:]}")

        # 賛成・反対・欠席・棄権・議長・会派 のコンテキスト
        for kw in ["賛成", "反対", "欠席", "棄権", "議長", "会派", "所属", "pro", "con", "party", "nam"]:
            hits = re.findall(rf'.{{0,80}}{kw}.{{0,80}}', html_detail, re.IGNORECASE)
            if hits:
                print(f"\n  [{kw}] {len(hits)}件: {hits[:3]}")
    else:
        print(f"  取得失敗: {html_detail}")
else:
    print("  詳細ページURLを特定できなかった")
