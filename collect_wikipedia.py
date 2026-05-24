#!/usr/bin/env python3
"""
統覧 TORAN — Wikipedia 基本情報収集スクリプト
================================================
使い方:
  1. politicians_names.txt に1行1名で氏名を書く（例: 高市早苗）
  2. pip install requests openpyxl  （初回のみ）
  3. python collect_wikipedia.py
  4. 出力: output/politicians_basic.json

Excelファイルから読む場合は --excel オプションを使用:
  python collect_wikipedia.py --excel 名前リスト.xlsx --col A --start 2
"""

import requests
import json
import re
import time
import argparse
import os
from datetime import date

# ─── 設定 ───────────────────────────────────────────────
WIKIPEDIA_API = "https://ja.wikipedia.org/w/api.php"
DELAY = 0.5          # リクエスト間隔（秒）— Wikipediaの利用規約に従い0.5秒以上推奨
OUTPUT_DIR = "output"
# ────────────────────────────────────────────────────────

PARTY_ALIASES = {
    "自由民主党": "自民党",
    "自由民主党 (日本)": "自民党",
    "立憲民主党 (日本)": "立憲民主党",
    "日本維新の会 (2015-)": "日本維新の会",
    "公明党": "公明党",
    "国民民主党 (日本 2018-)": "国民民主党",
    "日本共産党": "日本共産党",
    "れいわ新選組": "れいわ新選組",
    "参政党": "参政党",
    "社会民主党 (日本)": "社民党",
}


def normalize_party(raw: str) -> str:
    """[[自由民主党 (日本)|自由民主党]] → 自民党"""
    # [[X|Y]] → Y
    m = re.search(r'\[\[.*?\|(.*?)\]\]', raw)
    if m:
        name = m.group(1).strip()
    else:
        # [[X]] → X
        m2 = re.search(r'\[\[(.*?)\]\]', raw)
        name = m2.group(1).strip() if m2 else raw.strip()
    # HTML/wikitextタグを除去
    name = re.sub(r'<.*?>', '', name)
    name = re.sub(r'\{\{.*?\}\}', '', name)
    name = name.strip()
    return PARTY_ALIASES.get(name, name)


def extract_birth_year(raw: str) -> int | None:
    """{{生年月日と年齢|1961|3|7}} → 1961"""
    m = re.search(r'\|(\d{4})\|', raw)
    return int(m.group(1)) if m else None


def calc_age(birth_year: int | None) -> int | None:
    if birth_year is None:
        return None
    return date.today().year - birth_year


def clean_wikitext(text: str) -> str:
    """WikitextからHTMLタグ・リンク・テンプレートを除去"""
    text = re.sub(r'\[\[.*?\|(.*?)\]\]', r'\1', text)
    text = re.sub(r'\[\[(.*?)\]\]', r'\1', text)
    text = re.sub(r'\{\{.*?\}\}', '', text)
    text = re.sub(r"'{2,}", '', text)
    text = re.sub(r'<.*?>', '', text)
    return text.strip()


