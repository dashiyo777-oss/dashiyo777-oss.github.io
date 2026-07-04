#!/usr/bin/env python3
"""
robots.txt の確認と、衆参一覧ページの HTML 構造を調査するプローブスクリプト。
GitHub Actions 上で実行し、出力を確認してから本実装を行う。
"""

import urllib.request, urllib.parse, time, sys

UA = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; research purpose)"
SLEEP = 3.0  # 礼儀正しい間隔


def fetch(url, label=""):
    print(f"\n{'='*60}")
    print(f"URL: {url}")
    if label:
        print(f"目的: {label}")
    print("="*60)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            # エンコード推定
            for enc in ("utf-8", "euc-jp", "shift_jis", "cp932"):
                try:
                    text = raw.decode(enc)
                    print(f"[エンコード: {enc}]")
                    return text
                except UnicodeDecodeError:
                    continue
            print("[エンコード不明 — バイナリ出力]")
            return raw.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[エラー] {e}")
        return None


def show_html_snippet(html, max_lines=80):
    """HTMLの先頭部分と、tableタグ周辺を表示する。"""
    lines = html.splitlines()
    print(f"\n--- 先頭50行 ---")
    for line in lines[:50]:
        print(line)

    print(f"\n--- <table> タグ付近（最大{max_lines}行）---")
    in_table = False
    table_lines = 0
    for line in lines:
        if "<table" in line.lower():
            in_table = True
        if in_table:
            print(line)
            table_lines += 1
            if table_lines >= max_lines:
                print("... (以下省略)")
                break
        if "</table>" in line.lower() and in_table:
            break


def main():
    # ── 1. robots.txt ──────────────────────────────────────
    print("\n" + "★"*60)
    print("★ STEP 1: robots.txt の確認")
    print("★"*60)

    shugiin_robots = fetch(
        "https://www.shugiin.go.jp/robots.txt",
        "衆議院 robots.txt"
    )
    if shugiin_robots:
        print(shugiin_robots[:2000])
    time.sleep(SLEEP)

    sangiin_robots = fetch(
        "https://www.sangiin.go.jp/robots.txt",
        "参議院 robots.txt"
    )
    if sangiin_robots:
        print(sangiin_robots[:2000])
    time.sleep(SLEEP)

    # ── 2. 参議院 一覧ページの構造確認（第221回）──────────────
    print("\n" + "★"*60)
    print("★ STEP 2: 参議院 第221回 質問主意書一覧の HTML 構造確認")
    print("★"*60)

    sangiin_html = fetch(
        "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/221/syuisyo.htm",
        "参議院 第221回 質問主意書一覧"
    )
    if sangiin_html:
        show_html_snippet(sangiin_html, max_lines=120)
    time.sleep(SLEEP)

    # ── 3. 衆議院 一覧ページの構造確認（第221回）──────────────
    print("\n" + "★"*60)
    print("★ STEP 3: 衆議院 第221回 質問答弁一覧の HTML 構造確認")
    print("★"*60)

    shugiin_html = fetch(
        "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/kaiji221_l.htm",
        "衆議院 第221回 質問答弁一覧"
    )
    if shugiin_html:
        show_html_snippet(shugiin_html, max_lines=120)
    time.sleep(SLEEP)

    # ── 4. 参議院 第207回（範囲確認）──────────────────────────
    print("\n" + "★"*60)
    print("★ STEP 4: 参議院 第207回 存在確認")
    print("★"*60)

    sangiin_207 = fetch(
        "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/207/syuisyo.htm",
        "参議院 第207回 質問主意書一覧（存在確認）"
    )
    if sangiin_207:
        lines = sangiin_207.splitlines()
        print(f"取得成功: {len(lines)}行")
        # 提出者名が入りそうな行を探す
        print("\n--- '提出者' または '君' を含む行 ---")
        for line in lines:
            if "提出者" in line or ("君" in line and len(line) < 200):
                print(repr(line))
    time.sleep(SLEEP)

    print("\n" + "="*60)
    print("プローブ完了。上記出力を確認してください。")
    print("="*60)


if __name__ == "__main__":
    main()
