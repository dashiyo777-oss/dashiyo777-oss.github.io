#!/usr/bin/env python3
"""
追加プローブ（第2回）:
- 衆議院: kaiji221.htm の全 href を抽出し実際のリンク構造を確認
- 参議院: 相対 URL を正しく絶対化し個別明細ページ 2 件の発議者 HTML 構造を報告
- 両院: 衆法/参法のみを絞り込む確実な方法を特定
"""
import re
import time
import urllib.request
import urllib.error
import urllib.parse
import os
from collections import Counter

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
# 1. 衆議院 kaiji221.htm — 全 href 抽出とリンク構造確認
# ──────────────────────────────────────────────
section("1. 衆議院 kaiji221.htm の href 構造全調査")

SHUGIIN_KAIJI = "https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/kaiji221.htm"
out(f"URL: `{SHUGIIN_KAIJI}`")
st1, sz1, html1 = fetch(SHUGIIN_KAIJI, encoding="shift_jis")
out(f"HTTP status: **{st1}** / サイズ: {sz1:,} bytes")

shu_bill_url = None

if st1 == 200:
    # 全 href を収集
    all_hrefs = re.findall(r'href="([^"]+)"', html1, re.IGNORECASE)
    ext_hrefs = [h for h in all_hrefs if not h.startswith('#')]
    out(f"\n全 href 数: {len(all_hrefs)} / ハッシュリンク除外後: {len(ext_hrefs)}")
    out("\n外部 href サンプル（最初の30件）:")
    out("```")
    for h in ext_hrefs[:30]:
        out(h)
    out("```")

    # OpenDocument 形式の URL（Lotus Notes/Domino 特有）
    opendoc = [h for h in all_hrefs if 'OpenDocument' in h or 'opendocument' in h.lower()]
    out(f"\nOpenDocument を含む href: {len(opendoc)} 件")
    if opendoc:
        out("```")
        for h in opendoc[:10]:
            out(h)
        out("```")
        first = opendoc[0]
        shu_bill_url = ("https://www.shugiin.go.jp" + first) if first.startswith('/') else first

    # 衆法セクション付近の HTML（前後2000文字）
    pos = html1.find('衆法の一覧')
    if pos >= 0:
        snippet = html1[max(0, pos - 200):pos + 2000]
        subsection("「衆法の一覧」周辺 HTML（前200 + 後2000文字）")
        out("```html")
        out(snippet)
        out("```")

        # スニペット内の href
        snip_hrefs = re.findall(r'href="([^"]+)"', snippet, re.IGNORECASE)
        out(f"\nこのスニペット内 href ({len(snip_hrefs)} 件): {snip_hrefs}")

    # <a href> を含む全行をリスト
    a_rows = [l.strip() for l in html1.split('\n') if '<a ' in l.lower() and 'href' in l.lower()]
    out(f"\n<a href> を含む行数: {len(a_rows)}")
    if a_rows:
        out("\n全 <a href> 行（最大30件）:")
        out("```")
        for r in a_rows[:30]:
            out(r[:400])
        out("```")

time.sleep(SLEEP)

# ──────────────────────────────────────────────
# 2. 衆法 個別ページ（取得できた URL で）
# ──────────────────────────────────────────────
section("2. 衆法 個別ページ（発議者・賛成者の HTML 構造）")

st2, sz2, html2 = None, 0, ""
if shu_bill_url:
    out(f"URL: `{shu_bill_url}`")
    st2, sz2, html2 = fetch(shu_bill_url)
    out(f"HTTP status: **{st2}** / サイズ: {sz2:,} bytes")
    if st2 == 200:
        out("✅ 取得成功")
        for kw in ["提出者", "発議者", "賛成者", "起草者", "提案者"]:
            rows = [l.strip() for l in html2.split('\n') if kw in l]
            if rows:
                out(f"\n[{kw}]:")
                out("```")
                for r in rows[:5]:
                    out(r[:350])
                out("```")
        kimi = [l.strip() for l in html2.split('\n') if '君' in l and '<' in l]
        out(f"\n「君」を含む行: {len(kimi)} 件")
        if kimi:
            out("```")
            for r in kimi[:5]:
                out(r[:300])
            out("```")
        out("\nHTML 先頭 1000 文字:")
        out("```html")
        out(html2[:1000])
        out("```")
    else:
        out(f"❌ 取得失敗")
else:
    out("⚠️ 衆法個別 URL が取得できなかったためスキップ")
    out("→ kaiji221.htm に直接リンクが存在しない可能性。")
    out("  衆法一覧の別ページ（kaiji系の他URLや OpenDocument 経由）を要調査。")

time.sleep(SLEEP)

# ──────────────────────────────────────────────
# 3. 参議院 議案一覧 → 参法セクション絞り込み → 絶対 URL 構築
# ──────────────────────────────────────────────
section("3. 参議院 gian.htm の構造調査・参法セクション絞り込み")

SANGIIN_BASE = "https://www.sangiin.go.jp/japanese/joho1/kousei/gian/221/"
SANGIIN_KAIJI = SANGIIN_BASE + "gian.htm"
out(f"URL: `{SANGIIN_KAIJI}`")
st3, sz3, html3 = fetch(SANGIIN_KAIJI)
out(f"HTTP status: **{st3}** / サイズ: {sz3:,} bytes")

sanho_links = []
all_meisai_by_section = []  # list of (section_label, abs_url)
st4, sz4, html4 = None, 0, ""
st5, sz5, html5 = None, 0, ""

