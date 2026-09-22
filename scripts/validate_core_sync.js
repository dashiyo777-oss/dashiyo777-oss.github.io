#!/usr/bin/env node
// data_core.js（politicians.html が読み込む軽量版）が data.js（サイト正本）と
// 同期しているかを検証する。乖離があれば exit 1。
//
// 背景: 2026-09-22 に data.js から evidence 101件を削除した際、data_core.js に
// 反映し忘れたため、議員一覧ページの「根拠」件数が 830件（実際は 552件）のまま
// 表示されていた。politicians.html は data.js ではなく data_core.js を読むため、
// 正本だけ直しても一覧ページには反映されない。
//
// 使い方: node scripts/validate_core_sync.js

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const dataCtx = vm.runInNewContext(
  fs.readFileSync(path.join(ROOT, 'data.js'), 'utf8') + ';({POLITICIANS, EVIDENCE})',
  {}
);
const coreCtx = vm.runInNewContext(
  fs.readFileSync(path.join(ROOT, 'data_core.js'), 'utf8') + ';({POLITICIANS, EVIDENCE_COUNT})',
  {}
);

const FIELDS = [
  'name', 'reading', 'party', 'role', 'chamber', 'district', 'status', 'gender',
  'total', 'rank', 'axes', 'survey', 'flag_crime', 'flag_caution',
];

const dataById = new Map(dataCtx.POLITICIANS.map((p) => [p.id, p]));
const coreById = new Map(coreCtx.POLITICIANS.map((p) => [p.id, p]));
const errors = [];

for (const id of dataById.keys()) {
  if (!coreById.has(id)) errors.push(`${id}: data.js にあるが data_core.js に無い`);
}
for (const id of coreById.keys()) {
  if (!dataById.has(id)) errors.push(`${id}: data_core.js にあるが data.js に無い`);
}

for (const [id, d] of dataById) {
  const c = coreById.get(id);
  if (!c) continue;
  for (const f of FIELDS) {
    const a = JSON.stringify(d[f]);
    const b = JSON.stringify(c[f]);
    if (a !== b) errors.push(`${id}（${d.name}）: ${f} が不一致 — data.js=${a} / data_core.js=${b}`);
  }
}

if (coreCtx.EVIDENCE_COUNT !== dataCtx.EVIDENCE.length) {
  errors.push(
    `EVIDENCE_COUNT が不一致 — data_core.js=${coreCtx.EVIDENCE_COUNT} / ` +
    `data.js の実際の件数=${dataCtx.EVIDENCE.length}`
  );
}

if (errors.length) {
  console.error(`❌ data_core.js が data.js と同期していません（${errors.length}件）\n`);
  errors.slice(0, 40).forEach((m) => console.error('  - ' + m));
  if (errors.length > 40) console.error(`  … ほか ${errors.length - 40}件`);
  console.error('\n  politicians.html は data_core.js を読み込みます。');
  console.error('  data.js を修正したら data_core.js にも同じ修正を反映してください。');
  process.exit(1);
}

console.log(
  `✅ data_core.js は data.js と同期しています（${dataById.size}件 / 根拠${dataCtx.EVIDENCE.length}件）`
);
