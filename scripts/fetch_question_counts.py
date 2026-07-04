#!/usr/bin/env python3
"""
衆参両院の質問主意書提出数を取得し facts.json に question_count を追加するスクリプト。

衆議院: https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/kaiji{N}_l.htm
参議院: https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/{N}/syuisyo.htm

HTML形式が2種類あるため自動検出して対応：
  - 新形式（第211回以降推定）: <TD headers="SHITSUMON.TEISHUTSUSHA">名前君</TD>
  - 旧形式（第207回など）:     <td class="ta_l">姓　　名君</td>

使い方:
  python3 scripts/fetch_question_counts.py          # 全15会期取得
  python3 scripts/fetch_question_counts.py --test   # 第221回のみ（動作確認）
  python3 scripts/fetch_question_counts.py --dry-run # API呼び出しなし
"""

import json, re, time, datetime, os, unicodedata, urllib.request, collections, argparse

UA = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; public data research)"
SLEEP = 3.0

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS    = os.path.join(BASE_DIR, "data.js")
FACTS_PATH = os.path.join(BASE_DIR, "facts.json")
UNMATCHED  = os.path.join(BASE_DIR, "unmatched_question_names.txt")
ERROR_LOG  = os.path.join(BASE_DIR, "error_log.txt")

# 取得対象会期（2021年11月以降）
SESSIONS      = list(range(207, 222))   # 207〜221
FROM_SESSION  = 207
UNTIL_SESSION = 221

SHUGIIN_URL = "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/kaiji{n}_l.htm"
SANGIIN_URL = "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/{n}/syuisyo.htm"

# 表記ゆれ・通称名マッピング（fix_speech_aliases.py と共通）
ALIASES = {
    "P010": ["浅田真澄美"],
    "P076": ["漆間譲司"],        # data.jsは「うるま譲司」（ひらがな）、質問主意書は漢字表記
    "P109": ["鹿島祐介"],
    "P121": ["金沢結衣"],
    "P284": ["長沢興祐"],
    "P783": ["斎藤元彦", "齊藤元彦"],
    "P794": ["浜田省司"],
    "P073": ["内山幸子"],
    "P165": ["高来啓一郎", "高麗啓一郎"],
    "P802": ["玉城康裕"],
    "P815": ["大石あきこ"],      # data.jsは「大石晃子」（漢字）、質問主意書はひらがな表記
    "P817": ["佐藤紗央里"],
}


# ── ユーティリティ ──────────────────────────────────────────────

def normalize(name: str) -> str:
    """NFKC正規化 + 全スペース（全角含む）除去 + 末尾の「君」除去"""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r'[\s　]+', '', name)
    name = name.rstrip('君')
    return name.strip()


def fetch_html(url: str, encoding: str | None = None) -> str | None:
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
        return None


# ── HTML パーサー ────────────────────────────────────────────────

def extract_names_new(html: str) -> list[str]:
    """新形式: headers="SHITSUMON.TEISHUTSUSHA" から抽出"""
    return re.findall(
        r'headers="SHITSUMON\.TEISHUTSUSHA"[^>]*>\s*<span[^>]*>([^<]+)</span>',
        html, re.IGNORECASE
    )


def extract_names_old(html: str) -> list[str]:
    """旧形式: class="ta_l" の「君」で終わるセルを抽出"""
    return re.findall(
        r'<td[^>]*class="ta_l"[^>]*>([^<]*君)</td>',
        html, re.IGNORECASE
    )


def extract_names(html: str) -> list[str]:
    """形式を自動検出して提出者名を抽出・正規化して返す"""
    if 'SHITSUMON.TEISHUTSUSHA' in html or 'shitsumontable' in html:
        raw_names = extract_names_new(html)
        fmt = "新"
    else:
        raw_names = extract_names_old(html)
        fmt = "旧"
    normalized = [normalize(n) for n in raw_names]
    normalized = [n for n in normalized if n]  # 空文字除去
    return normalized, fmt


# ── 議員名照合辞書の構築 ─────────────────────────────────────────