def parse_infobox(content: str) -> dict:
    """Wikitext の {{政治家}} インフォボックスを解析"""
    result = {}

    # インフォボックスを抽出（ネストした {{ }} を考慮）
    start = content.find('{{政治家')
    if start == -1:
        # 別名テンプレートも試す
        for alt in ['{{Infobox 政治家', '{{Politician', '{{政治家情報']:
            start = content.find(alt)
            if start != -1:
                break
    if start == -1:
        return result

    # 対応する }} を探す
    depth = 0
    end = start
    for i in range(start, min(start + 8000, len(content))):
        if content[i:i+2] == '{{':
            depth += 1
            end = i
        elif content[i:i+2] == '}}':
            depth -= 1
            if depth == 0:
                end = i + 2
                break
    infobox = content[start:end]

    # フィールド抽出
    fields = {}
    for line in infobox.split('\n'):
        m = re.match(r'\|\s*(.+?)\s*=\s*(.*)', line)
        if m:
            fields[m.group(1).strip()] = m.group(2).strip()

    # よみ
    for key in ['読み', 'ふりがな', 'yomi']:
        if key in fields and fields[key]:
            reading = clean_wikitext(fields[key])
            reading = reading.replace('　', '').replace(' ', '')
            result['reading'] = reading
            break

    # 所属政党
    for key in ['所属政党', '政党', 'party']:
        if key in fields and fields[key]:
            result['party'] = normalize_party(fields[key])
            break

    # 選挙区
    for key in ['選挙区', '選挙区・選出']:
        if key in fields and fields[key]:
            district = clean_wikitext(fields[key])
            # 第X区を短縮
            district = re.sub(r'第(\d+)区', r'\1区', district)
            result['district'] = district
            break

    # 生年月日
    for key in ['生年月日', '誕生日']:
        if key in fields and fields[key]:
            by = extract_birth_year(fields[key])
            result['birth_year'] = by
            result['age'] = calc_age(by)
            break

    # 性別
    for key in ['性別', 'gender']:
        if key in fields and fields[key]:
            g = fields[key]
            result['gender'] = '女' if '女' in g or 'female' in g.lower() else '男'
            break

    # 役職（職名/称号）
    for key in ['職名', '役職']:
        if key in fields and fields[key]:
            role = clean_wikitext(fields[key])
            if role:
                result['role'] = role
                break

    return result


def detect_chamber(content: str, name: str) -> str:
    """記事内容から院を判定"""
    if re.search(r'衆議院議員|衆院|小選挙区|比例代表.*衆', content):
        if re.search(r'参議院議員|参院', content):
            # 両方ある → 現職で判断
            if '衆議院議員' in content[:500]:
                return '衆議院'
            return '参議院'
        return '衆議院'
    if re.search(r'参議院議員|参院議員', content):
        return '参議院'
    if re.search(r'知事|都知事|府知事|道知事|県知事', content):
        return '首長'
    if re.search(r'市長|町長|村長', content):
        return '首長'
    return '衆議院'  # デフォルト


