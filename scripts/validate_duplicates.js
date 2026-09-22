#!/usr/bin/env node
// 同一人物が複数レコードに重複登録されていないかを検証する。
//
// 背景:
//   2026-09の全件検証で、同一人物が「平仮名表記（参議院の登録名）」と
//   「漢字表記（本名・戸籍名）」で別レコードになっている重複が9組見つかった。
//   森まさこ（本名：三好雅子）、吉良よし子（本名：吉良佳子）、
//   福島みずほ（本名：福島瑞穂）など。議員総数が790人と過大に集計され、
//   CSVを二次利用した人にも重複レコードが届いていた。
//
//   出どころは、氏名が角かっこ付きで取り込まれた参議院議員43人のバッチと
//   みられる（wikiリンクに "[釜萢敏]" のような表記が残っていた）。
//
// 検出方法:
//   (1) 読み（reading）＋院＋選挙区 が一致する別レコード
//   (2) 氏名に角かっこが含まれるレコード（取り込み時のプレースホルダ残り）
//   (3) links の URL に角かっこが含まれるレコード
//
// 使い方: node scripts/validate_duplicates.js

const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const dataJs = fs.readFileSync(path.join(ROOT, 'data.js'), 'utf8');
const POLITICIANS = vm.runInNewContext(dataJs + ';POLITICIANS', {});

const errors = [];
const norm = (v) => String(v || '').replace(/[\s　]/g, '');

// (1) 読み＋院＋選挙区が同じレコード
{
  const byKey = new Map();
  for (const p of POLITICIANS) {
    const yomi = norm(p.reading);
    if (!yomi) continue;
    const key = `${yomi}|${p.chamber}|${p.district}`;
    if (!byKey.has(key)) byKey.set(key, []);
    byKey.get(key).push(p);
  }
  for (const [key, list] of byKey) {
    if (list.length < 2) continue;
    errors.push(
      `読み・院・選挙区が同一のレコードが ${list.length}件 あります: ` +
      list.map((p) => `${p.id}「${p.name}」`).join(' / ') + `\n` +
      `      （${key}）\n` +
      `      同一人物の重複であれば統合してください。参議院の議員名簿での登録名を\n` +
      `      正式表記とし、本名は comment に記載する運用です。\n` +
      `      別人であれば、読みが同じでも選挙区が異なるはずです（例: 伊藤孝江/伊藤孝恵）。`
    );
  }
}

// (2)(3) 取り込み時のプレースホルダ（角かっこ）残り
for (const p of POLITICIANS) {
  if (/[[\]［］]/.test(p.name || '')) {
    errors.push(`${p.id}: 氏名に角かっこが含まれます「${p.name}」。取り込み時のプレースホルダが残っています。`);
  }
  const links = p.links || {};
  for (const [k, v] of Object.entries(links)) {
    if (typeof v === 'string' && /%5B|%5D|\[|\]/.test(v) && v.trim() !== '') {
      errors.push(`${p.id}「${p.name}」: links.${k} に角かっこが含まれます。取り込み時のプレースホルダが残っている可能性があります。\n      ${v.slice(0, 90)}`);
    }
  }
}

if (errors.length) {
  console.error(`❌ 議員レコードの重複検証に失敗しました（${errors.length}件）\n`);
  errors.forEach((m) => console.error('  - ' + m));
  console.error(
    `\n  同一人物の重複レコードは議員総数を過大に見せ、CSVの二次利用者にも影響します。\n` +
    `  詳細は CLAUDE.md「議員レコードの重複防止」を参照してください。`
  );
  process.exit(1);
}

console.log(`✅ 議員レコードの重複なし（${POLITICIANS.length}件）`);
