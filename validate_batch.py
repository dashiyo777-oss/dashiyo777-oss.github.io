#!/usr/bin/env python3
"""
統覧 TORAN — バッチ検証スクリプト
=====================================
バッチJSONをマージ前に検証し、ハルシネーションの疑いがある
エントリを警告します。

使い方（単体実行）:
  python validate_batch.py batches/batch_011_P151-P165.json

merge_batches.py からも自動呼び出しされます。
"""

import json, re, sys

# ── 既知の政治家名・愛称・フレーズ（別人データ混入の手がかり） ──
KNOWN_POLITICIANS = [
    '高市早苗', '岸田文雄', '菅義偉', '安倍晋三', '安倍 晋三',
    '河野太郎', '小泉進次郎', '石破茂', '泉健太', '橋下徹',
    '松井一郎', '吉村洋文', '枝野幸男', '前原誠司', '野田佳彦',
    '麻生太郎', '二階俊博', '茂木敏充', '林芳正', '西村康稔',
    '加藤勝信', '木原誠二', '木原稔', '斉藤鉄夫', '北側一雄',
    '山口那津男', '河村たかし', '小林鷹之', '北神圭朗',
    '小渕恵三', '福田康夫', '鳩山由紀夫', '菅直人',
]

KNOWN_NICKNAMES = [
    'コバホーク', 'サナエノミクス', 'アベノミクス',
    '令和の鉄の天井', '庶民革命',
]

# 代名詞+代目の組み合わせ（首相代数）と正当な持ち主
PM_NUMBERS = {
    '第90代': '安倍晋三', '第96代': '安倍晋三',
    '第97代': '安倍晋三', '第98代': '安倍晋三',
    '第99代': '菅義偉',
    '第100代': '岸田文雄', '第101代': '岸田文雄',
    '第102代': '石破茂',  '第103代': '石破茂',
}

# 固有施策フレーズ → 本来の持ち主ID or 名前
POLICY_PHRASES = {
    'デジタル庁創設':           '菅義偉',
    '不妊治療の保険適用':       '菅義偉',
    'G7広島サミット':           '岸田文雄',
    'ふるさと納税のルール厳格化': None,   # 菅義偉かもしれないが複数いる
    '名古屋市長':               '河村たかし',
    '名古屋での独自の減税':     '河村たかし',
    '市民税一律減税':           '河村たかし',
    '経済安全保障推進法.*初代担当': '小林鷹之',
    'コバホーク.*愛称':         '小林鷹之',
    '広島サミット.*議長':       '岸田文雄',
    '宏池会.*解散':             '岸田文雄',
    '防衛費.*GDP比2%':          '岸田文雄',
    '次期戦闘機.*GIGO':        '木原稔',
    '官房副長官.*こども未来戦略': '木原誠二',
    '携帯料金.*値下げ':         '菅義偉',
}

# 役職と政党の組み合わせが明らかにおかしいケース
PARTY_ROLE_MISMATCH = {
    '共産党': ['自民党', '自由民主党'],
    '日本維新の会': [],  # 大臣経験者が一部いるので緩め
}


def load_base(base_file='output/politicians_base.json'):
    try:
        with open(base_file, encoding='utf-8') as f:
            data = json.load(f)
        return {p['id']: p for p in data}
    except FileNotFoundError:
        return {}


