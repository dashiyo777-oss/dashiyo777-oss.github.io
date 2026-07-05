#!/usr/bin/env python3
"""
参議院 第221回国会 本会議投票記録取得スクリプト。

出力: votes/{議員ID}.json (参議院議員ごと、1ファイル = 1議員の全投票記録)
実行: python3 scripts/fetch_vote_records.py [--limit N] [--dry-run]

  --limit N   : 最初の N 件の議案のみ処理（テスト用）
  --dry-run   : HTTPアクセスなし、辞書構築のみ確認
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_aliases import get_aliases

# ── 定数 ─────────────────────────────────────────────────────────────
UA = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; research)"
SLEEP = 3.0
SESSION = 221
SESSION_YEAR = 2026
BASE_URL = f"https://www.sangiin.go.jp/japanese/touhyoulist/{SESSION}/"
INDEX_URL = f"{BASE_URL}vote_ind.htm"
REPO_ROOT = Path(__file__).resolve().parent.parent

# 参議院投票記録用のエイリアス（common_aliases.py で一元管理）
ALIASES = get_aliases("sangiin_vote")


# ── ユーティリティ ────────────────────────────────────────────────────
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


def normalize_name(name: str) -> str:
    """NFKC正規化 + 全角・半角スペースを全て除去"""
    return re.sub(r"[　\s]+", "", unicodedata.normalize("NFKC", name))


# ── data.js から参議院議員を読み込む ─────────────────────────────────
def load_sangiin_members() -> tuple[dict[str, str], dict[str, dict]]:
    """
    戻り値:
      name_to_id: 正規化名 → 議員ID
      id_to_info: 議員ID → {name, party}
    """
    data = (REPO_ROOT / "data.js").read_text(encoding="utf-8")

    name_to_id: dict[str, str] = {}
    id_to_info: dict[str, dict] = {}

    for pid_m in re.finditer(r'\bid:"(P\d+)"', data):
        pid = pid_m.group(1)
        ob = data.rfind("{", 0, pid_m.start())
        if ob < 0:
            continue
        # ブレース深度マッチングでエントリ全体を抽出
        depth, i = 1, ob + 1
        while i < len(data) and depth > 0:
            if data[i] == "{":
                depth += 1
            elif data[i] == "}":
                depth -= 1
            i += 1
        entry = data[ob:i]

        chamber_m = re.search(r'\bchamber:"([^"]+)"', entry)
        if not chamber_m or chamber_m.group(1) != "参議院":
            continue

        name_m = re.search(r'\bname:"([^"]+)"', entry)
        party_m = re.search(r'\bparty:"([^"]+)"', entry)
        if not (name_m and party_m):
            continue

        norm = normalize_name(name_m.group(1))
        name_to_id[norm] = pid
        id_to_info[pid] = {"name": name_m.group(1), "party": party_m.group(1)}

    # ALIASES を参議院議員のみ追加
    for alias_pid, aliases in ALIASES.items():
        if alias_pid not in id_to_info:
            continue
        for alias in aliases:
            name_to_id[normalize_name(alias)] = alias_pid

    return name_to_id, id_to_info


# ── vote_ind.htm から詳細URLを抽出 ────────────────────────────────────
def extract_detail_urls(index_html: str) -> list[str]:
    hrefs = re.findall(r'href="([^"]+)"', index_html, re.IGNORECASE)
    return list(dict.fromkeys(
        BASE_URL + h
        for h in hrefs
        if re.match(r"\d+-\d{4}-v\d+\.htm$", h, re.IGNORECASE)
    ))


# ── 詳細ページのパース ────────────────────────────────────────────────
def parse_bill_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    if not m:
        return ""
    return re.sub(r"\s*[：:]本会議投票結果.*", "", m.group(1)).strip()


def parse_vote_date(url: str) -> str:
    """URLパターン 221-MMDD-vNNN.htm → 2026-MM-DD"""
    m = re.search(r"/\d{3}-(\d{2})(\d{2})-v\d+\.htm", url, re.IGNORECASE)
    return f"{SESSION_YEAR}-{m.group(1)}-{m.group(2)}" if m else ""


def parse_member_votes(html: str) -> list[dict]:
    """
    議員ごとの投票記録を返す。
    各レコード: {raw_name: str, vote: "pros"|"cons"|"novote"|"unknown", party_group: str}
    """
    records: list[dict] = []
    current_party = ""

    # h4.party (会派区切り) と li.giin (議員エントリ) を文書順で処理
    for tok in re.finditer(
        r'<h4[^>]*class="party"[^>]*>(.*?)</h4>'
        r'|<li[^>]*class="giin"[^>]*>(.*?)</li>',
        html, re.DOTALL | re.IGNORECASE
    ):
        if tok.group(1) is not None:
            raw = re.sub(r"<[^>]+>", "", tok.group(1))
            current_party = re.sub(r"\(\s*\d+\s*名?\s*\)", "", raw).strip()
        else:
            li_html = tok.group(2)
            nm = re.search(r'class="names"[^>]*>(.*?)</span>', li_html,
                           re.IGNORECASE | re.DOTALL)
            if not nm:
                continue
            raw_name = re.sub(r"<[^>]+>", "", nm.group(1)).strip()

            if re.search(r'class="pros"[^>]*>\s*賛成\s*</span>', li_html, re.IGNORECASE):
                vote = "pros"
            elif re.search(r'class="cons"[^>]*>\s*反対\s*</span>', li_html, re.IGNORECASE):
                vote = "cons"
            elif re.search(r'class="novote"', li_html, re.IGNORECASE):
                vote = "novote"
            else:
                vote = "unknown"

            records.append({
                "raw_name": raw_name,
                "vote": vote,
                "party_group": current_party,
            })

    return records


# ── メイン ────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="参議院第221回 投票記録取得")
    parser.add_argument("--limit", type=int, default=None,
                        help="処理する議案数の上限（省略時は全件）")
    parser.add_argument("--dry-run", action="store_true",
                        help="HTTPアクセスなし、辞書構築のみ確認")
    args = parser.parse_args()

    label = f"（テスト: 先頭{args.limit}件）" if args.limit else "（全件）"
    print(f"=== 参議院第221回 投票記録取得スクリプト {label} ===\n")

    # [1] data.js 読み込み
    print("[1] data.js から参議院議員情報を読み込み中...")
    name_to_id, id_to_info = load_sangiin_members()
    print(f"    参議院議員数: {len(id_to_info)}名")
    print(f"    正規化名辞書: {len(name_to_id)}件 (ALIASES含む)\n")

    if args.dry_run:
        print("[DRY-RUN] 辞書確認完了。HTTPアクセスをスキップします。")
        return

    # [2] 投票一覧インデックス取得
    print(f"[2] 投票結果一覧取得: {INDEX_URL}")
    index_html = fetch(INDEX_URL)
    time.sleep(SLEEP)
    detail_urls = extract_detail_urls(index_html)
    if args.limit:
        detail_urls = detail_urls[:args.limit]
    print(f"    詳細ページ: {len(detail_urls)}件\n")

    # [3] 各詳細ページを取得・パース
    print(f"[3] 各詳細ページを取得中 ({SLEEP:.0f}秒間隔)...")
    all_votes: dict[str, list] = {}
    unmatched: dict[str, int] = {}
    stats = {"pages": 0, "total": 0, "matched": 0, "unmatched": 0}

    for i, url in enumerate(detail_urls, 1):
        fname = url.rsplit("/", 1)[-1]
        try:
            html = fetch(url)
            time.sleep(SLEEP)
        except Exception as e:
            print(f"  [{i:2d}/{len(detail_urls)}] {fname} → ERROR: {e}")
            continue

        title = parse_bill_title(html)
        date = parse_vote_date(url)
        records = parse_member_votes(html)
        stats["pages"] += 1

        print(f"  [{i:2d}/{len(detail_urls)}] {fname} ({date}) {title[:38]}… ({len(records)}名)")

        base_entry = {
            "session": SESSION,
            "date": date,
            "bill": title,
            "url": fname,
        }

        for rec in records:
            stats["total"] += 1
            pid = name_to_id.get(normalize_name(rec["raw_name"]))
            if pid is None:
                stats["unmatched"] += 1
                unmatched[rec["raw_name"]] = unmatched.get(rec["raw_name"], 0) + 1
                continue
            stats["matched"] += 1
            all_votes.setdefault(pid, []).append({
                **base_entry,
                "vote": rec["vote"],
                "party_group": rec["party_group"],
            })

    # [4] votes/ に出力
    votes_dir = REPO_ROOT / "votes"
    votes_dir.mkdir(exist_ok=True)
    print(f"\n[4] votes/ に出力中...")

    for pid in sorted(all_votes):
        info = id_to_info[pid]
        out_path = votes_dir / f"{pid}.json"
        # 既存ファイルがあれば votes リストをマージ（将来の複数会期対応）
        if out_path.exists():
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            existing_urls = {v["url"] for v in existing.get("votes", [])}
            new_votes = [v for v in all_votes[pid] if v["url"] not in existing_urls]
            merged = existing.get("votes", []) + new_votes
        else:
            merged = all_votes[pid]

        out = {
            "id": pid,
            "name": info["name"],
            "party": info["party"],
            "chamber": "参議院",
            "votes": sorted(merged, key=lambda v: (v["date"], v["url"])),
        }
        out_path.write_text(
            json.dumps(out, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"    {len(all_votes)}名分出力\n")

    # [5] サマリー
    print("=== サマリー ===")
    print(f"詳細ページ: {stats['pages']} / {len(detail_urls)} 件処理")
    print(f"レコード総数: {stats['total']}")
    print(f"  照合成功: {stats['matched']}")
    print(f"  未照合:   {stats['unmatched']}")
    print(f"出力ファイル: {len(all_votes)} 名分")

    if unmatched:
        print(f"\n[未照合名一覧] {len(unmatched)}件 — ALIASES 追加を検討:")
        for name, cnt in sorted(unmatched.items(), key=lambda x: -x[1]):
            print(f"  '{name}' ({cnt}件)")
    else:
        print("\n[未照合] なし")


if __name__ == "__main__":
    main()