if st3 == 200:
    # セクションを追いながら meisai リンクを分類
    lines = html3.split('\n')
    current_sec = None
    for line in lines:
        if '法律案（参法）' in line or ('参法' in line and '一覧' in line):
            current_sec = 'sanho'
        elif '内閣提出' in line and ('一覧' in line or '閣法' in line):
            current_sec = 'kakuho'
        elif '衆法' in line and '一覧' in line:
            current_sec = 'shuho'

        hrefs = re.findall(r'href="([^"]*meisai[^"]*\.htm)"', line, re.IGNORECASE)
        for h in hrefs:
            abs_url = urllib.parse.urljoin(SANGIIN_BASE, h)
            all_meisai_by_section.append((current_sec, abs_url))
            if current_sec == 'sanho':
                sanho_links.append(abs_url)

    sec_counts = Counter(s for s, _ in all_meisai_by_section)
    out(f"\nセクション別リンク数: {dict(sec_counts)}")
    out(f"参法リンク数（sanho）: {len(sanho_links)}")

    if sanho_links:
        out(f"\n参法リンク サンプル（最初の5件）:")
        out("```")
        for u in sanho_links[:5]:
            out(u)
        out("```")

    # ファイル名パターン分析（セクション別）
    out("\n全明細URL ファイル名パターン（先頭20件、セクション付き）:")
    out("```")
    for sec, url in all_meisai_by_section[:20]:
        out(f"{sec or '?':8s}  {url.split('/')[-1]}")
    out("```")

time.sleep(SLEEP)

# ──────────────────────────────────────────────
# 4. 参法 個別明細ページ 1 件目
# ──────────────────────────────────────────────
section("4. 参法 個別明細ページ 1 件目（発議者 HTML 構造）")

if sanho_links:
    san_url1 = sanho_links[0]
    out(f"URL: `{san_url1}`")
    st4, sz4, html4 = fetch(san_url1)
    out(f"HTTP status: **{st4}** / サイズ: {sz4:,} bytes")

    if st4 == 200:
        out("✅ 取得成功")

        # 発議者関連キーワード
        for kw in ["発議者", "提出者", "賛成者", "議員発議"]:
            rows = [l.strip() for l in html4.split('\n') if kw in l]
            if rows:
                out(f"\n[{kw}]:")
                out("```")
                for r in rows[:5]:
                    out(r[:400])
                out("```")

        # 「外○名」パターン
        gaido = re.findall(r'外\s*\d+\s*名', html4)
        out(f"\n「外○名」パターン: {gaido}")

        # 「君」を含む行（議員名の表記確認）
        kimi = [l.strip() for l in html4.split('\n') if '君' in l and '<' in l]
        out(f"\n「君」を含む行: {len(kimi)} 件")
        if kimi:
            out("```")
            for r in kimi[:8]:
                out(r[:350])
            out("```")

        # 種別判定のキーワード
        for kw in ["参法", "閣法", "衆法", "内閣提出", "議員発議", "参議院先議"]:
            rows = [l.strip() for l in html4.split('\n') if kw in l]
            if rows:
                out(f"\n[種別:{kw}]:")
                out("```")
                for r in rows[:3]:
                    out(r[:250])
                out("```")

        # HTML 先頭 1500 文字
        out("\nHTML 先頭 1500 文字:")
        out("```html")
        out(html4[:1500])
        out("```")

        # HTML 末尾 500 文字
        out("\nHTML 末尾 500 文字:")
        out("```html")
        out(html4[-500:])
        out("```")
    else:
        out(f"❌ 取得失敗: {html4[:200]}")
else:
    out("⚠️ 参法リンクが見つからなかったためスキップ")

time.sleep(SLEEP)

# ──────────────────────────────────────────────
# 5. 参法 個別明細ページ 2 件目（発議者パターン比較）
# ──────────────────────────────────────────────
section("5. 参法 個別明細ページ 2 件目（発議者パターン比較）")

if len(sanho_links) >= 2:
    san_url2 = sanho_links[1]
    out(f"URL: `{san_url2}`")
    st5, sz5, html5 = fetch(san_url2)
    out(f"HTTP status: **{st5}** / サイズ: {sz5:,} bytes")

    if st5 == 200:
        out("✅ 取得成功")
        for kw in ["発議者", "提出者", "賛成者"]:
            rows = [l.strip() for l in html5.split('\n') if kw in l]
            if rows:
                out(f"\n[{kw}]:")
                out("```")
                for r in rows[:5]:
                    out(r[:400])
                out("```")
        gaido2 = re.findall(r'外\s*\d+\s*名', html5)
        out(f"\n「外○名」パターン: {gaido2}")
        kimi2 = [l.strip() for l in html5.split('\n') if '君' in l and '<' in l]
        out(f"\n「君」を含む行: {len(kimi2)} 件")
        if kimi2:
            out("```")
            for r in kimi2[:5]:
                out(r[:300])
            out("```")
    else:
        out(f"❌ 取得失敗: {html5[:200]}")
else:
    out("（参法リンクが 1 件以下のため省略）")

# ──────────────────────────────────────────────
# まとめ
# ──────────────────────────────────────────────
section("まとめ")
out("| 調査項目 | 結果 |")
out("|---------|------|")    
out(f"| 衆議院 一覧ページ | {'✅ 200' if st1 == 200 else f'❌ {st1}'} |")
out(f"| 衆法 個別ページ | {'✅ 200' if st2 == 200 else f'❌ {st2}（URL未取得）' if not shu_bill_url else f'❌ {st2}'} |")
out(f"| 参議院 一覧ページ | {'✅ 200' if st3 == 200 else f'❌ {st3}'} |")
out(f"| 参法リンク数（参法セクション） | {len(sanho_links)} |")
out(f"| 参法明細ページ 1 件目 | {'✅ 200' if st4 == 200 else f'❌ {st4}'} |")
out(f"| 参法明細ページ 2 件目 | {'✅ 200' if st5 == 200 else f'❌ {st5}'} |")
