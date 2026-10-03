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
//   (4) 現職の人数が衆参の定数を超えている
//   (5) 衆議院の同じ小選挙区に現職が2人以上いる
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

// (4) 現職の人数が定数を超えていないか
//   2026-10、現職が衆468人（定数465）・参251人（定数248）と定数を上回っていた。
//   参議院は通称と本名で読みが異なる重複4組が (1) をすり抜けており、
//   衆議院は議席を失った3人と死去した1人が現職のまま残っていた。
{
  const SEATS = { 衆議院: 465, 参議院: 248 };
  for (const [chamber, seats] of Object.entries(SEATS)) {
    const n = POLITICIANS.filter((p) => p.chamber === chamber && p.status === '現職').length;
    if (n > seats) {
      errors.push(
        `${chamber}の現職が ${n}人 で、定数 ${seats} を超えています。\n` +
        `      通称と本名による重複登録、または議席を失った議員が現職のまま残っていないか、\n` +
        `      ${chamber}の公式サイトの議員一覧と照合してください。`
      );
    }
  }
}

// (5) 衆議院の同じ小選挙区に現職が2人以上いないか（比例は対象外）
{
  const byDistrict = new Map();
  for (const p of POLITICIANS) {
    if (p.chamber !== '衆議院' || p.status !== '現職') continue;
    const d = norm(p.district).replace(/区$/, '');
    if (!d || d.startsWith('比例')) continue;
    if (!byDistrict.has(d)) byDistrict.set(d, []);
    byDistrict.get(d).push(p);
  }
  for (const [d, list] of byDistrict) {
    if (list.length < 2) continue;
    errors.push(
      `衆議院 ${d}区 に現職が ${list.length}人 います: ` +
      list.map((p) => `${p.id}「${p.name}」`).join(' / ') + `\n` +
      `      小選挙区の当選者は1人です。比例復活なら district を比例ブロックに、\n` +
      `      落選・辞職・死去なら status を元職にしてください。`
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
