#!/usr/bin/env python3
"""
衆参議員公式名簿と data.js の chamber フィールドを突合し、
選挙・辞職による陳腐化を検出するスクリプト。

出力:
  - 参院名簿にあるが chamber="衆議院" になっている議員
  - 衆院名簿にあるが chamber="参議院" になっている議員

使い方:
  python3 scripts/validate_chamber.py          # 通常実行
  python3 scripts/validate_chamber.py --dry-run # HTTP なし（辞書構築の確認のみ）

参照URL:
  参議院: https://www.sangiin.go.jp/japanese/joho1/kousei/giin/current/giin.htm
  衆議院: https://www.shugiin.go.jp/internet/itdb_annai.nsf/html/statics/syu/1giin.htm
"""

import argparse
import os
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

UA = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; research)"
SLEEP = 3.0
REPO_ROOT = Path(__file__).resolve().parent.parent

SANGIIN_URL = "https://www.sangiin.go.jp/japanese/joho1/kousei/giin/current/giin.htm"
SHUGIIN_URL = "https://www.shugiin.go.jp/internet/itdb_annai.nsf/html/statics/syu/1giin.htm"


def normalize(name: str) -> str:
    return re.sub(r"[　\s]+", "", unicodedata.normalize("NFKC", name))


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    for enc in ("utf-8", "euc-jp", "shift_jis", "cp932"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_names_from_html(html: str) -> set[str]:
    """
    衆参どちらのページでも機能する名前抽出。
    複数パターンを試みて結果を合算する。
    """
    names: set[str] = set()

    # パターン1: <a ...>姓　名</a> 形式（参院・衆院共通）
    for m in re.findall(r'<a[^>]+>([^\s<]{2,5}[　\s][^\s<]{1,5})</a>', html):
        n = normalize(m)
        if 2 <= len(n) <= 8:
            names.add(n)

    # パターン2: <td ...>姓　名</td>（スペース区切りの漢字名）
    for m in re.findall(r'<td[^>]*>([^\s<]{2,5}[　\s　][^\s<]{1,5})</td>', html):
        n = normalize(m)
        if 2 <= len(n) <= 8:
            names.add(n)

    # パターン3: data-name 属性
    for m in re.findall(r'data-name="([^"]{2,10})"', html):
        n = normalize(m)
        if n:
            names.add(n)

    # パターン4: class="name" スパン
    for m in re.findall(r'class="[^"]*name[^"]*"[^>]*>([^<]{2,10})<', html, re.IGNORECASE):
        n = normalize(m.strip())
        if 2 <= len(n) <= 8:
            names.add(n)

    return names


def load_data_js_members() -> list[dict]:
    data = (REPO_ROOT / "data.js").read_text(encoding="utf-8")
    members = []
    for pid_m in re.finditer(r'\bid:"(P\d+)"', data):
        pid = pid_m.group(1)
        ob = data.rfind('{', 0, pid_m.start())
        if ob < 0:
            continue
        depth, i = 1, ob + 1
        while i < len(data) and depth > 0:
            if data[i] == '{':
                depth += 1
            elif data[i] == '}':
                depth -= 1
            i += 1
        entry = data[ob:i]
        name_m = re.search(r'\bname:"([^"]+)"', entry)
        chamber_m = re.search(r'\bchamber:"([^"]+)"', entry)
        if name_m and chamber_m:
            members.append({
                'id': pid,
                'name': name_m.group(1),
                'norm': normalize(name_m.group(1)),
                'chamber': chamber_m.group(1),
            })
    return members


def main() -> int:
    parser = argparse.ArgumentParser(description="衆参名簿 vs data.js 整合チェック")
    parser.add_argument("--dry-run", action="store_true",
                        help="HTTP アクセスなし（辞書構築確認のみ）")
    args = parser.parse_args()

    members = load_data_js_members()
    sangiin_in_data = [m for m in members if m['chamber'] == '参議院']
    shugiin_in_data = [m for m in members if m['chamber'] == '衆議院']
    print(f"data.js: 参議院 {len(sangiin_in_data)}名 / 衆議院 {len(shugiin_in_data)}名 / 計 {len(members)}名")

    if args.dry_run:
        print("[DRY-RUN] HTTP アクセスをスキップ。辞書構築のみ確認完了。")
        return 0

    print(f"\n[1] 参議院名簿取得: {SANGIIN_URL}")
    try:
        sangiin_html = fetch(SANGIIN_URL)
        time.sleep(SLEEP)
        sangiin_official = extract_names_from_html(sangiin_html)
        print(f"    抽出名数: {len(sangiin_official)}件")
    except Exception as e:
        print(f"    ERROR: {e}")
        sangiin_official = set()

    print(f"\n[2] 衆議院名簿取得: {SHUGIIN_URL}")
    try:
        shugiin_html = fetch(SHUGIIN_URL)
        time.sleep(SLEEP)
        shugiin_official = extract_names_from_html(shugiin_html)
        print(f"    抽出名数: {len(shugiin_official)}件")
    except Exception as e:
        print(f"    ERROR: {e}")
        shugiin_official = set()

    if not sangiin_official and not shugiin_official:
        print("\n両院の名簿取得に失敗。チェックを中断します。")
        return 1

    issues: list[tuple[str, dict]] = []

    # data.js で参議院扱いだが、衆院名簿にいて参院名簿にいない
    for m in sangiin_in_data:
        if shugiin_official and m['norm'] in shugiin_official:
            if not sangiin_official or m['norm'] not in sangiin_official:
                issues.append(('chamber=参議院 → 衆院名簿に存在（要確認）', m))

    # data.js で衆議院扱いだが、参院名簿にいて衆院名簿にいない
    for m in shugiin_in_data:
        if sangiin_official and m['norm'] in sangiin_official:
            if not shugiin_official or m['norm'] not in shugiin_official:
                issues.append(('chamber=衆議院 → 参院名簿に存在（要確認）', m))

    print(f"\n=== 整合チェック結果: {len(issues)}件の要確認 ===")
    if issues:
        for label, m in issues:
            print(f"  {m['id']} {m['name']}: {label}")
        print("\n※ 公式名簿のHTML構造変更により誤検知の可能性あり。必ず目視確認を。")
    else:
        print("不整合なし ✅")

    return len(issues)


if __name__ == "__main__":
    sys.exit(main())
