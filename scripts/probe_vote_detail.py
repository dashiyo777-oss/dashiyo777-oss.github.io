#!/usr/bin/env python3
"""
参議院 投票結果詳細ページ1件を取得してHTML構造を報告する。
実現可能性調査最終プローブ。
"""

import urllib.request, time, re

UA = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; feasibility study)"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    for enc in ("utf-8", "euc-jp", "shift_jis", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors='replace')

def section(title):
    print(f"\n{'='*60}\n  {title}\n{'='*60}")

# 確定したURL: 防衛省設置法等一部改正（2026-06-26）
TARGET = "https://www.sangiin.go.jp/japanese/touhyoulist/221/221-0626-v001.htm"

section("詳細ページ取得")
print(f"URL: {TARGET}")
html = fetch(TARGET)
time.sleep(3)

print(f"取得成功: {len(html)}文字")

# HTML全文（先頭・後半）
print(f"\n【先頭5000文字】\n{html[:5000]}")
print(f"\n【後半3000文字】\n{html[-3000:]}")

# テーブル構造を抽出
tables = re.findall(r'<table[^>]*>.*?</table>', html, re.DOTALL | re.IGNORECASE)
print(f"\nテーブル数: {len(tables)}")
for i, t in enumerate(tables):
    print(f"\n[テーブル{i+1}] ({len(t)}文字) 先頭800文字:\n{t[:800]}")

# キーワード検索
for kw in ["賛成", "反対", "欠席", "棄権", "議長", "会派", "所属", "君"]:
    hits = re.findall(rf'.{{0,60}}{kw}.{{0,60}}', html)
    if hits:
        print(f"\n[{kw}] {len(hits)}件 例: {hits[:3]}")

# CSSクラス別の要素を抽出
for cls in ["pro", "con", "party", "nam", "ttl"]:
    elems = re.findall(rf'class="{cls}"[^>]*>(.*?)</[^>]+>', html, re.IGNORECASE | re.DOTALL)
    if elems:
        print(f"\n[class={cls}] {len(elems)}件: {[e.strip()[:60] for e in elems[:5]]}")

# <td>と<th>を全て列挙（最初の50件）
cells = re.findall(r'<(?:td|th)[^>]*>(.*?)</(?:td|th)>', html, re.DOTALL | re.IGNORECASE)
print(f"\n全セル数: {len(cells)}")
print("最初の30セル:")
for i, c in enumerate(cells[:30]):
    cleaned = re.sub(r'\s+', ' ', c.strip())[:80]
    print(f"  [{i+1}] {cleaned}")
