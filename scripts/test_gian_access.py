#!/usr/bin/env python3
"""
GitHub Actions 上での公式サイトアクセス可否テスト。
衆議院・参議院の議員立法（衆法・参法）ページの取得とHTML構造を確認する。
実装用スクリプトではなく、調査専用。
"""

import re
import sys
import time
import urllib.request
import urllib.error
import os

UA = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; public data research)"
SLEEP = 3.5
SUMMARY = os.environ.get("GITHUB_STEP_SUMMARY", "")


def out(text=""):
    print(text)
    if SUMMARY:
        with open(SUMMARY, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def fetch(url, encoding=None):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            status = resp.status
        if encoding:
            return status, len(raw), raw.decode(encoding, errors="replace")
        for enc in ("utf-8", "euc-jp", "shift_jis", "cp932"):
            try:
                return status, len(raw), raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return status, len(raw), raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, 0, f"HTTPError: {e}"
    except Exception as e:
        return None, 0, f"Error: {e}"


def section(title):
    out(f"\n## {title}")


def subsection(title):
    out(f"\n### {title}")


# ──────────────────────────────────────────────
# 1. 衆議院 議案一覧 kaiji221.htm
# ──────────────────────────────────────────────
section("1. 衆議院 議案一覧（kaiji221.htm）")

SHUGIIN_KAIJI = "https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/kaiji221.htm"
out(f"URL: `{SHUGIIN_KAIJI}`")
status, size, html = fetch(SHUGIIN_KAIJI, encoding="shift_jis")
out(f"HTTP status: **{status}** / サイズ: {size:,} bytes")

shu_keika_url = None

if status == 200 and html:
    out("✅ **取得成功**")

    # 衆法行を検索
    rows_with_shuho = [l.strip() for l in html.split('\n') if '衆法' in l]
    out(f"\n`衆法` を含む行数: {len(rows_with_shuho)}")
    if rows_with_shuho:
        out("\nサンプル行（最初の3件）:")
        out("```")
        for r in rows_with_shuho[:3]:
            out(r[:300])
        out("```")

    # 個別議案（経過）ページへのリンクを探す
    keika_links = re.findall(
        r'href="(/internet/itdb_gian\.nsf/html/gian/keika/[^"]+\.htm)"',
        html, re.IGNORECASE
    )
    out(f"\n経過ページリンク数（keika/）: {len(keika_links)}")
    if keika_links:
        out(f"最初の5件: {keika_links[:5]}")
        shu_keika_url = "https://www.shugiin.go.jp" + keika_links[0]

    # テーブルヘッダー行
    th_rows = [l.strip() for l in html.split('\n') if '<th' in l.lower()]
    out(f"\nテーブルヘッダー行数: {len(th_rows)}")
    if th_rows:
        out("ヘッダー行サンプル（最初の3件）:")
        out("```")
        for r in th_rows[:3]:
            out(r[:300])
        out("```")

    out("\nHTMLの先頭500文字:")
    out("```html")
    out(html[:500])
    out("```")
else:
    out(f"❌ **取得失敗**: {html[:200]}")

time.sleep(SLEEP)

# ──────────────────────────────────────────────
# 2. 衆法 個別経過ページ（1件）
# ──────────────────────────────────────────────
section("2. 衆法 個別経過ページ（サンプル1件）")

if not shu_keika_url:
    shu_keika_url = "https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/keika/1DDBAEB.htm"
    out("（kaiji221.htmからリンク取得できなかったため代替URLを使用）")

out(f"URL: `{shu_keika_url}`")
status2, size2, html2 = fetch(shu_keika_url)
out(f"HTTP status: **{status2}** / サイズ: {size2:,} bytes")

if status2 == 200 and html2:
    out("✅ **取得成功**")

    # 提出者・賛成者フィールドを探す
    keywords = ["提出者", "発議者", "賛成者", "起草者", "提案者"]
    out("\n提出者/賛成者関連キーワードを含む行:")
    out("```")
    found_kw = []
    for kw in keywords:
        matches = [l.strip() for l in html2.split('\n') if kw in l]
        if matches:
            found_kw.append(kw)
            out(f"[{kw}]:")
            for m in matches[:3]:
                out(f"  {m[:250]}")
    if not found_kw:
        out("（キーワード該当行なし）")
    out("```")

    # 議員名「君」を含む行
    kimi_rows = [l.strip() for l in html2.split('\n') if '君' in l and '<' in l]
    out(f"\n「君」を含むHTML行数: {len(kimi_rows)}")
    if kimi_rows:
        out("サンプル（最初の5件）:")
        out("```")
        for r in kimi_rows[:5]:
            out(r[:300])
        out("```")

    out("\nHTMLの先頭800文字:")
    out("```html")
    out(html2[:800])
    out("```")
    out("\nHTMLの末尾300文字:")
    out("```html")
    out(html2[-300:])
    out("```")
else:
    out(f"❌ **取得失敗**: {html2[:200]}")

time.sleep(SLEEP)

# ──────────────────────────────────────────────
# 3. 参議院 議案一覧
# ──────────────────────────────────────────────
section("3. 参議院 議案一覧（第221回）")

SANGIIN_KAIJI = "https://www.sangiin.go.jp/japanese/joho1/kousei/gian/221/gian.htm"
out(f"URL: `{SANGIIN_KAIJI}`")
status3, size3, html3 = fetch(SANGIIN_KAIJI)
out(f"HTTP status: **{status3}** / サイズ: {size3:,} bytes")

san_meisai_url = None

if status3 == 200 and html3:
    out("✅ **取得成功**")

    rows_sanho = [l.strip() for l in html3.split('\n') if '参法' in l or '議員発議' in l]
    out(f"\n`参法`/`議員発議` を含む行数: {len(rows_sanho)}")
    if rows_sanho:
        out("\nサンプル行（最初の3件）:")
        out("```")
        for r in rows_sanho[:3]:
            out(r[:300])
        out("```")

    meisai_links = re.findall(
        r'href="([^"]*meisai[^"]*\.htm)"',
        html3, re.IGNORECASE
    )
    out(f"\n明細ページリンク数（meisai）: {len(meisai_links)}")
    if meisai_links:
        out(f"最初の5件: {meisai_links[:5]}")
        link = meisai_links[0]
        san_meisai_url = ("https://www.sangiin.go.jp" + link) if link.startswith('/') else link

    out("\nHTMLの先頭600文字:")
    out("```html")
    out(html3[:600])
    out("```")
else:
    out(f"❌ **取得失敗**: {html3[:200]}")

time.sleep(SLEEP)

# ──────────────────────────────────────────────
# 4. 参法 個別ページ（サンプル1件）
# ──────────────────────────────────────────────
section("4. 参法 個別ページ（サンプル1件）")

if not san_meisai_url:
    san_meisai_url = "https://www.sangiin.go.jp/japanese/joho1/kousei/gian/221/meisai/m22103221001.htm"
    out("（議案一覧からリンク取得できなかったため標準URLパターンを試行）")

out(f"URL: `{san_meisai_url}`")
status4, size4, html4 = fetch(san_meisai_url)
out(f"HTTP status: **{status4}** / サイズ: {size4:,} bytes")

if status4 == 200 and html4:
    out("✅ **取得成功**")

    keywords4 = ["発議者", "提出者", "賛成者", "議員発議", "提案者"]
    out("\n発議者関連キーワードを含む行:")
    out("```")
    for kw in keywords4:
        matches = [l.strip() for l in html4.split('\n') if kw in l]
        if matches:
            out(f"[{kw}]:")
            for m in matches[:3]:
                out(f"  {m[:250]}")
    out("```")

    kimi_rows4 = [l.strip() for l in html4.split('\n') if '君' in l and '<' in l]
    out(f"\n「君」を含むHTML行数: {len(kimi_rows4)}")
    if kimi_rows4:
        out("サンプル（最初の5件）:")
        out("```")
        for r in kimi_rows4[:5]:
            out(r[:300])
        out("```")

    out("\nHTMLの先頭800文字:")
    out("```html")
    out(html4[:800])
    out("```")
else:
    out(f"❌ **取得失敗**: {html4[:200]}")

# ──────────────────────────────────────────────
# まとめ
# ──────────────────────────────────────────────
section("まとめ")
results = {
    "衆議院 議案一覧": status,
    "衆法 個別経過ページ": status2,
    "参議院 議案一覧": status3,
    "参法 個別ページ": status4,
}
out("| ページ | HTTPステータス | 結果 |")
out("|--------|---------------|------|")
for page, st in results.items():
    mark = "✅ 成功" if st == 200 else f"❌ 失敗({st})"
    out(f"| {page} | {st} | {mark} |")
