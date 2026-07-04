#!/usr/bin/env python3
"""
参議院 投票記録ページ（touhyoulist.html）第2回プローブ。
実現可能性調査用。本番実装には使わない。
"""

import urllib.request, time, re

UA = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; feasibility study)"
SLEEP = 3.0

def fetch(url, encoding=None):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
        if encoding:
            return raw.decode(encoding, errors='replace')
        for enc in ("utf-8", "euc-jp", "shift_jis", "cp932"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors='replace')
    except Exception as e:
        return f"ERROR: {e}"

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)


# ── 1. ルート一覧ページ ──────────────────────────────────────────
section("1. 参議院 touhyoulist.html ルート一覧")

root_url = "https://www.sangiin.go.jp/japanese/touhyoulist/touhyoulist.html"
print(f"URL: {root_url}")
root_html = fetch(root_url)
time.sleep(SLEEP)

if root_html.startswith("ERROR"):
    print(f"  取得失敗: {root_html}")
else:
    print(f"  取得成功: {len(root_html)}文字")
    print(f"  HTML先頭2000文字:\n{root_html[:2000]}")
    # 回次（第221回など）へのリンクを探す
    session_links = re.findall(r'href="([^"]+)"[^>]*>[^<]*(?:第\d+回|221|220|219)', root_html, re.IGNORECASE)
    session_links2 = re.findall(r'href="([^"]*(?:221|220|touhyou)[^"]*)"', root_html, re.IGNORECASE)
    all_links = list(dict.fromkeys(session_links + session_links2))
    print(f"\n  回次関連リンク候補: {all_links[:20]}")
    # 全hrefを表示（構造把握のため）
    all_hrefs = re.findall(r'href="([^"]+)"', root_html)
    print(f"\n  全href ({len(all_hrefs)}件, 先頭30件): {all_hrefs[:30]}")


# ── 2. 第221回の一覧ページ ───────────────────────────────────────
section("2. 第221回 投票結果一覧")

# root から 221 へのリンクを解決
if not root_html.startswith("ERROR"):
    # 221 を含む href を探す
    links_221 = [l for l in re.findall(r'href="([^"]+)"', root_html) if '221' in l]
    print(f"  221関連href: {links_221}")

    if links_221:
        first = links_221[0]
        if not first.startswith("http"):
            base = "https://www.sangiin.go.jp"
            if first.startswith("/"):
                url_221 = base + first
            else:
                url_221 = "https://www.sangiin.go.jp/japanese/touhyoulist/" + first
        else:
            url_221 = first
    else:
        # フォールバック: よくあるパターンを試す
        url_221 = "https://www.sangiin.go.jp/japanese/touhyoulist/221/touhyoulist221.html"
        print(f"  リンク未検出。フォールバックURL試行: {url_221}")
else:
    url_221 = "https://www.sangiin.go.jp/japanese/touhyoulist/221/touhyoulist221.html"
    print(f"  ルート取得失敗のためフォールバックURL試行: {url_221}")

print(f"\n[第221回一覧] {url_221}")
html_221 = fetch(url_221)
time.sleep(SLEEP)

if html_221.startswith("ERROR"):
    print(f"  取得失敗: {html_221}")
    # 別パターンを試す
    alt_urls = [
        "https://www.sangiin.go.jp/japanese/touhyoulist/touhyoulist221.html",
        "https://www.sangiin.go.jp/japanese/joho1/kousei/vote/221/touhyoulist.html",
        "https://www.sangiin.go.jp/japanese/touhyoulist/221/vote.htm",
    ]
    for alt in alt_urls:
        print(f"  別パターン試行: {alt}")
        alt_html = fetch(alt)
        time.sleep(SLEEP)
        if not alt_html.startswith("ERROR"):
            print(f"  → 取得成功: {len(alt_html)}文字")
            html_221 = alt_html
            url_221 = alt
            break
        else:
            print(f"  → {alt_html}")
else:
    print(f"  取得成功: {len(html_221)}文字")
    print(f"  HTML先頭2000文字:\n{html_221[:2000]}")

    # 投票件数をカウント
    detail_links = re.findall(r'href="([^"]+)"', html_221)
    vote_detail_links = [l for l in detail_links if re.search(r'\d{3,}', l) or 'vote' in l.lower() or 'touhyou' in l.lower()]
    vote_detail_links = list(dict.fromkeys(vote_detail_links))
    print(f"\n  投票詳細リンク候補 ({len(vote_detail_links)}件): {vote_detail_links[:20]}")
    # テーブル行数で件数推定
    rows = re.findall(r'<tr[^>]*>', html_221, re.IGNORECASE)
    print(f"  <tr>タグ数: {len(rows)} (概算)")
    # 法案名・議案名らしきテキストを抽出
    bills = re.findall(r'[第一二三四五六七八九〇百千万を改正する法律案][^\n<]{2,50}', html_221)
    print(f"  法案名サンプル: {bills[:10]}")


# ── 3. 詳細ページ1件 ────────────────────────────────────────────
section("3. 投票結果詳細ページ（1件サンプル）")

detail_url = None

if not html_221.startswith("ERROR"):
    hrefs = re.findall(r'href="([^"]+)"', html_221)
    # 詳細ページへのリンクを探す（数字IDを含むもの）
    candidates = [l for l in hrefs if re.search(r'\d{3,}', l) and '.htm' in l.lower()]
    candidates = list(dict.fromkeys(candidates))
    print(f"  詳細候補リンク: {candidates[:10]}")
    if candidates:
        first_link = candidates[0]
        if not first_link.startswith("http"):
            base_dir = url_221.rsplit("/", 1)[0]
            detail_url = base_dir + "/" + first_link.lstrip("/")
        else:
            detail_url = first_link
else:
    print("  一覧取得失敗のため詳細ページ取得をスキップ")

if detail_url:
    print(f"\n  取得URL: {detail_url}")
    detail_html = fetch(detail_url)
    time.sleep(SLEEP)

    if detail_html.startswith("ERROR"):
        print(f"  取得失敗: {detail_html}")
    else:
        print(f"  取得成功: {len(detail_html)}文字")
        print(f"\n  【HTML全文（先頭5000文字）】")
        print(detail_html[:5000])
        print(f"\n  【後半2000文字】")
        print(detail_html[-2000:])

        # テーブル構造を抽出
        tables = re.findall(r'<table[^>]*>.*?</table>', detail_html, re.DOTALL | re.IGNORECASE)
        print(f"\n  テーブル数: {len(tables)}")
        for i, t in enumerate(tables[:3]):
            print(f"\n  [テーブル{i+1}] 先頭1000文字:\n{t[:1000]}")

        # 賛成・反対・欠席・棄権・議長 キーワード検索
        for kw in ["賛成", "反対", "欠席", "棄権", "議長", "会派", "所属"]:
            count = detail_html.count(kw)
            ctx = re.findall(rf'.{{0,50}}{kw}.{{0,50}}', detail_html)
            print(f"\n  [{kw}] {count}件: {ctx[:3]}")
