#!/usr/bin/env python3
"""
統覧 TORAN — JS埋め込みデータ生成スクリプト
==========================================
output/politicians_base.json → politicians.html の POLITICIANS/EVIDENCE 配列を更新
"""

import json, os, re

BASE_FILE = 'output/politicians_base.json'
POLITICIANS_HTML = 'politicians.html'
POLITICIAN_HTML = 'politician.html'

def fmt_val(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, (int, float)):
        return str(v)
    if v is None:
        return 'null'
    return json.dumps(v, ensure_ascii=False)

def politician_to_js(p):
    axes = p.get('axes', [0]*8)
    stances = p.get('stances', {})
    stance_keys = ['tax_cut','active_fiscal','discipline','defense','econ_sec',
                   'immigration','renewable','nuclear','expo','ir','mynumber',
                   'birthrate','education','regional','china','foreign','food','semi']

    stances_js = '{' + ','.join(f"{k}:{fmt_val(stances.get(k,'△'))}" for k in stance_keys) + '}'
    axes_js = '[' + ','.join(str(a) for a in axes) + ']'

    links = p.get('links', {})
    if not links:
        links = {'hp':'','tw':'','yt':'','wiki':''}
    links_js = '{' + ','.join(f"{k}:{fmt_val(v)}" for k,v in links.items()) + '}'

    return (
        f"  {{\n"
        f"    id:{fmt_val(p['id'])}, name:{fmt_val(p['name'])}, reading:{fmt_val(p.get('reading',''))}, "
        f"party:{fmt_val(p.get('party',''))}, role:{fmt_val(p.get('role',''))},\n"
        f"    chamber:{fmt_val(p.get('chamber',''))}, district:{fmt_val(p.get('district',''))}, "
        f"status:{fmt_val(p.get('status','現職'))}, gender:{fmt_val(p.get('gender','男'))}, age:{fmt_val(p.get('age'))},\n"
        f"    total:{p.get('total',0)}, rank:{fmt_val(p.get('rank','未評価'))},\n"
        f"    axes:{axes_js},\n"
        f"    stances:{stances_js},\n"
        f"    plus:{fmt_val(p.get('plus',''))}, minus:{fmt_val(p.get('minus',''))},\n"
        f"    comment:{fmt_val(p.get('comment',''))},\n"
        f"    links:{links_js},\n"
        f"    flag_crime:{fmt_val(p.get('flag_crime',False))}, flag_caution:{fmt_val(p.get('flag_caution',False))}, "
        f"updated:{fmt_val(p.get('updated',''))}, survey:{fmt_val(p.get('survey','未評価'))}\n"
        f"  }}"
    )

def evidence_to_js(e):
    return (
        f"  {{"
        f"id:{fmt_val(e.get('id',''))}, pid:{fmt_val(e.get('pid',''))}, "
        f"cat:{fmt_val(e.get('cat',''))}, sub:{fmt_val(e.get('sub',''))}, "
        f"summary:{fmt_val(e.get('summary',''))}, "
        f"detail:{fmt_val(e.get('detail',''))}, "
        f"src:{fmt_val(e.get('src',''))}, url:{fmt_val(e.get('url',''))}, "
        f"rel:{fmt_val(e.get('rel',''))}, impact:{fmt_val(e.get('impact',''))}, "
        f"date:{fmt_val(e.get('date',''))}"
        f"}}"
    )

def main():
    with open(BASE_FILE, encoding='utf-8') as f:
        politicians = json.load(f)

    print(f"📂 読み込み: {len(politicians)}名")

    # POLITICIANS JS配列を生成
    pols_js_entries = [politician_to_js(p) for p in politicians]
    politicians_js = "const POLITICIANS = [\n" + ",\n".join(pols_js_entries) + "\n];"

    # EVIDENCE を全政治家から収集
    ev_counter = 1
    evidence_items = []
    for p in politicians:
        for ev in p.get('evidence', []):
            ev_copy = dict(ev)
            ev_copy['pid'] = p['id']
            if 'id' not in ev_copy or not ev_copy['id']:
                ev_copy['id'] = f"E{ev_counter:04d}"
            ev_counter += 1
            evidence_items.append(ev_copy)

    evidence_js = "const EVIDENCE = [\n" + ",\n".join(evidence_to_js(e) for e in evidence_items) + "\n];"

    print(f"📋 根拠: {len(evidence_items)}件")

    # politicians.html を更新
    for html_file in [POLITICIANS_HTML, POLITICIAN_HTML]:
        if not os.path.exists(html_file):
            print(f"  ⚠️ {html_file} が見つかりません → スキップ")
            continue

        with open(html_file, encoding='utf-8') as f:
            content = f.read()

        # POLITICIANS配列を置換
        content = re.sub(
            r'const POLITICIANS = \[.*?\];',
            politicians_js,
            content, flags=re.DOTALL
        )
        # EVIDENCE配列を置換
        content = re.sub(
            r'const EVIDENCE = \[.*?\];',
            evidence_js,
            content, flags=re.DOTALL
        )

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"  ✅ {html_file} 更新完了")

    print("\n✅ 完了！")

if __name__ == '__main__':
    main()
