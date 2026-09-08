#!/usr/bin/env node
// politicians_base.json（CSVエクスポートの元データ）が data.js（サイト正本）と
// 同期しているかを検証する。乖離があれば exit 1。
//
// 背景: 2026-05-24に手動アップロードされた politicians_base.json が data.js の
// その後の修正（[ ]付き参院エントリ43件の解決など）を取り込まず、CSVに
// プレースホルダー・重複レコードが露出した（2026-09-09 訂正対応）。
// 再発防止として、両者の ID集合と主要フィールドの一致をCIで強制する。
//
// 使い方: node scripts/validate_base_sync.js

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const dataJs = fs.readFileSync(path.join(ROOT, 'data.js'), 'utf8');
const POLITICIANS = vm.runInNewContext(dataJs + ';POLITICIANS', {});
const base = JSON.parse(fs.readFileSync(path.join(ROOT, 'politicians_base.json'), 'utf8'));

const FIELDS = ['name', 'reading', 'party', 'role', 'chamber', 'district', 'status', 'total', 'rank'];
const errors = [];

const baseById = new Map(base.map((p) => [p.id, p]));
const dataById = new Map(POLITICIANS.map((p) => [p.id, p]));

for (const id of dataById.keys()) {
  if (!baseById.has(id)) errors.push(`politicians_base.json に ${id} がありません（data.jsには存在）`);
}
for (const id of baseById.keys()) {
  if (!dataById.has(id)) errors.push(`politicians_base.json に余分な ${id} があります（data.jsに存在しない）`);
}
for (const [id, d] of dataById) {
  const b = baseById.get(id);
  if (!b) continue;
  for (const f of FIELDS) {
    if (String(b[f] ?? '') !== String(d[f] ?? '')) {
      errors.push(`${id} の ${f} が不一致: base="${b[f]}" data.js="${d[f]}"`);
    }
  }
}

if (errors.length) {
  console.error(`❌ politicians_base.json が data.js と乖離しています（${errors.length}件）:`);
  for (const e of errors.slice(0, 30)) console.error('  - ' + e);
  if (errors.length > 30) console.error(`  ...ほか ${errors.length - 30} 件`);
  console.error('data.js を修正した場合は politicians_base.json も再生成してください。');
  process.exit(1);
}
console.log(`✅ politicians_base.json は data.js と同期しています（${base.length}件）`);