def build_name_dict() -> dict[str, str]:
    """data.js から id と name を読み込み、正規化した名前 → pid の辞書を作る"""
    text = open(DATA_JS, encoding='utf-8').read()
    pattern = re.compile(r'id:"(P\d+)"[^{}]*?name:"([^"]+)"')
    d = {}
    for m in pattern.finditer(text):
        pid, name = m.group(1), m.group(2)
        norm = normalize(name)
        if norm:
            d[norm] = pid
    # エイリアスを追加
    for pid, aliases in ALIASES.items():
        for alias in aliases:
            d[normalize(alias)] = pid
    return d


# ── メイン ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="API呼び出しなし（確認のみ）")
    parser.add_argument("--test",    action="store_true", help="第221回のみ（動作確認）")
    args = parser.parse_args()

    # ── robots.txt 確認 ──
    print("=== robots.txt 確認 ===")
    for label, url in [
        ("衆議院", "https://www.shugiin.go.jp/robots.txt"),
        ("参議院", "https://www.sangiin.go.jp/robots.txt"),
    ]:
        html = fetch_html(url)
        if html:
            print(f"[{label}]\n{html[:600]}")
        else:
            print(f"[{label}] 取得失敗（続行）")
        time.sleep(2)

    # ── 照合辞書構築 ──
    name_to_pid = build_name_dict()
    print(f"\n照合辞書: {len(name_to_pid)}件のエントリ")

    question_counts: dict[str, int] = collections.Counter()
    unmatched: dict[str, int]       = collections.Counter()
    errors: list[str]               = []

    sessions = [221] if args.test else SESSIONS

    # ── 各会期・各院を巡回 ──
    for session in sessions:
        for chamber, url_tmpl, enc in [
            ("衆議院", SHUGIIN_URL, "shift_jis"),
            ("参議院", SANGIIN_URL, None),
        ]:
            url = url_tmpl.format(n=session)
            print(f"\n[第{session}回 {chamber}]")

            if args.dry_run:
                print(f"  [DRY-RUN] {url}")
                continue

            html = fetch_html(url, encoding=enc)
            if not html:
                msg = f"第{session}回 {chamber}: 取得失敗"
                print(f"  ✗ {msg}")
                errors.append(msg)
                time.sleep(SLEEP)
                continue

            names, fmt = extract_names(html)
            print(f"  形式={fmt}形式, 提出者名={len(names)}件")

            matched = 0
            for name in names:
                pid = name_to_pid.get(name)
                if pid:
                    question_counts[pid] += 1
                    matched += 1
                else:
                    unmatched[name] += 1

            print(f"  照合成功={matched}件 / 未照合={len(names)-matched}件")
            time.sleep(SLEEP)

    if args.dry_run:
        print("\n[DRY-RUN] 完了（ファイル更新なし）")
        return

    # ── facts.json 更新 ──
    with open(FACTS_PATH, encoding='utf-8') as f:
        facts = json.load(f)

    period_str = f"第{FROM_SESSION}回〜第{UNTIL_SESSION}回国会"

    # カウントがあった議員を更新
    for pid, count in question_counts.items():
        if pid not in facts:
            facts[pid] = {}
        facts[pid]["question_count"]  = count
        facts[pid]["question_period"] = period_str

    # カウントがなかった議員は 0 を明示
    for pid in facts:
        if "question_count" not in facts[pid]:
            facts[pid]["question_count"]  = 0
            facts[pid]["question_period"] = period_str

    with open(FACTS_PATH, "w", encoding='utf-8') as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)

    # ── 未照合リスト出力 ──
    print(f"\n=== 完了 ===")
    print(f"question_count 更新: {len(question_counts)}名")
    print(f"エラー: {len(errors)}件")

    print(f"\n=== 照合できなかった提出者名（上位50件）===")
    for name, cnt in unmatched.most_common(50):
        print(f"  {name}: {cnt}件")

    if unmatched:
        with open(UNMATCHED, "w", encoding='utf-8') as f:
            for name, cnt in unmatched.most_common():
                f.write(f"{name}\t{cnt}\n")
        print(f"\n全未照合リスト → {UNMATCHED}")

    if errors:
        with open(ERROR_LOG, "a", encoding='utf-8') as f:
            for e in errors:
                f.write(e + "\n")


if __name__ == "__main__":
    main()
