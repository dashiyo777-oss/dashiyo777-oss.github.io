#!/usr/bin/env python3
"""
第207〜221回の衆法・参法を巡回し、発議者・賛成者カウントを facts.json に追加。

衆議院: kaiji{NNN}.htm → keika/{HEX}.htm (Shift_JIS)
  - 「議案提出者一覧」の次の width="60%" セル → 発議者全員（;区切り）
  - 「議案提出の賛成者」の次の width="60%" セル → 賛成者全員（同様）
  - 単独発議の場合は headers="NAIYO" セルの筆頭名にフォールバック

参議院: gian/{NNN}/gian.htm → meisai/m{NNN}10*.htm (UTF-8)
  - 主発議者のみ（「君」直前の名前）
  - 外N名は co_sponsor_count として保持するが集計には含めない

追加フィールド (facts.json):
  bill_sponsor_count   : 発議者件数（衆法発議 + 参法主発議）
  bill_supporter_count : 賛成者件数（衆法のみ、当面表示なし）
  bill_period          : 対象会期文字列

使い方:
  python3 scripts/fetch_bill_counts.py          # 全15会期（第207〜221回）
  python3 scripts/fetch_bill_counts.py --test   # 第221回のみ（動作確認）
  python3 scripts/fetch_bill_counts.py --dry-run
"""

import json, re, time, os, sys, unicodedata, urllib.request, urllib.parse, \
    collections, argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common_aliases import get_aliases

UA    = "TORAN-Research/1.0 (https://dashiyo777-oss.github.io; public data research)"
SLEEP = 3.5

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS    = os.path.join(BASE_DIR, "data.js")
FACTS_PATH = os.path.join(BASE_DIR, "facts.json")
UNMATCHED  = os.path.join(BASE_DIR, "unmatched_bill_names.txt")
ERROR_LOG  = os.path.join(BASE_DIR, "error_log.txt")
SUMMARY    = os.environ.get("GITHUB_STEP_SUMMARY", "")

SESSIONS      = list(range(207, 222))
FROM_SESSION  = 207
UNTIL_SESSION = 221

# 衆議院: kaiji{N}.htm は gian/ ディレクトリ配下
SHUGIIN_LIST_URL = (
    "https://www.shugiin.go.jp"
    "/internet/itdb_gian.nsf/html/gian/kaiji{n}.htm"
)
SHUGIIN_BASE = (
    "https://www.shugiin.go.jp"
    "/internet/itdb_gian.nsf/html/gian/"
)

# 参議院: gian/{N}/gian.htm
SANGIIN_LIST_URL = (
    "https://www.sangiin.go.jp"
    "/japanese/joho1/kousei/gian/{n}/gian.htm"
)
SANGIIN_BASE = (
    "https://www.sangiin.go.jp"
    "/japanese/joho1/kousei/gian/{n}/"
)

ALIASES = get_aliases("gian")


# ── ユーティリティ ────────────────────────────────────────────

def out(text: str = "") -> None:
    print(text)
    if SUMMARY:
        with open(SUMMARY, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def normalize(name: str) -> str:
    """NFKC正規化 + 全スペース除去 + 末尾「君」除去"""
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r'[\s　]+', '', name)
    name = name.rstrip('君')
    return name.strip()


def fetch_html(url: str, encoding: str | None = None) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        if encoding:
            return raw.decode(encoding, errors='replace')
        for enc in ("utf-8", "shift_jis", "cp932", "euc-jp"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors='replace')
    except Exception:
        return None


# ── 衆議院パーサー ────────────────────────────────────────────

def extract_shugiin_keika_urls(html: str) -> list[str]:
    """
    kaiji.htm から衆法 keika/ URL 一覧を抽出（絶対URL）。
    「衆法」セクション以降の ./keika/*.htm リンクのみを対象にする。
    """
    # 衆法セクション開始: より具体的な語句を優先
    for marker in ('衆法の一覧', '衆議院提出法律案', '衆法'):
        idx = html.find(marker)
        if idx != -1:
            shu_html = html[idx:]
            break
    else:
        shu_html = html

    # 衆法セクション終了: 参法 or 参議院提出 の見出しが来たら切る
    for end_marker in ('参法の一覧', '参議院提出法律案', '参法'):
        ei = shu_html.find(end_marker)
        if ei != -1:
            shu_html = shu_html[:ei]
            break

    hrefs = re.findall(r'href="(\./keika/[^"]+\.htm)"', shu_html, re.IGNORECASE)
    return [urllib.parse.urljoin(SHUGIIN_BASE, h) for h in hrefs]