def get_wikipedia_data(name: str) -> dict | None:
    """Wikipedia APIから政治家情報を取得"""
    params = {
        "action": "query",
        "titles": name,
        "prop": "revisions|categories",
        "rvprop": "content",
        "rvslots": "main",
        "cllimit": "50",
        "format": "json",
        "formatversion": "2",
    }
    try:
        r = requests.get(WIKIPEDIA_API, params=params, timeout=15,
                        headers={"User-Agent": "TORAN-DataCollector/1.0 (educational project)"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  ⚠️  通信エラー: {e}")
        return None

    pages = data.get("query", {}).get("pages", [])
    if not pages:
        return None
    page = pages[0]

    if "missing" in page:
        print(f"  ❌ Wikipedia記事なし: {name}")
        return None

    content = ""
    try:
        content = page["revisions"][0]["slots"]["main"]["content"]
    except (KeyError, IndexError):
        return None

    # インフォボックス解析
    info = parse_infobox(content)

    # 院を判定
    info["chamber"] = detect_chamber(content, name)

    # カテゴリから性別・院を補強
    categories = [c.get("title", "") for c in page.get("categories", [])]
    for cat in categories:
        if "女性" in cat:
            info["gender"] = "女"
        if "衆議院議員" in cat:
            info["chamber"] = "衆議院"
        if "参議院議員" in cat:
            info.setdefault("chamber", "参議院")

    return info


def make_politician_entry(idx: int, name: str, wiki: dict | None) -> dict:
    """POLITICIANS配列の1エントリを生成"""
    pid = f"P{idx:03d}"
    entry = {
        "id": pid,
        "name": name,
        "reading": wiki.get("reading", "（要入力）") if wiki else "（要入力）",
        "party": wiki.get("party", "（要入力）") if wiki else "（要入力）",
        "role": wiki.get("role", "（要入力）") if wiki else "（要入力）",
        "chamber": wiki.get("chamber", "衆議院") if wiki else "（要入力）",
        "district": wiki.get("district", "（要入力）") if wiki else "（要入力）",
        "status": "現職",
        "gender": wiki.get("gender", "男") if wiki else "（要入力）",
        "age": wiki.get("age") if wiki else None,
        # ── スコア（AIで入力）──
        "total": 0,
        "rank": "未評価",
        "axes": [0, 0, 0, 0, 0, 0, 0, 0],
        "stances": {k: "△" for k in [
            "tax_cut","active_fiscal","discipline","defense","econ_sec",
            "immigration","renewable","nuclear","expo","ir","mynumber",
            "birthrate","education","regional","china","foreign","food","semi"
        ]},
        "plus": "（AI評価待ち）",
        "minus": "（AI評価待ち）",
        "comment": "（AI評価待ち）",
        "flag_crime": False,
        "flag_caution": False,
        "updated": date.today().strftime("%Y.%m"),
        "survey": "基本情報収集済",
        "wiki_ok": wiki is not None,
    }
    return entry


def load_names_from_txt(path: str) -> list[str]:
    with open(path, encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]


def load_names_from_excel(path: str, col: str = 'A', start_row: int = 2) -> list[str]:
    try:
        import openpyxl
    except ImportError:
        raise SystemExit("openpyxl が必要です: pip install openpyxl")
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    col_idx = ord(col.upper()) - ord('A') + 1
    names = []
    for row in ws.iter_rows(min_row=start_row):
        cell = row[col_idx - 1]
        if cell.value:
            names.append(str(cell.value).strip())
    return names


def main():
    parser = argparse.ArgumentParser(description='Wikipedia から政治家基本情報を収集')
    parser.add_argument('--names', default='politicians_names.txt', help='名前リストTXTファイル')
    parser.add_argument('--excel', help='Excelファイルパス（--namesの代わりに使用）')
    parser.add_argument('--col', default='A', help='Excel列名（デフォルト: A）')
    parser.add_argument('--start', type=int, default=2, help='Excel開始行（デフォルト: 2）')
    parser.add_argument('--offset', type=int, default=1, help='ID開始番号（デフォルト: 1）')
    parser.add_argument('--out', default='output/politicians_basic.json', help='出力ファイル')
    args = parser.parse_args()

    # 名前リスト読み込み
    if args.excel:
        print(f"📂 Excelから読み込み: {args.excel} 列{args.col} {args.start}行目〜")
        names = load_names_from_excel(args.excel, args.col, args.start)
    elif os.path.exists(args.names):
        print(f"📂 テキストから読み込み: {args.names}")
        names = load_names_from_txt(args.names)
    else:
        # サンプルで実行
        print("⚠️  politicians_names.txt が見つかりません。サンプル10名で実行します。")
        names = ["高市早苗","石破茂","玉木雄一郎","吉村洋文","山本太郎",
                 "河野太郎","野田佳彦","蓮舫","小池百合子","岸田文雄"]

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    print(f"\n🔍 {len(names)}名の基本情報をWikipediaから収集します\n")

    results = []
    ok_count = 0
    ng_count = 0

    for i, name in enumerate(names, start=args.offset):
        print(f"[{i:03d}/{len(names)+args.offset-1}] {name} ... ", end='', flush=True)
        wiki = get_wikipedia_data(name)

        if wiki:
            entry = make_politician_entry(i, name, wiki)
            ok_count += 1
            fields_found = [k for k in ['reading','party','chamber','district','age','gender'] if wiki.get(k)]
            print(f"✅ ({', '.join(fields_found)})")
        else:
            entry = make_politician_entry(i, name, None)
            ng_count += 1
            print("❌ 取得失敗（手動入力が必要）")

        results.append(entry)
        time.sleep(DELAY)

    # 出力
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完了: {ok_count}名取得成功 / {ng_count}名失敗")
    print(f"📄 出力: {args.out}")
    print(f"\n次のステップ:")
    print(f"  → AIプロンプトで scores / stances / evidence を追加 (15名ずつ)")
    print(f"  → merge_batches.py で data.js に統合")


if __name__ == "__main__":
    main()
