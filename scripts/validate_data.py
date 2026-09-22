#!/usr/bin/env python3
"""data.js 整合性チェック — CI で実行

評価点（total）は 8軸（axes）の合計から算出される。裏付け evidence を持たない
議員は 2026.09.22 以降 total/rank/axes をブランクにしているため、
「点がある議員」と「ブランクの議員」の両方を、それぞれの不変条件で検査する。
"""
import re, sys

def calc_rank(total):
    if total >= 90: return "S"
    if total >= 87: return "A+"
    if total >= 83: return "A"
    if total >= 80: return "A-"
    if total >= 77: return "B+"
    if total >= 73: return "B"
    if total >= 70: return "B-"
    if total >= 67: return "C+"
    if total >= 63: return "C"
    if total >= 60: return "C-"
    return "D"

data = open('data.js', encoding='utf-8').read()

# POLITICIANS の範囲だけを対象にする。EVIDENCE の pid:"Pxxx" は
# id:"Pxxx" を部分文字列として含むため、範囲を切らないと誤検出する。
_start = data.index('const POLITICIANS = [')
_end = data.index('const EVIDENCE = [')
data = data[_start:_end]

# 議員レコードを id:"Pxxx" 単位に切り出す（DOTALL の .*? はレコードを
# またいで誤マッチしうるため、明示的に分割する）
starts = [m.start() for m in re.finditer(r'(?<![A-Za-z])id:"P\d+",', data)]
records = []
for i, s in enumerate(starts):
    e = starts[i + 1] if i + 1 < len(starts) else len(data)
    records.append(data[s:e])

field = lambda rec, pat: (re.search(pat, rec) or [None, None])[1]

errors = []
scored = 0
blank = 0

for rec in records:
    pid = field(rec, r'id:"(P\d+)"')
    total_s = field(rec, r'total:\s*(null|\d+)')
    rank = field(rec, r'rank:"([^"]*)"')
    axes_s = field(rec, r'axes:\s*(null|\[[^\]]*\])')
    survey = field(rec, r'survey:"([^"]*)"')

    if total_s is None or rank is None or axes_s is None:
        errors.append(f"  {pid}: total/rank/axes のいずれかが読み取れません")
        continue

    # --- ブランク（裏付けなし）のレコード ---
    if total_s == 'null':
        blank += 1
        if rank != "":
            errors.append(f'  {pid}: total=null なのに rank="{rank}" が残っています')
        if axes_s != 'null':
            errors.append(f"  {pid}: total=null なのに axes が残っています")
        if survey != '未評価':
            errors.append(f'  {pid}: total=null なのに survey="{survey}"（"未評価" であるべき）')
        continue

    # --- 評価点を持つレコード ---
    if survey != '評価済':
        errors.append(f'  {pid}: total={total_s} なのに survey="{survey}"（"評価済" であるべき）')
        continue
    scored += 1
    total = int(total_s)
    axes = [int(x.strip()) for x in axes_s.strip('[]').split(',')]
    axes_sum = sum(axes)
    expected_total = int(axes_sum * 100 / 40)
    expected_rank = calc_rank(total)

    if total != expected_total:
        errors.append(
            f"  {pid}: total={total} (axes sum={axes_sum} → expected {expected_total})"
        )
    if rank != expected_rank:
        errors.append(
            f'  {pid}: rank="{rank}" total={total} → expected "{expected_rank}"'
        )

print(f"議員レコード {len(records)}件 — 評価点あり {scored}件 / ブランク {blank}件")

if errors:
    print(f"\n❌ 不整合 {len(errors)}件:\n" + "\n".join(errors))
    sys.exit(1)

print("✅ total/rank/axes 整合性 OK")