def check_entry(item, base_map):
    """
    バッチの1エントリを検証し、警告リストを返す。
    警告は (level, message) のタプル。
      level: 'ERROR' = ほぼ確実に別人 / 'WARN' = 要注意
    """
    warnings = []
    pid  = item.get('id', '?')
    base = base_map.get(pid)

    if base is None:
        warnings.append(('ERROR', f'{pid} はベースJSONに存在しません'))
        return warnings

    base_name  = base.get('name', '')
    base_party = base.get('party', '')
    item_text  = ' '.join([
        item.get('plus', ''),
        item.get('minus', ''),
        item.get('comment', ''),
        item.get('role', ''),
        ' '.join(e.get('summary','') + ' ' + e.get('detail','')
                 for e in item.get('evidence', [])),
    ])

    # ── Check 1: 他の政治家の本名が混入していないか ──
    for name in KNOWN_POLITICIANS:
        # ベースの人物名と一致する場合はスキップ
        if name in base_name or base_name in name:
            continue
        if name in item_text:
            warnings.append(('ERROR',
                f'別政治家「{name}」の名前がテキストに含まれています'))

    # ── Check 2: 愛称・造語が混入していないか ──
    for nick in KNOWN_NICKNAMES:
        if nick in item_text:
            # 当人が持つ愛称かチェック（河村たかしの「庶民革命」など）
            if nick == '庶民革命' and '河村' in base_name:
                continue
            warnings.append(('ERROR',
                f'別人固有の愛称・フレーズ「{nick}」が含まれています'))

    # ── Check 3: 首相代数が混入していないか ──
    base_name_ns = base_name.replace(' ', '').replace('　', '')  # スペース除去
    for pm_num, pm_name in PM_NUMBERS.items():
        if pm_num in item_text:
            pm_name_ns = pm_name.replace(' ', '').replace('　', '')
            if pm_name_ns not in base_name_ns and base_name_ns not in pm_name_ns:
                warnings.append(('ERROR',
                    f'首相代数「{pm_num}」は{pm_name}のデータです（{base_name}に使用）'))

    # ── Check 4: 固有施策フレーズが混入していないか ──
    for phrase, owner in POLICY_PHRASES.items():
        if re.search(phrase, item_text):
            if owner is None:
                continue  # ownerが未定義 → 警告しない
            # スペース除去で比較（「河村 たかし」vs「河村たかし」対応）
            owner_ns   = owner.replace(' ', '').replace('　', '')
            base_ns    = base_name.replace(' ', '').replace('　', '')
            if owner_ns in base_ns or base_ns in owner_ns:
                continue  # 本人のデータ → スキップ
            warnings.append(('ERROR',
                f'「{phrase}」は{owner}固有の実績です（{base_name}に使用）'))

    # ── Check 5: roleに内閣総理大臣があるが持ち主ではない ──
    item_role = item.get('role', '')
    if '内閣総理大臣' in item_role or '総理大臣' in item_role:
        # 歴代首相の姓リスト
        pm_surnames = ['石破', '岸田', '菅', '安倍', '福田', '鳩山', '野田', '小泉', '森', '橋本', '村山', '宮沢']
        is_pm = any(s in base_name for s in pm_surnames)
        if not is_pm:
            warnings.append(('ERROR',
                f'role に「内閣総理大臣」がありますが {base_name} は首相経験者ではありません'))

    # ── Check 6: 政党矛盾（コメントで別党のものと言っている） ──
    if base_party == '日本共産党' and '自民党' in item_text:
        warnings.append(('WARN',
            f'共産党議員のテキストに「自民党」への言及（{base_name}）'))
    if base_party in ['日本維新の会', '維新'] and '自民党期待' in item_text:
        warnings.append(('WARN',
            f'維新議員のテキストに「自民党期待」（{base_name}）'))

    # ── Check 7: 旧政権名義ミスマッチ ──
    if '旧民主党政権で首相補佐官' in item_text and base_party == '自民党':
        warnings.append(('WARN',
            f'自民党議員なのに「旧民主党政権で首相補佐官」とある（{base_name}）'))

    # ── Check 8: axes スコア過剰（情報不足なのに高スコア） ──
    axes = item.get('axes', [])
    if axes and item.get('survey') == '情報不足':
        if sum(axes) >= 32:  # 40点満点で32点超（8割）
            warnings.append(('WARN',
                f'survey=情報不足 なのに axes合計={sum(axes)}/40 は高すぎます'))

    # ── Check 9: surveyフィールドが抜けている ──
    if 'survey' not in item:
        warnings.append(('WARN', f'survey フィールドがありません（自動で補完されます）'))

    return warnings


def validate_batch(batch_file, base_map=None, silent=False):
    """
    バッチファイルを検証する。
    戻り値: (ok件数, warn件数, error件数)
    """
    if base_map is None:
        base_map = load_base()

    with open(batch_file, encoding='utf-8') as f:
        batch = json.load(f)

    ok_count    = 0
    warn_count  = 0
    error_count = 0

    if not silent:
        print(f'\n🔍 検証: {batch_file} ({len(batch)}件)')

    for item in batch:
        pid = item.get('id', '?')
        base = base_map.get(pid, {})
        name = base.get('name', '?')
        warnings = check_entry(item, base_map)

        errors = [w for w in warnings if w[0] == 'ERROR']
        warns  = [w for w in warnings if w[0] == 'WARN']

        if errors:
            error_count += 1
            if not silent:
                print(f'  🚨 {pid} {name}')
                for _, msg in errors:
                    print(f'      ERROR: {msg}')
                for _, msg in warns:
                    print(f'      WARN:  {msg}')
        elif warns:
            warn_count += 1
            if not silent:
                print(f'  ⚠️  {pid} {name}')
                for _, msg in warns:
                    print(f'      WARN: {msg}')
        else:
            ok_count += 1
            if not silent:
                print(f'  ✅  {pid} {name}')

    if not silent:
        print(f'\n  結果: ✅OK={ok_count}  ⚠️WARN={warn_count}  🚨ERROR={error_count}')
        if error_count > 0:
            print(f'  ❌ ERRORが{error_count}件あります。マージ前に内容を確認してください。')
        elif warn_count > 0:
            print(f'  ⚠️  WARNが{warn_count}件あります。念のため確認してください。')
        else:
            print(f'  ✅ 問題なし。マージを続行できます。')

    return ok_count, warn_count, error_count


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('使い方: python validate_batch.py <batch_file.json>')
        sys.exit(1)
    base_map = load_base()
    ok, warn, err = validate_batch(sys.argv[1], base_map)
    sys.exit(1 if err > 0 else 0)