def parse_keika_page(html: str) -> dict:
    """
    衆法 keika/ ページから提出者・賛成者を抽出。
    Returns {session, bill_no, title, sponsors, supporters}
    """
    result: dict = {
        'session': 0, 'bill_no': 0, 'title': '',
        'sponsors': [], 'supporters': [],
    }

    # タイトルタグから回次・番号・議案名
    m = re.search(
        r'<TITLE>衆法\s+第(\d+)回国会\s+(\d+)\s+([^<]+)</TITLE>',
        html, re.IGNORECASE
    )
    if m:
        result['session'] = int(m.group(1))
        result['bill_no'] = int(m.group(2))
        result['title']   = m.group(3).strip()

    # 提出者全員: 「議案提出者一覧」ヘッダの直後の width="60%" セル
    sm = re.search(
        r'議案提出者一覧[^<]*</span>[^<]*</TD>\s*'
        r'<TD[^>]*width="60%"[^>]*>[^<]*<span[^>]*>([^<]+)</span>',
        html, re.IGNORECASE
    )
    if sm:
        result['sponsors'] = [
            normalize(n) for n in sm.group(1).split(';') if normalize(n)
        ]
    else:
        # 単独発議フォールバック: 「議案提出者」行の NAIYO セル
        fm = re.search(
            r'議案提出者[^<]*</span>[^<]*</TD>\s*'
            r'<TD[^>]*headers="NAIYO"[^>]*>[^<]*<span[^>]*>([^<]+)</span>',
            html, re.IGNORECASE
        )
        if fm:
            raw  = fm.group(1)
            name = re.sub(r'外\s*\d+\s*名', '', raw).strip()
            n    = normalize(name)
            if n:
                result['sponsors'] = [n]

    # 賛成者全員: 「議案提出の賛成者」ヘッダの直後の width="60%" セル
    rm = re.search(
        r'議案提出の賛成者[^<]*</span>[^<]*</TD>\s*'
        r'<TD[^>]*width="60%"[^>]*>[^<]*<span[^>]*>([^<]+)</span>',
        html, re.IGNORECASE
    )
    if rm:
        result['supporters'] = [
            normalize(n) for n in rm.group(1).split(';') if normalize(n)
        ]

    return result


# ── 参議院パーサー ────────────────────────────────────────────

def extract_sangiin_meisai_urls(html: str, session: int) -> list[str]:
    """
    gian.htm から参法 meisai/ URL 一覧を抽出（絶対URL）。
    参法URLパターン: ./meisai/m{session}10*.htm（type code 10 = 参法）
    """
    pattern = rf'href="(\./meisai/m{session}10[^"]+\.htm)"'
    hrefs = re.findall(pattern, html, re.IGNORECASE)
    base  = SANGIIN_BASE.format(n=session)
    return [urllib.parse.urljoin(base, h) for h in hrefs]


def parse_meisai_page(html: str) -> dict:
    """
    参法 meisai/ ページから主発議者を抽出。
    Returns {main_sponsor, co_sponsor_count}
    """
    result: dict = {'main_sponsor': '', 'co_sponsor_count': 0}

    # class="ta_l" セルのうち「君」を含むものが発議者
    cells = re.findall(
        r'<td[^>]*class="ta_l"[^>]*>([^<]*君[^<]*)</td>',
        html, re.IGNORECASE
    )
    for cell in cells:
        cell = cell.strip()
        # 「外N名」あり
        m = re.match(r'(.+?君)\s*外\s*(\d+)\s*名', cell)
        if m:
            result['main_sponsor']     = normalize(m.group(1))
            result['co_sponsor_count'] = int(m.group(2))
            break
        # 「外N名」なし
        if cell.endswith('君'):
            result['main_sponsor'] = normalize(cell)
            break

    return result


# ── 名前照合辞書 ──────────────────────────────────────────────

