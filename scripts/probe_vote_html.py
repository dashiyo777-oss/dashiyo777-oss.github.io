#!/usr/bin/env python3
"""
参議院・衆議院の投票記録ページのHTML構造を調査するプローブスクリプト。
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


# ── robots.txt ──────────────────────────────────────────────────
section("1. robots.txt 確認")

for label, url in [
    ("参議院", "https://www.sangiin.go.jp/robots.txt"),
    ("衆議院", "https://www.shugiin.go.jp/robots.txt"),
]:
    print(f"\n[{label}] {url}")
    html = fetch(url)
    print(html[:800] if not html.startswith("ERROR") else html)
    time.sleep(SLEEP)


# ── 参議院 投票結果一覧ページ ────────────────────────────────────
section("2. 参議院 投票結果一覧（第221回・第207回）")

for session in [221, 217, 207]:
    url = f"https://www.sangiin.go.jp/japanese/joho1/kousei/vote/{session}/vote.htm"
    print(f"\n[第{session}回] {url}")
    html = fetch(url)
    if html.startswith("ERROR"):
        print(html)
        time.sleep(SLEEP)
        continue
    print(f"  取得成功: {len(html)}文字")
    # 議案へのリンクを探す
    links = re.findall(r'href="([^"]*vote[^"]*)"', html, re.IGNORECASE)
    links += re.findall(r'href="([^"]*\d{4,}[^"]*\.htm)"', html, re.IGNORECASE)
    links = list(dict.fromkeys(links))[:10]  # 重複除去・上位10件
    print(f"  リンク候補（上位10件）: {links}")
    # ページ全体の一部を表示（構造確認）
    print(f"  HTML先頭800文字:\n{html[:800]}")
    time.sleep(SLEEP)


# ── 参議院 個別投票結果ページ（サンプル取得） ───────────────────
section("3. 参議院 投票結果一覧（第221回）詳細")

url_221 = "https://www.sangiin.go.jp/japanese/joho1/kousei/vote/221/vote.htm"
html_221 = fetch(url_221)
time.sleep(SLEEP)

if not html_221.startswith("ERROR"):
    # 個別議案ページのURL形式を探す
    detail_links = re.findall(r'href="([^"]+\.htm)"', html_221, re.IGNORECASE)
    detail_links = [l for l in detail_links if 'vote' in l.lower() or re.search(r'\d{3,}', l)]
    detail_links = list(dict.fromkeys(detail_links))
    print(f"  議案詳細リンク候補: {detail_links[:15]}")

    # 最初の詳細リンクを取得
    if detail_links:
        first = detail_links[0]
        if not first.startswith("http"):
            first = "https://www.sangiin.go.jp" + (first if first.startswith("/") else f"/japanese/joho1/kousei/vote/221/{first}")
        print(f"\n  サンプル詳細ページ取得: {first}")
        detail_html = fetch(first)
        time.sleep(SLEEP)
        if not detail_html.startswith("ERROR"):
            print(f"  取得成功: {len(detail_html)}文字")
            print(f"  HTML先頭2000文字:\n{detail_html[:2000]}")
            # 議員名と賛否を探す
            yeas = re.findall(r'賛成[^<]*<[^>]*>([^<]+)<', detail_html)
            nays = re.findall(r'反対[^<]*<[^>]*>([^<]+)<', detail_html)
            print(f"  賛成ヒット例: {yeas[:5]}")
            print(f"  反対ヒット例: {nays[:5]}")
            # テーブル構造
            tables = re.findall(r'<table[^>]*>.*?</table>', detail_html, re.DOTALL|re.IGNORECASE)
            print(f"  テーブル数: {len(tables)}")
            if tables:
                print(f"  最初のテーブル先頭500文字:\n{tables[0][:500]}")
        else:
            print(f"  {detail_html}")
else:
    print(f"  一覧取得失敗: {html_221}")


# ── 衆議院 本会議議決・投票情報 ─────────────────────────────────
section("4. 衆議院 議案データベース（第221回）")

shugiin_urls = [
    ("議案一覧", "https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/kaiji221.htm"),
    ("投票DB", "https://www.shugiin.go.jp/internet/itdb_vote.nsf/html/vote/"),
    ("本会議議決", "https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/honkaigi221.htm"),
]

for label, url in shugiin_urls:
    print(f"\n[衆議院 {label}] {url}")
    html = fetch(url, encoding="shift_jis")
    if html.startswith("ERROR"):
        print(f"  {html}")
    else:
        print(f"  取得成功: {len(html)}文字")
        print(f"  HTML先頭1000文字:\n{html[:1000]}")
        # 投票・賛否関連リンクを探す
        vote_links = re.findall(r'href="([^"]*(?:vote|賛否|投票)[^"]*)"', html, re.IGNORECASE)
        print(f"  投票関連リンク: {vote_links[:10]}")
    time.sleep(SLEEP)


# ── 参議院 件数カウント（第207〜221回） ─────────────────────────
section("5. 参議院 押しボタン投票 件数見積もり")

total_count = 0
for session in range(207, 222):
    url = f"https://www.sangiin.go.jp/japanese/joho1/kousei/vote/{session}/vote.htm"
    html = fetch(url)
    if html.startswith("ERROR"):
        print(f"  第{session}回: 取得失敗 ({html})")
    else:
        # リンク数で議案数を概算
        links = re.findall(r'href="[^"]+\.htm"', html, re.IGNORECASE)
        # 一覧ページ自体のナビリンクを除く（投票結果ページへのリンクのみカウント）
        vote_links = [l for l in links if re.search(r'\d{3,}', l)]
        count = len(set(vote_links))
        total_count += count
        print(f"  第{session}回: 議案リンク約{count}件")
    time.sleep(2)

print(f"\n  合計（第207〜221回）: 約{total_count}件")
print(f"  ※ 参議院議員数 約248名として全件格納: {total_count * 248}レコード")
print(f"  ※ 1レコード = 議員ID+賛否1文字 として約{total_count * 248 * 20 // 1024}KB")
