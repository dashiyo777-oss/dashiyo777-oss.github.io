#!/usr/bin/env python3
"""
追加プローブ（第3回）:
- 衆法 個別経過ページ（keika/）の提出者・賛成者 HTML 構造確認
- keika/1DE153E.htm (第221回衆法第1号) を完全取得
- keika/1DE1F62.htm (第221回衆法第2号) で比較
- URL hex ハッシュの規則性確認
"""
import re
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
        for enc in ("utf-8", "shift_jis", "cp932", "euc-jp"):
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


def report_page(label, url, html, status):
    """経過ページの内容を分析して報告する"""
    out(f"\nHTTP status: **{status}** / サイズ: {len(html):,} bytes")
    if status != 200:
        out(f"❌ 取得失敗: {html[:200]}")
        return

    out("✅ 取得成功")

    # ── 議案名・回次などのメタ情報 ──
    out("\n### メタ情報")
    for kw in ["議案名", "件名", "法律案", "議案", "提出回次", "提出番号", "審議"]:
        rows = [l.strip() for l in html.split('\n')
                if kw in l and '<' in l and len(l.strip()) < 600]
        if rows:
            out(f"\n[{kw}]:")
            out("```")
            for r in rows[:5]:
                out(r[:350])
            out("```")

    # ── 提出者・賛成者 ──
    out("\n### 提出者・賛成者")
    for kw in ["提出者", "発議者", "賛成者", "起草者", "提案者"]:
        rows = [l.strip() for l in html.split('\n') if kw in l]
        if rows:
            out(f"\n[{kw}]:")
            out("```")
            for r in rows[:15]:
                out(r[:400])
            out("```")

    # 「君」を含む行（議員名の表記確認：全員列挙 or 筆頭+外N名）
    kimi = [l.strip() for l in html.split('\n')
            if '君' in l and len(l.strip()) < 1000]
    out(f"\n### 「君」を含む行: {len(kimi)} 件（議員名の列挙方式確認）")
    if kimi:
        out("```")
        for r in kimi[:20]:
            out(r[:400])
        out("```")

    # 「外○名」パターン
    gaido = re.findall(r'外\s*\d+\s*名', html)
    out(f"\n「外○名」パターン: {gaido}")

    # ── HTML 全文 ──
    out("\n### HTML 先頭 3000 文字")
    out("```html")
    out(html[:3000])
    out("```")

    out("\n### HTML 末尾 1000 文字")
    out("```html")
    out(html[-1000:])
    out("```")


# ──────────────────────────────────────────────
# 1. 衆法 第221回 第1号 経過ページ
#    議案名: 政治資金規正法の一部を改正する法律案
# ──────────────────────────────────────────────
SHU1_URL = ("https://www.shugiin.go.jp"
            "/internet/itdb_gian.nsf/html/gian/keika/1DE153E.htm")

section("1. 衆法 第221回第1号 経過ページ（政治資金規正法改正案）")
out(f"URL: `{SHU1_URL}`")
# 衆議院は Shift_JIS 系が多い
st1, sz1, html1 = fetch(SHU1_URL, encoding="shift_jis")
report_page("衆法第1号", SHU1_URL, html1, st1)

time.sleep(SLEEP)

# ──────────────────────────────────────────────
# 2. 衆法 第221回 第2号 経過ページ（比較用）
#    議案名: 令和八年度における公債の発行の特例に関する法律案
# ──────────────────────────────────────────────
SHU2_URL = ("https://www.shugiin.go.jp"
            "/internet/itdb_gian.nsf/html/gian/keika/1DE1F62.htm")

section("2. 衆法 第221回第2号 経過ページ（比較・提出者パターン確認）")
out(f"URL: `{SHU2_URL}`")
st2, sz2, html2 = fetch(SHU2_URL, encoding="shift_jis")
report_page("衆法第2号", SHU2_URL, html2, st2)

# ──────────────────────────────────────────────
# 3. URL hex ハッシュの規則性確認
# ──────────────────────────────────────────────
section("3. URL hex ハッシュの規則性確認")

hashes = ['1DE153E', '1DE1F62', '1DE1E7E', '1DE1E6A']
labels = ['衆法第1号', '衆法第2号', '衆法第3号', '衆法第4号']

out("\nkaiji221.htm から収集した keika/ URL のハッシュ:")
out("```")
vals = []
for h, lb in zip(hashes, labels):
    v = int(h, 16)
    vals.append(v)
    out(f"  {lb}: {h}  →  {v:,} (10進)")
out("```")

diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
out(f"\n隣接差分 (10進): {diffs}")
out("差分の一様性: " + ("あり（連番）" if len(set(diffs)) == 1 else "なし（ランダム）"))
out("\n→ 差分が不規則 → URL を bill 番号から逆算不可 → 一覧ページ href 経由取得が必須")

# ──────────────────────────────────────────────
# まとめ
# ──────────────────────────────────────────────
section("まとめ")
out("| 確認項目 | 結果 |")
out("|---------|------|")    
out(f"| 衆法第1号 経過ページ | {'✅ 200' if st1 == 200 else f'❌ {st1}'} |")
out(f"| 衆法第2号 経過ページ | {'✅ 200' if st2 == 200 else f'❌ {st2}'} |")
out("| URL hex ハッシュ規則性 | なし（一覧経由必須） |")