def build_name_dict() -> dict[str, str]:
    """data.js から正規化名 → pid の辞書を構築（エイリアス込み）"""
    text = open(DATA_JS, encoding='utf-8').read()
    pat  = re.compile(r'id:"(P\d+)"[^{}]*?name:"([^"]+)"')
    d: dict[str, str] = {}
    for m in pat.finditer(text):
        pid, name = m.group(1), m.group(2)
        norm = normalize(name)
        if norm:
            d[norm] = pid
    for pid, aliases in ALIASES.items():
        for alias in aliases:
            d[normalize(alias)] = pid
    return d


# ── メイン ────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="API呼び出しなし")
    parser.add_argument("--test",    action="store_true", help="第221回のみ")
    args = parser.parse_args()

    name_to_pid = build_name_dict()
    out(f"照合辞書: {len(name_to_pid)}件")

    sponsor_counts:   collections.Counter = collections.Counter()
    supporter_counts: collections.Counter = collections.Counter()
    # 院別内訳
    shu_sponsor: collections.Counter = collections.Counter()
    san_sponsor: collections.Counter = collections.Counter()

    unmatched: collections.Counter = collections.Counter()
    errors: list[str] = []

    total_shu_bills = 0
    total_san_bills = 0
    total_shu_matched = 0
    total_san_matched = 0
    # 継続審議で同一 keika URL が複数会期の一覧に載るため全セッション横断で重複排除
    processed_keika_urls: set[str] = set()

    sessions = [221] if args.test else SESSIONS

    for session in sessions:
        out(f"\n{'='*52}")
        out(f"=== 第{session}回国会 ===")

        # ── 衆議院 ──────────────────────────────────────────
        list_url = SHUGIIN_LIST_URL.format(n=session)
        out(f"\n[衆議院] {list_url}")

        if args.dry_run:
            out(f"  [DRY-RUN] skip")
        else:
            html = fetch_html(list_url, encoding='shift_jis')
            time.sleep(SLEEP)

            if not html:
                msg = f"第{session}回 衆議院一覧: 取得失敗"
                out(f"  ✗ {msg}")
                errors.append(msg)
            else:
                keika_urls = extract_shugiin_keika_urls(html)
                # 継続審議による重複を排除（同一 URL は初出会期のみ処理）
                new_keika_urls = [u for u in keika_urls if u not in processed_keika_urls]
                skipped = len(keika_urls) - len(new_keika_urls)
                out(f"  衆法件数: {len(keika_urls)}（継続審議除く新規: {len(new_keika_urls)}件）")
                total_shu_bills += len(new_keika_urls)

                for i, kurl in enumerate(new_keika_urls, 1):
                    processed_keika_urls.add(kurl)
                    page = fetch_html(kurl, encoding='shift_jis')
                    if not page:
                        errors.append(f"第{session}回 衆法 keika取得失敗: {kurl}")
                        time.sleep(SLEEP)
                        continue

                    # 閣法（内閣提出）が衆法セクションに混入した場合はスキップ
                    if re.search(r'<TITLE>\s*閣法', page, re.IGNORECASE):
                        out(f"  [{i:3d}] 閣法ページ → スキップ: {kurl.split('/')[-1]}")
                        time.sleep(SLEEP)
                        continue

                    data = parse_keika_page(page)
                    label = (
                        f"第{data['session']}回衆法第{data['bill_no']}号"
                        if data['session'] else f"({kurl.split('/')[-1]})"
                    )

                    for name in data['sponsors']:
                        pid = name_to_pid.get(name)
                        if pid:
                            sponsor_counts[pid] += 1
                            shu_sponsor[pid]    += 1
                            total_shu_matched   += 1
                        else:
                            unmatched[f"[衆発議]{name}"] += 1

                    for name in data['supporters']:
                        pid = name_to_pid.get(name)
                        if pid:
                            supporter_counts[pid] += 1
                        # 未照合賛成者は報告不要（引退議員が大量）

                    out(
                        f"  [{i:3d}] {label}: "
                        f"発議者{len(data['sponsors'])}名"
                        f" 賛成者{len(data['supporters'])}名"
                    )
                    time.sleep(SLEEP)

        # ── 参議院 ──────────────────────────────────────────
        san_url = SANGIIN_LIST_URL.format(n=session)
        out(f"\n[参議院] {san_url}")

        if args.dry_run:
            out(f"  [DRY-RUN] skip")
        else:
            html = fetch_html(san_url)
            time.sleep(SLEEP)

            if not html:
                msg = f"第{session}回 参議院一覧: 取得失敗"
                out(f"  ✗ {msg}")
                errors.append(msg)
            else:
                meisai_urls = extract_sangiin_meisai_urls(html, session)
                out(f"  参法件数: {len(meisai_urls)}")
                total_san_bills += len(meisai_urls)

                for i, murl in enumerate(meisai_urls, 1):
                    page = fetch_html(murl)
                    if not page:
                        errors.append(f"第{session}回 参法 meisai取得失敗: {murl}")
                        time.sleep(SLEEP)
                        continue

                    data = parse_meisai_page(page)
                    name = data['main_sponsor']
                    co   = data['co_sponsor_count']

                    if name:
                        pid = name_to_pid.get(name)
                        if pid:
                            sponsor_counts[pid] += 1
                            san_sponsor[pid]    += 1
                            total_san_matched   += 1
                        else:
                            unmatched[f"[参発議]{name}"] += 1
                        extra = f"外{co}名" if co else "単独"
                        out(f"  [{i:3d}] 参法{i:03d}: {name}（{extra}）")
                    else:
                        out(f"  [{i:3d}] 参法{i:03d}: 発議者を取得できず")

                    time.sleep(SLEEP)

    if args.dry_run:
        out("\n[DRY-RUN] 完了（ファイル更新なし）")
        return

    # ── facts.json 更新 ──────────────────────────────────────
    with open(FACTS_PATH, encoding='utf-8') as f:
        facts = json.load(f)

    period_str = (
        "第221回国会"
        if args.test
        else f"第{FROM_SESSION}回〜第{UNTIL_SESSION}回国会"
    )

    for pid in facts:
        facts[pid]["bill_sponsor_count"]   = sponsor_counts.get(pid, 0)
        facts[pid]["bill_supporter_count"] = supporter_counts.get(pid, 0)
        facts[pid]["bill_period"]          = period_str

    # facts に存在しない pid（引退議員へのマッチ念のため無視）
    for pid in sponsor_counts:
        if pid not in facts:
            facts[pid] = {
                "bill_sponsor_count":   sponsor_counts[pid],
                "bill_supporter_count": supporter_counts.get(pid, 0),
                "bill_period":          period_str,
            }

    with open(FACTS_PATH, "w", encoding='utf-8') as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)

    # ── サマリ出力 ────────────────────────────────────────────
    out(f"\n{'='*52}")
    out("## 完了サマリ")
    out(f"| 項目 | 値 |")
    out(f"|------|-----|")
    out(f"| 衆法 一覧ページ | {len(sessions)}回次 / ユニーク {total_shu_bills} 件（重複除く） |")
    out(f"| 参法 一覧ページ | {len(sessions)}回次 / 合計 {total_san_bills} 件 |")
    out(f"| 参法 照合成功  | {total_san_matched}/{total_san_bills} |")
    out(f"| bill_sponsor_count 更新 | {len(sponsor_counts)} 名 |")
    out(f"| bill_supporter_count 更新 | {len(supporter_counts)} 名 |")
    out(f"| エラー | {len(errors)} 件 |")
    out(f"| 未照合名（発議者） | {len(unmatched)} 件 |")

    out("\n## 発議件数 上位20名")
    out("| 氏名 | ID | 衆法 | 参法 | 合計 |")
    out("|------|-----|------|------|------|")
    for pid, count in sorted(sponsor_counts.items(), key=lambda x: -x[1])[:20]:
        name = facts.get(pid, {}).get('name', pid)
        shu  = shu_sponsor.get(pid, 0)
        san  = san_sponsor.get(pid, 0)
        out(f"| {name} | {pid} | {shu} | {san} | {count} |")

    out("\n## 照合できなかった発議者名（上位40件）")
    out("```")
    for name, cnt in unmatched.most_common(40):
        out(f"  {name}: {cnt}件")
    out("```")

    if unmatched:
        with open(UNMATCHED, "w", encoding='utf-8') as f:
            for name, cnt in unmatched.most_common():
                f.write(f"{name}\t{cnt}\n")
        out(f"\n全未照合リスト → {UNMATCHED}")

    if errors:
        with open(ERROR_LOG, "a", encoding='utf-8') as f:
            for e in errors:
                f.write(e + "\n")
        out("\n## エラー")
        for e in errors:
            out(f"  - {e}")


if __name__ == "__main__":
    main()
